#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International
"""Parse the ET Programmer's Reference Manual and inject operation() pseudocode
into custom Xaifoundry instruction YAML files.

Usage:
    python3 tools/inject_pseudocode.py [--dry-run] [--manual PATH]

The script:
  1. Parses instruction definitions from the manual text file
  2. Finds matching YAML source files in spec/custom/isa/aifoundry/inst/
  3. Injects the operation pseudocode as an 'operation()' field
"""

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANUAL_DEFAULT = Path.home() / "et-man" / "ET Programmer's Reference Manual.txt"
INST_DIR = REPO_ROOT / "spec" / "custom" / "isa" / "aifoundry" / "inst"


def parse_manual(manual_path: Path) -> dict[str, dict]:
    """Parse the manual text and extract instruction definitions.

    Returns a dict mapping normalised instruction name -> {
        'raw_name': str,      # original name from Format line
        'format': str,        # full format line
        'description': str,   # description block
        'operation': str,     # operation pseudocode
        'exceptions': str,    # exceptions text
    }
    """
    text = manual_path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    instructions: dict[str, dict] = {}
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Look for "Format:" lines that define an instruction
        if not line.startswith("Format:"):
            i += 1
            continue

        format_line = line[len("Format:"):].strip()

        # Extract instruction mnemonic (first token)
        tokens = format_line.split()
        if not tokens:
            i += 1
            continue

        raw_name = tokens[0]

        # Skip CSRRW-encoded instructions — handle them specially
        if raw_name.upper() == "CSRRW":
            # Format: CSRRW xd, <csr_name>, xs
            # Extract the CSR name as the instruction name
            # e.g. "CSRRW xd, tensor_load, xs" -> "tensor_load"
            parts = format_line.split(",")
            if len(parts) >= 2:
                raw_name = parts[1].strip().split()[0].strip()
            else:
                i += 1
                continue

        # Now scan forward to find "Description:" and "Operation:" blocks
        i += 1
        description_lines: list[str] = []
        operation_lines: list[str] = []
        exceptions_text = ""
        in_description = False
        in_operation = False
        in_exceptions = False

        while i < len(lines):
            cur = lines[i]
            stripped = cur.strip()

            # Detect section headers
            if stripped.startswith("Description:"):
                in_description = True
                in_operation = False
                in_exceptions = False
                # Capture text after "Description:" on same line
                after = stripped[len("Description:"):].strip()
                if after:
                    description_lines.append(after)
                i += 1
                continue

            if stripped.startswith("Operation:"):
                in_description = False
                in_operation = True
                in_exceptions = False
                # Capture text after "Operation:" on same line
                after = stripped[len("Operation:"):].strip()
                if after:
                    operation_lines.append(after)
                i += 1
                continue

            if stripped.startswith("Exceptions:"):
                in_operation = False
                in_description = False
                in_exceptions = True
                after = stripped[len("Exceptions:"):].strip()
                if after:
                    exceptions_text = after
                i += 1
                continue

            if stripped.startswith("Restrictions:"):
                in_exceptions = False
                i += 1
                # After Restrictions, we're done with this instruction
                break

            # Detect start of encoding diagram (signals end of current block)
            # Encoding diagrams start with bit position numbers like "31" or
            # lines of just digits/spaces, or lines with field patterns
            if in_operation and _is_encoding_line(stripped, lines, i):
                in_operation = False
                # Don't increment i here - let the outer loop continue
                break

            # Detect next instruction definition (Name: line followed by Format:)
            if stripped.startswith("Name:") or stripped.startswith("Format:"):
                # We've hit the next instruction
                break

            # Accumulate content
            if in_description:
                description_lines.append(cur.rstrip())
            elif in_operation:
                operation_lines.append(cur.rstrip())
            elif in_exceptions:
                if stripped:
                    exceptions_text += " " + stripped

            i += 1

        # Clean up operation text
        operation = _clean_operation(operation_lines)

        if operation:
            norm_name = _normalise_name(raw_name)
            instructions[norm_name] = {
                "raw_name": raw_name,
                "format": format_line,
                "description": "\n".join(description_lines).strip(),
                "operation": operation,
                "exceptions": exceptions_text.strip(),
            }

    return instructions


