# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""
Custom extension compliance checks for the RISC-V MCP server.

Reimplements the 6 checks from tools/check_custom_compliance.rb in Python,
operating on parsed YAML dicts from gen/resolved_spec/<config>/.

Checks:
  1. Opcode Space — bits[6:0] must be in custom-0..3 space
  2. Collision Detection — custom encoding not indistinguishable from standard
  3. Variable Name Convention — rs1@19:15, rs2@24:20, rd@11:7, rs3@31:27
  4. Assembly-Encoding Consistency — assembly operands match encoding variables
  5. Encoding Format Integrity — bits[1:0]=11 for 32-bit, valid width, bit coverage
  6. Extension Path Consistency — file under directory matching definedBy
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

# ============================================================================
# Constants
# ============================================================================

# Standard register variable positions per RISC-V ISA (R/I/S/B/U/J/R4-type)
# Source: RISC-V Unprivileged ISA Manual, encoding format tables
STANDARD_VAR_POSITIONS: dict[str, list[int]] = {
    "rs1": [19, 18, 17, 16, 15],
    "xs1": [19, 18, 17, 16, 15],
    "fs1": [19, 18, 17, 16, 15],
    "rs2": [24, 23, 22, 21, 20],
    "xs2": [24, 23, 22, 21, 20],
    "fs2": [24, 23, 22, 21, 20],
    "rd": [11, 10, 9, 8, 7],
    "xd": [11, 10, 9, 8, 7],
    "fd": [11, 10, 9, 8, 7],
    "rs3": [31, 30, 29, 28, 27],
    "fs3": [31, 30, 29, 28, 27],
}

# Assembly operand -> expected encoding variable names
ASM_TO_VAR: dict[str, list[str]] = {
    "xd": ["rd", "xd"],
    "xs1": ["rs1", "xs1"],
    "xs2": ["rs2", "xs2"],
    "fd": ["rd", "fd"],
    "fs1": ["rs1", "fs1"],
    "fs2": ["rs2", "fs2"],
    "fs3": ["rs3", "fs3"],
    "rd": ["rd"],
    "rs1": ["rs1"],
    "rs2": ["rs2"],
    "rs3": ["rs3"],
}

CUSTOM_OPCODE_PATTERN = re.compile(r"^custom-")
RESERVED_OPCODE = "1101011"

# Custom opcode spaces available for use
CUSTOM_OPCODES: dict[str, str] = {
    "custom-0": "0001011",
    "custom-1": "0101011",
    "custom-2": "1011011",
    "custom-3": "1111011",
}

# Tool definition exposed to server.py
TOOL_CHECK_COMPLIANCE = {
    "name": "check_custom_compliance",
    "description": (
        "Run compliance checks on custom extension instructions. "
        "Validates opcode space usage, encoding collisions with standard instructions, "
        "register variable positions, assembly-encoding consistency, encoding format "
        "integrity, and extension path consistency. Returns structured findings with "
        "severity levels (warn/info). Optionally filter to specific checks."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "checks": {
                "description": (
                    "Which checks to run (omit for all). "
                    "1=Opcode Space, 2=Collision Detection, 3=Variable Convention, "
                    "4=Assembly-Encoding Consistency, 5=Encoding Format Integrity, "
                    "6=Extension Path Consistency"
                ),
                "type": "array",
                "items": {"type": "integer", "enum": [1, 2, 3, 4, 5, 6]},
            },
        },
    },
}


# ============================================================================
# Helpers
# ============================================================================


def _extract_opcode(match_str: str) -> str | None:
    """Extract bits[6:0] from a match string (MSB-first)."""
    if len(match_str) < 7:
        return None
    return match_str[-7:]


