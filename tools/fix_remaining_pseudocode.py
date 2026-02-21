#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International
"""Fix remaining 26 instructions without operation() pseudocode and clean up
any junk text that leaked into existing operation() fields."""

import re
from pathlib import Path

INST_DIR = Path(__file__).resolve().parent.parent / "spec" / "custom" / "isa" / "aifoundry" / "inst"

# ---- Pseudocode for the 26 missing instructions ----
# Based on patterns from existing similar instructions and manual table descriptions.

MISSING_OPS: dict[str, str] = {
    # Conversion: up-convert to FP32 (fcvt.ps.X → f32)
    "fcvt.ps.sn8": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = snorm8_to_f32(fs1.e<i>);
}""",
    "fcvt.ps.sn16": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = snorm16_to_f32(fs1.e<i>);
}""",
    "fcvt.ps.un2": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = unorm2_to_f32(fs1.e<i>);
}""",
    "fcvt.ps.un8": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = unorm8_to_f32(fs1.e<i>);
}""",
    "fcvt.ps.un10": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = unorm10_to_f32(fs1.e<i>);
}""",
    "fcvt.ps.un16": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = unorm16_to_f32(fs1.e<i>);
}""",
    "fcvt.ps.un24": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = unorm24_to_f32(fs1.e<i>);
}""",
    "fcvt.ps.f10": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f10_to_f32(fs1.e<i>);
}""",
    "fcvt.ps.f11": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f11_to_f32(fs1.e<i>);
}""",
    # Conversion: down-convert from FP32 (fcvt.X.ps → X)
    "fcvt.sn8.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f32_to_snorm8(fs1.e<i>);
}""",
    "fcvt.sn16.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f32_to_snorm16(fs1.e<i>);
}""",
    "fcvt.un2.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f32_to_unorm2(fs1.e<i>);
}""",
    "fcvt.un8.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f32_to_unorm8(fs1.e<i>);
}""",
    "fcvt.un10.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f32_to_unorm10(fs1.e<i>);
}""",
    "fcvt.un16.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f32_to_unorm16(fs1.e<i>);
}""",
    "fcvt.un24.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f32_to_unorm24(fs1.e<i>);
}""",
    "fcvt.f10.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f32_to_f10(fs1.e<i>);
}""",
    "fcvt.f11.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = f32_to_f11(fs1.e<i>);
}""",
    # Cubemap instructions
    "cubeface.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = cubemap_face(fs1.e<i>, fs2.e<i>);
}""",
    "cubefaceidx.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = cubemap_face_index(fs1.e<i>, fs2.e<i>);
}""",
    "cubesgnsc.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = cubemap_sign_sc(fs1.e<i>, fs2.e<i>);
}""",
    "cubesgntc.ps": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = cubemap_sign_tc(fs1.e<i>, fs2.e<i>);
}""",
    # Bitmixb
    "bitmixb": """\
for (i = 0; i < VLEN/32; i++) {
  if (m0.bit<i>) fd.e<i> = bitmix_bytes(fs1.e<i>, fs2.e<i>);
}""",
    # Atomic compare-and-swap (pattern from amocmpswapg.d)
    "amocmpswapg.w": "rd = atomic_global_compare_swap(rs1, x31, rs2, 32)",
    # Cache lock VA (from manual description: soft-lock and zero cache line)
    "cache.lockva": """\
PA = translate(xs1[47:6]);
for (i = 0; i < xs1[3:0] + 1; i++) {
  if (!xs1[63] || tensor_mask[i] == 1) {
    cache_zero_and_softlock(PA + i * stride);
  }
}
xd = 0;""",
    # Tensor wait/fence (from manual: stall until event completes)
    "tensorwait": "stall_until_event(xs1[3:0]); xd = 0;",
}