def _is_encoding_line(stripped: str, lines: list[str], idx: int) -> bool:
    """Heuristic to detect encoding diagram lines that follow Operation blocks."""
    if not stripped:
        # Blank line — check if next non-blank line looks like encoding
        for j in range(idx + 1, min(idx + 4, len(lines))):
            nxt = lines[j].strip()
            if nxt and re.match(r"^\d{1,2}(\s+\d{1,2})*$", nxt):
                return True
            if nxt:
                break
        return False
    # Line is just bit positions like "31  27 26 25 24"
    if re.match(r"^\d{1,2}(\s+\d{1,2})*$", stripped):
        return True
    return False


def _clean_operation(op_lines: list[str]) -> str:
    """Clean up extracted operation pseudocode."""
    # Remove trailing blank lines
    while op_lines and not op_lines[-1].strip():
        op_lines.pop()
    # Remove leading blank lines
    while op_lines and not op_lines[0].strip():
        op_lines.pop(0)

    if not op_lines:
        return ""

    # Find minimum indentation (ignoring blank lines)
    min_indent = 999
    for line in op_lines:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            min_indent = min(min_indent, indent)

    if min_indent == 999:
        min_indent = 0

    # Dedent
    cleaned = []
    for line in op_lines:
        if line.strip():
            cleaned.append(line[min_indent:].rstrip())
        else:
            cleaned.append("")

    return "\n".join(cleaned)


def _normalise_name(name: str) -> str:
    """Normalise instruction name for matching."""
    return name.lower().strip().replace(" ", "")


def find_yaml_files(inst_dir: Path) -> dict[str, Path]:
    """Scan the instruction YAML directory and build a name -> path mapping."""
    mapping: dict[str, Path] = {}
    if not inst_dir.exists():
        return mapping

    for yaml_path in inst_dir.rglob("*.yaml"):
        # Read the name field from the YAML to get the canonical name
        # (faster than full YAML parse — just grep for 'name:')
        try:
            content = yaml_path.read_text(encoding="utf-8")
        except Exception:
            continue

        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("name:"):
                yaml_name = stripped[len("name:"):].strip().strip("'\"")
                norm = _normalise_name(yaml_name)
                mapping[norm] = yaml_path
                break

    return mapping


# Manual-to-YAML name overrides for instructions whose names differ
NAME_OVERRIDES: dict[str, str] = {
    # Tensor instructions: manual uses CSR name, YAML uses combined name
    "tensor_load": "tensorload",
    "tensor_load_l2": "tensorloadl2scp",
    "tensor_fma": "tensorfma32",
    "tensor_quant": "tensorquant",
    "tensor_store": "tensorstore",
    "tensor_reduce": "tensorreduce",
    "tensor_wait": "tensorwait",
    # Cache instructions: manual uses CSR-style names
    "evict_sw": "cache.evictsw",
    "evict_va": "cache.evictva",
    "flush_sw": "cache.flushsw",
    "flush_va": "cache.flushva",
    "lock_sw": "cache.locksw",
    "lock_va": "cache.lockva",
    "prefetch_va": "cache.prefetchva",
    "unlock_sw": "cache.unlocksw",
    "unlock_va": "cache.unlockva",
    # Mask: manual has maskpopcz, YAML has maskpopz
    "maskpopcz": "maskpopz",
}