def _parse_location(location_str: str) -> list[int]:
    """Parse a location string into bit positions (high to low).

    Supports formats:
    - "19-15" → [19, 18, 17, 16, 15]
    - "31-25|11-7" → [31, 30, 29, 28, 27, 26, 25, 11, 10, 9, 8, 7] (split fields)
    - "7" → [7]
    """
    bits: list[int] = []
    for segment in str(location_str).split("|"):
        segment = segment.strip()
        if "-" in segment:
            parts = segment.split("-")
            high = int(parts[0])
            low = int(parts[1])
            bits.extend(range(high, low - 1, -1))
        else:
            bits.append(int(segment))
    return bits


def _parse_encoding_variables(yaml_vars: list[dict] | None) -> list[dict[str, Any]]:
    """Parse encoding.variables from YAML into [{name, bits}] dicts."""
    if not yaml_vars:
        return []
    result = []
    for var in yaml_vars:
        name = var.get("name", "")
        location = var.get("location", "")
        bits = _parse_location(location) if location else []
        result.append({"name": name, "bits": bits})
    return result


def _parse_assembly_operands(asm_str: str | None) -> list[str]:
    """Parse assembly string to extract operand tokens (skip the mnemonic)."""
    if not asm_str or not asm_str.strip():
        return []
    parts = asm_str.strip().split(None, 1)
    if len(parts) < 2:
        return []
    operand_str = parts[1]
    return [op.strip() for op in re.split(r"[,()]+", operand_str) if op.strip()]


def _collect_extension_names(defined_by: Any) -> list[str]:
    """Recursively collect extension names from a definedBy structure."""
    names: list[str] = []
    if isinstance(defined_by, str):
        names.append(defined_by)
    elif isinstance(defined_by, dict):
        if "name" in defined_by:
            names.append(defined_by["name"])
        elif "extension" in defined_by:
            names.extend(_collect_extension_names(defined_by["extension"]))
        else:
            for v in defined_by.values():
                if isinstance(v, list):
                    for item in v:
                        names.extend(_collect_extension_names(item))
                else:
                    names.extend(_collect_extension_names(v))
    return names


def _is_custom_instruction(path: Path) -> bool:
    """Determine if an instruction is custom based on its path (ext dir starts with X)."""
    parts = path.parts
    for i, part in enumerate(parts):
        if part == "inst" and i + 1 < len(parts):
            ext_dir = parts[i + 1]
            return ext_dir.startswith("X")
    return False


def _defined_in_base(inst_data: dict, xlen: int) -> bool:
    """Check if an instruction is defined for the given XLEN (32 or 64).

    Rules:
    - If 'base' field exists: instruction is only defined in that base
    - If definedBy contains allOf with xlen constraint: only that xlen
    - Otherwise: defined in all bases
    """
    base = inst_data.get("base")
    if base is not None:
        return int(base) == xlen

    # Check definedBy for xlen constraints (e.g., allOf: [{xlen: 32}, ...])
    defined_by = inst_data.get("definedBy")
    if isinstance(defined_by, dict) and "allOf" in defined_by:
        for item in defined_by["allOf"]:
            if isinstance(item, dict) and "xlen" in item:
                return int(item["xlen"]) == xlen

    return True


def _encodings_indistinguishable(match_a: str, match_b: str) -> bool:
    """Check if two encoding match strings are indistinguishable.

    Two encodings are indistinguishable if for every bit position,
    at least one is a don't-care ('-') or they have the same fixed value.
    """
    if len(match_a) != len(match_b):
        return False
    for ca, cb in zip(match_a, match_b, strict=True):
        if ca == "-" or cb == "-":
            continue
        if ca != cb:
            return False
    return True


# ============================================================================
# Check implementations
# ============================================================================