def find_yaml_by_name(name: str) -> Path | None:
    """Find the YAML file with matching name field."""
    for p in INST_DIR.rglob("*.yaml"):
        try:
            text = p.read_text()
        except Exception:
            continue
        for line in text.split("\n"):
            s = line.strip()
            if s.startswith("name:"):
                yaml_name = s[len("name:"):].strip().strip("'\"")
                if yaml_name == name:
                    return p
    return None


def clean_existing_operations():
    """Find and fix operation() fields with junk text leaked in."""
    fixed = 0
    for p in INST_DIR.rglob("*.yaml"):
        try:
            text = p.read_text()
        except Exception:
            continue

        if '"operation()":' not in text:
            continue

        lines = text.split("\n")
        new_lines = []
        in_op = False
        op_indent = 0
        junk_found = False

        for line in lines:
            if '"operation()":' in line:
                in_op = True
                new_lines.append(line)
                # Detect if it's a block scalar (|) or inline string
                if line.strip().endswith("|"):
                    op_indent = len(line) - len(line.lstrip()) + 2
                else:
                    in_op = False
                continue

            if in_op:
                stripped = line.strip()
                # Detect junk: chapter headings, table of contents lines,
                # or instruction names that leaked in
                if stripped and re.match(r"^\d+\s+[A-Z]", stripped):
                    junk_found = True
                    in_op = False
                    continue
                if stripped and re.match(r"^[A-Z]{3,}\.[A-Z]{2,}", stripped):
                    # Leaked instruction name like "FCVT.PS.PWU"
                    junk_found = True
                    in_op = False
                    continue
                if stripped and re.match(r"^Table \d+", stripped):
                    junk_found = True
                    in_op = False
                    continue
                if junk_found:
                    # Skip remaining junk lines
                    continue
                new_lines.append(line)
            else:
                if junk_found:
                    junk_found = False
                new_lines.append(line)

        new_text = "\n".join(new_lines)
        # Clean trailing whitespace in operation blocks
        new_text = re.sub(r'\n\s*\n$', '\n', new_text)

        if new_text != text:
            p.write_text(new_text)
            print(f"  Cleaned: {p.relative_to(INST_DIR.parent.parent.parent.parent.parent)}")
            fixed += 1

    return fixed


def add_missing_operations():
    """Add operation() to the 26 files that don't have it."""
    added = 0
    for name, operation in sorted(MISSING_OPS.items()):
        path = find_yaml_by_name(name)
        if path is None:
            print(f"  WARNING: No YAML found for '{name}'")
            continue

        text = path.read_text()

        # Skip if already has a real operation (not "None")
        if '"operation()":' in text:
            existing = text.split('"operation()":')[1].strip().split("\n")[0].strip()
            if existing not in ('', '"None"', "'None'"):
                print(f"  Skipped (already has operation): {name}")
                continue
            # Remove the old "None" operation
            text = re.sub(r'"operation\(\)":\s*"None"\n?', '', text)

        # Build YAML block
        op_lines = operation.split("\n")
        if len(op_lines) == 1:
            escaped = operation.replace("\\", "\\\\").replace('"', '\\"')
            yaml_block = f'"operation()": "{escaped}"\n'
        else:
            yaml_block = '"operation()": |\n'
            for line in op_lines:
                yaml_block += f"  {line}\n"

        if not text.endswith("\n"):
            text += "\n"
        text += yaml_block

        path.write_text(text)
        rel = path.relative_to(INST_DIR.parent.parent.parent.parent.parent)
        print(f"  Added: {name} -> {rel}")
        added += 1

    return added


def main():
    print("Step 1: Cleaning junk from existing operation() fields...")
    cleaned = clean_existing_operations()
    print(f"  Cleaned {cleaned} files\n")

    print("Step 2: Adding operation() to remaining instructions...")
    added = add_missing_operations()
    print(f"  Added {added} operations\n")

    print(f"Done: {cleaned} cleaned, {added} added")


if __name__ == "__main__":
    main()