def inject_operation(yaml_path: Path, operation: str, dry_run: bool = False) -> bool:
    """Add operation() field to a YAML file. Returns True if modified."""
    content = yaml_path.read_text(encoding="utf-8")

    # Skip if already has operation()
    if '"operation()":' in content or "'operation()':" in content or "operation():" in content:
        return False

    # Build the YAML block for the operation
    # Use literal block scalar for multi-line, quoted string for single-line
    op_lines = operation.split("\n")
    if len(op_lines) == 1:
        # Single line — use quoted string
        escaped = operation.replace("\\", "\\\\").replace('"', '\\"')
        yaml_block = f'"operation()": "{escaped}"\n'
    else:
        # Multi-line — use literal block scalar
        yaml_block = '"operation()": |\n'
        for line in op_lines:
            yaml_block += f"  {line}\n"

    # Insert before the end of the file (append)
    if not content.endswith("\n"):
        content += "\n"
    content += yaml_block

    if not dry_run:
        yaml_path.write_text(content, encoding="utf-8")

    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Don't modify files")
    parser.add_argument(
        "--manual",
        type=Path,
        default=MANUAL_DEFAULT,
        help=f"Path to manual text file (default: {MANUAL_DEFAULT})",
    )
    args = parser.parse_args()

    manual_path: Path = args.manual
    if not manual_path.exists():
        print(f"ERROR: Manual not found: {manual_path}", file=sys.stderr)
        sys.exit(1)

    if not INST_DIR.exists():
        print(f"ERROR: Instruction dir not found: {INST_DIR}", file=sys.stderr)
        sys.exit(1)

    # Step 1: Parse the manual
    print(f"Parsing manual: {manual_path}")
    manual_instrs = parse_manual(manual_path)
    print(f"  Found {len(manual_instrs)} instruction definitions in manual")

    # Step 2: Find YAML files
    print(f"Scanning YAML files: {INST_DIR}")
    yaml_mapping = find_yaml_files(INST_DIR)
    print(f"  Found {len(yaml_mapping)} instruction YAML files")

    # Step 3: Match and inject
    matched = 0
    unmatched_manual: list[str] = []
    modified: list[str] = []
    skipped: list[str] = []

    for norm_name, instr_data in sorted(manual_instrs.items()):
        # Try direct match
        target_name = norm_name

        # Apply name overrides
        if norm_name in NAME_OVERRIDES:
            target_name = _normalise_name(NAME_OVERRIDES[norm_name])

        if target_name in yaml_mapping:
            yaml_path = yaml_mapping[target_name]
            operation = instr_data["operation"]

            if inject_operation(yaml_path, operation, dry_run=args.dry_run):
                modified.append(f"  {instr_data['raw_name']} -> {yaml_path.relative_to(REPO_ROOT)}")
                matched += 1
            else:
                skipped.append(f"  {instr_data['raw_name']} (already has operation())")
                matched += 1
        else:
            unmatched_manual.append(
                f"  {instr_data['raw_name']} (normalised: {norm_name}, tried: {target_name})"
            )

    # Step 4: Report
    print(f"\n{'='*60}")
    print(f"Results ({'DRY RUN' if args.dry_run else 'APPLIED'}):")
    print(f"  Manual instructions parsed: {len(manual_instrs)}")
    print(f"  YAML files found:           {len(yaml_mapping)}")
    print(f"  Matched & modified:          {len(modified)}")
    print(f"  Matched & skipped:           {len(skipped)}")
    print(f"  Unmatched from manual:       {len(unmatched_manual)}")

    if modified:
        print(f"\nModified files ({len(modified)}):")
        for m in modified:
            print(m)

    if skipped:
        print(f"\nSkipped (already have operation()):")
        for s in skipped:
            print(s)

    if unmatched_manual:
        print(f"\nUnmatched manual instructions ({len(unmatched_manual)}):")
        for u in unmatched_manual:
            print(u)

    # Also report YAML files that had no match from the manual
    matched_yamls = set()
    for norm_name in manual_instrs:
        target = norm_name
        if norm_name in NAME_OVERRIDES:
            target = _normalise_name(NAME_OVERRIDES[norm_name])
        if target in yaml_mapping:
            matched_yamls.add(target)

    unmatched_yaml = [
        name for name in sorted(yaml_mapping.keys()) if name not in matched_yamls
    ]
    if unmatched_yaml:
        print(f"\nYAML files with no manual match ({len(unmatched_yaml)}):")
        for name in unmatched_yaml:
            print(f"  {name} -> {yaml_mapping[name].relative_to(REPO_ROOT)}")

    return 0 if not unmatched_manual else 1


if __name__ == "__main__":
    main()