def _check_opcode_space(name: str, match_str: str, opcode_map: dict[str, str]) -> list[dict]:
    """Check 1: Opcode space classification."""
    findings: list[dict] = []
    if len(match_str) != 32:
        return findings

    opcode = _extract_opcode(match_str)
    if opcode is None:
        return findings

    opcode_fixed = opcode.replace("-", "0")
    opcode_name = opcode_map.get(opcode_fixed)

    if opcode_name:
        if not CUSTOM_OPCODE_PATTERN.match(opcode_name):
            # Build a suggested encoding with custom-0 opcode
            suggested = match_str[:-7] + CUSTOM_OPCODES["custom-0"] if len(match_str) >= 7 else ""
            findings.append(
                {
                    "severity": "warn",
                    "inst": name,
                    "message": (f"uses standard opcode space {opcode_name} (bits[6:0]={opcode})"),
                    "suggestion": (
                        f"Move to a custom opcode space. Change bits[6:0] from "
                        f"{opcode} to one of: "
                        f"custom-0={CUSTOM_OPCODES['custom-0']}, "
                        f"custom-1={CUSTOM_OPCODES['custom-1']}, "
                        f"custom-2={CUSTOM_OPCODES['custom-2']}, "
                        f"custom-3={CUSTOM_OPCODES['custom-3']}. "
                        f"Example: encoding.match: '{suggested}' (using custom-0). "
                        f"If the instruction intentionally reuses {opcode_name} space "
                        f"(e.g., CSR-mapped), document this with a comment in the YAML."
                    ),
                }
            )
    elif opcode_fixed[-3:] == "111":
        findings.append(
            {
                "severity": "warn",
                "inst": name,
                "message": (
                    f"uses >32b variable-length instruction prefix "
                    f"opcode space (bits[6:0]={opcode})"
                ),
                "suggestion": (
                    f"bits[6:0] ending in 111 (with bits[4:2] != 111) is reserved "
                    f"for future >32-bit instruction lengths. Move to a custom opcode "
                    f"space: custom-0={CUSTOM_OPCODES['custom-0']}, "
                    f"custom-1={CUSTOM_OPCODES['custom-1']}, etc. "
                    f"If this is intentionally a 48-bit instruction, ensure the "
                    f"encoding.match length is 48 bits, not 32."
                ),
            }
        )
    elif opcode_fixed == RESERVED_OPCODE:
        findings.append(
            {
                "severity": "info",
                "inst": name,
                "message": f"uses reserved opcode space (bits[6:0]={opcode})",
            }
        )
    elif "-" in opcode:
        findings.append(
            {
                "severity": "info",
                "inst": name,
                "message": (
                    f"opcode bits[6:0]={opcode} contain variable bits — cannot classify uniquely"
                ),
            }
        )
    else:
        findings.append(
            {
                "severity": "info",
                "inst": name,
                "message": f"uses unassigned opcode space (bits[6:0]={opcode})",
            }
        )

    return findings


def _check_collisions(
    custom_insts: list[dict], standard_insts: list[dict], xlen: int
) -> list[dict]:
    """Check 2: Standard instruction collision detection."""
    findings: list[dict] = []

    for cinst in custom_insts:
        if not _defined_in_base(cinst["data"], xlen):
            continue
        cmatch = cinst["data"].get("encoding", {}).get("match", "")
        if not cmatch:
            continue

        for sinst in standard_insts:
            if not _defined_in_base(sinst["data"], xlen):
                continue
            if cinst["name"] == sinst["name"]:
                continue
            smatch = sinst["data"].get("encoding", {}).get("match", "")
            if not smatch:
                continue
            if len(cmatch) != len(smatch):
                continue

            if _encodings_indistinguishable(cmatch, smatch):
                # Find which bits could differentiate
                diff_positions = []
                for pos, (ca, cb) in enumerate(zip(cmatch, smatch, strict=True)):
                    if ca == "-" and cb != "-":
                        diff_positions.append(len(cmatch) - 1 - pos)
                findings.append(
                    {
                        "severity": "warn",
                        "inst": cinst["name"],
                        "message": (
                            f"encoding indistinguishable from standard "
                            f"instruction '{sinst['name']}'"
                        ),
                        "suggestion": (
                            f"The encodings overlap because variable (don't-care) bits "
                            f"in '{cinst['name']}' match the fixed bits of "
                            f"'{sinst['name']}'. Fix by: "
                            f"(1) Move to a different opcode space (custom-0..3) so "
                            f"bits[6:0] differ. "
                            f"(2) Fix specific bits to distinguish: set bits "
                            f"{diff_positions[:5]}{'...' if len(diff_positions) > 5 else ''} "
                            f"to values that differ from '{sinst['name']}'. "
                            f"(3) If hardware disambiguates via context (e.g., CSR "
                            f"address), document this in the YAML description."
                        ),
                    }
                )

    return findings


