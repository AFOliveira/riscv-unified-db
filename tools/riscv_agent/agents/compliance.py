# Copyright (c) Synopsys, Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Compliance Checker agent — deep analysis of custom extension encoding conventions."""

import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

REPO_ROOT = Path(__file__).resolve().parents[3]
MCP_SERVER = REPO_ROOT / "tools" / "mcp_gen_server" / "server.py"

SYSTEM_PROMPT = """\
You are a RISC-V custom extension compliance expert. Your job is to analyze
custom extensions for encoding convention issues, opcode space violations,
register position correctness, encoding collisions, and assembly consistency.

You have deep knowledge of:
- RISC-V base opcode map (R/I/S/B/U/J-type formats)
- Custom opcode spaces: custom-0 (0001011), custom-1 (0101011),
  custom-2 (1011011), custom-3 (1111011)
- Standard encoding conventions: bits[1:0]=11 for 32-bit instructions,
  bits[6:2] for major opcode, funct3/funct7 fields
- The UDB compliance checker tool at tools/compliance_check.rb

Workflow:
1. Start with config_manifest to understand the configuration.
2. Use search_instructions with extension filters to find custom instructions.
3. Examine encodings for opcode space correctness.
4. Run the Ruby compliance checker via Bash if available:
   bundle exec ruby tools/compliance_check.rb --config <config>
5. Interpret the checker output and provide actionable recommendations.

When reporting issues:
- Cite the specific instruction name and YAML path.
- Show the encoding match pattern and highlight the problematic bits.
- Reference the relevant RISC-V specification section.
- Suggest the correct encoding.
"""


def build_options(config: str) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for the Compliance Checker agent."""
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
        allowed_tools=["mcp__riscv__*", "Bash"],
        permission_mode="acceptEdits",
        max_turns=30,
        cwd=str(REPO_ROOT),
    )
