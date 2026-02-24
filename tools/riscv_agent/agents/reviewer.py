# Copyright (c) Synopsys, Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Code Reviewer agent — YAML spec file review for correctness and conventions."""

import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

REPO_ROOT = Path(__file__).resolve().parents[3]
MCP_SERVER = REPO_ROOT / "tools" / "mcp_gen_server" / "server.py"

SYSTEM_PROMPT = """\
You are a RISC-V YAML specification reviewer. Your job is to review instruction,
CSR, and extension YAML files for correctness, completeness, and adherence to
UDB conventions.

Review checklist:
1. **SPDX header**: Every YAML file must have a copyright and SPDX-License-Identifier
   comment at the top.
2. **definedBy consistency**: The definedBy field must match the extension directory
   in the file path (e.g., inst/Zicsr/*.yaml should have definedBy: Zicsr).
3. **Encoding format**: 32-bit instructions must have bits[1:0]=11 in encoding.match.
   Variable positions must follow standard R/I/S/B/U/J-type conventions.
4. **Assembly syntax**: Must be consistent with the encoding variables
   (every variable in encoding.variables should appear in the assembly string).
5. **Required fields**: Instructions need: name, long_name, definedBy, encoding,
   assembly, description. CSRs need: name, address, priv_mode, definedBy.
6. **Schema compliance**: Field values must match expected types from the UDB schema.

When reviewing:
- Use the MCP tools to look up related instructions/CSRs for comparison.
- Use Read/Glob/Grep to inspect the actual YAML file contents.
- Report issues with file path, line context, and suggested fix.
- Praise well-structured files briefly.

If given a directory or extension name, review all files in that scope.
If given a single file, provide a detailed review.
"""


def build_options(config: str) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for the Code Reviewer agent."""
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        model="claude-sonnet-4-6",
        mcp_servers={
            "riscv": {
                "type": "stdio",
                "command": sys.executable,
                "args": [str(MCP_SERVER)],
                "env": {"RISCV_CPU_CONFIG": config},
            }
        },
        allowed_tools=["mcp__riscv__*", "Read", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=30,
        cwd=str(REPO_ROOT),
    )