def _check_variable_conventions(
    name: str, match_str: str, variables: list[dict[str, Any]]
) -> list[dict]:
    """Check 3: Variable name convention (standard register positions)."""
    findings: list[dict] = []
    if len(match_str) != 32:
        return findings

    for var in variables:
        expected_bits = STANDARD_VAR_POSITIONS.get(var["name"])
        if expected_bits is None:
            continue
        actual_bits = sorted(var["bits"], reverse=True)
        if actual_bits != expected_bits:
            hi = expected_bits[0]
            lo = expected_bits[-1]
            findings.append(
                {
                    "severity": "warn",
                    "inst": name,
                    "message": (
                        f"variable '{var['name']}' at bits {actual_bits} "
                        f"but standard position is {expected_bits}"
                    ),
                    "suggestion": (
                        f"Move '{var['name']}' to standard position bits[{hi}:{lo}] "
                        f'(location: "{hi}-{lo}") and update encoding.match so those '
                        f"bits are '-' (variable). If the non-standard position is "
                        f"intentional (custom format), rename the variable to avoid "
                        f"a standard name — e.g., use 'src2' instead of '{var['name']}'."
                    ),
                }
            )

    return findings


def _check_assembly_encoding_consistency(
    name: str, variables: list[dict[str, Any]], asm: str | None
) -> list[dict]:
    """Check 4: Assembly-encoding consistency."""
    findings: list[dict] = []
    if asm is None:
        return findings

    operands = _parse_assembly_operands(asm)
    var_names = [v["name"] for v in variables]

    for op in operands:
        expected_vars = ASM_TO_VAR.get(op)
        if expected_vars:
            if not any(ev in var_names for ev in expected_vars):
                std_positions = {
                    ev: STANDARD_VAR_POSITIONS.get(ev)
                    for ev in expected_vars
                    if ev in STANDARD_VAR_POSITIONS
                }
                pos_hint = ""
                for _ev, bits in std_positions.items():
                    if bits:
                        pos_hint = f' at location "{bits[0]}-{bits[-1]}"'
                        break
                findings.append(
                    {
                        "severity": "warn",
                        "inst": name,
                        "message": (
                            f"assembly operand '{op}' has no matching encoding "
                            f"variable (expected one of {expected_vars}, "
                            f"found {var_names})"
                        ),
                        "suggestion": (
                            f"Add an encoding variable for '{op}'. Add to "
                            f"encoding.variables: - name: {expected_vars[0]}, "
                            f'location: "{STANDARD_VAR_POSITIONS.get(expected_vars[0], ["?"])[0]}-'
                            f'{STANDARD_VAR_POSITIONS.get(expected_vars[0], ["?", "?"])[-1]}"'
                            f"{pos_hint} and set the corresponding bits in "
                            f"encoding.match to '-'. Alternatively, if '{op}' is "
                            f"implicit (not encoded), remove it from the assembly string."
                        ),
                    }
                )
        else:
            if not any(vn in op or op in vn for vn in var_names):
                findings.append(
                    {
                        "severity": "info",
                        "inst": name,
                        "message": (
                            f"assembly operand '{op}' has no obvious encoding "
                            f"variable match (variables: {var_names})"
                        ),
                    }
                )

    return findings


def _check_encoding_format_integrity(
    name: str, match_str: str, variables: list[dict[str, Any]]
) -> list[dict]:
    """Check 5: Encoding format integrity."""
    findings: list[dict] = []

    # bits[1:0] == 11 for 32-bit encodings
    if len(match_str) == 32:
        low_bits = match_str[-2:]
        if low_bits != "11":
            fixed = match_str[:-2] + "11"
            findings.append(
                {
                    "severity": "warn",
                    "inst": name,
                    "message": (f"bits[1:0]='{low_bits}' but expected '11' for 32-bit encoding"),
                    "suggestion": (
                        f"Per RISC-V spec, all 32-bit instructions must have "
                        f"bits[1:0]=11. Change encoding.match to: '{fixed}'. "
                        f"If this is a 16-bit compressed instruction, the match "
                        f"string should be 16 bits long with bits[1:0] != 11."
                    ),
                }
            )

    # Valid instruction width
    if len(match_str) not in (16, 32, 48):
        findings.append(
            {
                "severity": "warn",
                "inst": name,
                "message": (f"match string is {len(match_str)} bits (expected 16, 32, or 48)"),
                "suggestion": (
                    f"encoding.match must be exactly 16, 32, or 48 bits. "
                    f"Current length is {len(match_str)}. Pad or trim to the "
                    f"correct width."
                ),
            }
        )

    # Bit coverage: every '-' covered by a variable, every '0'/'1' not
    var_bits: set[int] = set()
    for var in variables:
        for b in var["bits"]:
            var_bits.add(b)

    for i in range(len(match_str)):
        bit_idx = len(match_str) - 1 - i
        char = match_str[i]

        if char == "-":
            if bit_idx not in var_bits:
                findings.append(
                    {
                        "severity": "warn",
                        "inst": name,
                        "message": (f"bit {bit_idx} is '-' but not covered by any decode variable"),
                        "suggestion": (
                            f"Bit {bit_idx} is marked as variable ('-') in "
                            f"encoding.match but no encoding.variables entry covers "
                            f"it. Either: (1) add a variable with a location that "
                            f"includes bit {bit_idx}, or (2) fix this bit to '0' or "
                            f"'1' in encoding.match if it should be constant."
                        ),
                    }
                )
        elif bit_idx in var_bits:
            findings.append(
                {
                    "severity": "warn",
                    "inst": name,
                    "message": (
                        f"bit {bit_idx} is fixed ('{char}') but also covered by a decode variable"
                    ),
                    "suggestion": (
                        f"Bit {bit_idx} is set to '{char}' in encoding.match but "
                        f"also claimed by an encoding variable. Either: (1) change "
                        f"bit {bit_idx} to '-' in encoding.match, or (2) remove bit "
                        f"{bit_idx} from the variable's location range."
                    ),
                }
            )

    return findings


def _check_extension_path_consistency(name: str, path: Path, defined_by: Any) -> list[dict]:
    """Check 6: Extension path consistency."""
    findings: list[dict] = []
    if defined_by is None:
        return findings

    ext_names = _collect_extension_names(defined_by)
    if not ext_names:
        return findings

    # Extract extension directory from path
    parts = path.parts
    ext_dir = None
    for i, part in enumerate(parts):
        if part == "inst" and i + 1 < len(parts):
            ext_dir = parts[i + 1]
            break

    if ext_dir is None:
        return findings

    if ext_dir not in ext_names:
        findings.append(
            {
                "severity": "warn",
                "inst": name,
                "message": (f"file is under inst/{ext_dir}/ but definedBy lists {ext_names}"),
                "suggestion": (
                    f"The file path and definedBy must agree. Either: "
                    f"(1) move the file to inst/{ext_names[0]}/{name}.yaml, or "
                    f"(2) change definedBy to '{ext_dir}', or "
                    f"(3) if the instruction belongs to multiple extensions, use "
                    f"definedBy with allOf/anyOf and ensure one matches '{ext_dir}'."
                ),
            }
        )

    return findings


# ============================================================================
# Main handler
# ============================================================================


async def check_custom_compliance(
    args: dict[str, Any],
    config_name: str,
    path_iterators: dict[str, list[Path]],
    load_yaml: Any,
) -> dict:
    """Run compliance checks on custom extension instructions.

    Args:
        args: Tool arguments (optional 'checks' filter).
        config_name: Active CPU configuration name.
        path_iterators: Dict with 'inst' and 'inst_opcode' path lists.
        load_yaml: Callable to load and parse a YAML file.

    Returns:
        Structured findings dict with summary and per-category results.
    """
    requested_checks = set(args.get("checks") or [1, 2, 3, 4, 5, 6])

    # 1. Load opcode map from inst_opcode paths
    opcode_map: dict[str, str] = {}
    for p in path_iterators.get("inst_opcode", []):
        data = load_yaml(p)
        if not data or data.get("kind") != "instruction_opcode":
            continue
        oname = data.get("name", "")
        value = (data.get("data") or {}).get("value")
        if value is None:
            continue
        int_val = int(str(value).replace("0b", ""), 2) if isinstance(value, str) else value
        bin_str = format(int_val, "07b")
        opcode_map[bin_str] = oname

    # 2. Load all instructions, partition custom vs standard
    custom_insts: list[dict] = []
    standard_insts: list[dict] = []

    for p in path_iterators.get("inst", []):
        data = load_yaml(p)
        if not data or data.get("kind") != "instruction":
            continue
        inst_name = data.get("name", p.stem)
        entry = {"name": inst_name, "data": data, "path": p}
        if _is_custom_instruction(p):
            custom_insts.append(entry)
        else:
            standard_insts.append(entry)

    # 3. Run checks on each custom instruction
    findings: dict[str, list[dict]] = defaultdict(list)

    for inst in custom_insts:
        data = inst["data"]
        name = inst["name"]
        path = inst["path"]
        match_str = (data.get("encoding") or {}).get("match", "")
        yaml_vars = (data.get("encoding") or {}).get("variables", [])
        variables = _parse_encoding_variables(yaml_vars)
        asm = data.get("assembly")
        defined_by = data.get("definedBy")

        checked = False
        for xlen in (32, 64):
            if not _defined_in_base(data, xlen):
                continue
            checked = True

            if 1 in requested_checks:
                findings["1. Opcode Space"].extend(_check_opcode_space(name, match_str, opcode_map))
            if 3 in requested_checks:
                findings["3. Variable Name Convention"].extend(
                    _check_variable_conventions(name, match_str, variables)
                )
            if 4 in requested_checks:
                findings["4. Assembly-Encoding Consistency"].extend(
                    _check_assembly_encoding_consistency(name, variables, asm)
                )
            if 5 in requested_checks:
                findings["5. Encoding Format Integrity"].extend(
                    _check_encoding_format_integrity(name, match_str, variables)
                )

        if not checked:
            findings["0. Skipped"].append(
                {
                    "severity": "info",
                    "inst": name,
                    "message": f"not defined in any checked XLEN (base={data.get('base')})",
                }
            )

        if 6 in requested_checks:
            findings["6. Extension Path Consistency"].extend(
                _check_extension_path_consistency(name, path, defined_by)
            )

    # 4. Collision detection (custom vs standard) per xlen
    if 2 in requested_checks:
        for xlen in (32, 64):
            findings["2. Collision Detection"].extend(
                _check_collisions(custom_insts, standard_insts, xlen)
            )

    # 5. Build result — drop empty categories
    result_findings = {k: v for k, v in sorted(findings.items()) if v}

    # Summary counts
    warn_count = sum(
        1 for items in result_findings.values() for f in items if f["severity"] == "warn"
    )
    info_count = sum(
        1 for items in result_findings.values() for f in items if f["severity"] == "info"
    )

    return {
        "config": config_name,
        "custom_instructions": len(custom_insts),
        "standard_instructions": len(standard_insts),
        "summary": {
            "warn": warn_count,
            "info": info_count,
            "total": warn_count + info_count,
        },
        "findings": result_findings,
    }
