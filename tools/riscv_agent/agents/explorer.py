# Copyright (c) Synopsys, Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""ISA Explorer agent — fast lookups using Haiku."""

import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

REPO_ROOT = Path(__file__).resolve().parents[3]
MCP_SERVER = REPO_ROOT / "tools" / "mcp_gen_server" / "server.py"

SYSTEM_PROMPT = """\
You are a RISC-V ISA expert assistant specializing in fast, accurate lookups.

Your job is to answer questions about RISC-V instructions, CSRs, extensions,
parameters, profiles, and register files using the MCP tools available to you.

Guidelines:
- Give concise, structured answers.
- Always cite the extension name and version when referencing ISA features.
- For encodings, use standard bit notation (e.g., bits[6:0] = 0110011).
- When listing instructions, include the assembly syntax and encoding match pattern.
- Use config_manifest as your first call when exploring a new configuration.
- Prefer typed search tools (search_instructions, search_csrs, etc.) over raw
  YAML browsing.
"""


def build_options(config: str) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for the ISA Explorer agent."""
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        model="claude-haiku-4-5-20251001",
        mcp_servers={
            "riscv": {
                "type": "stdio",
                "command": sys.executable,
                "args": [str(MCP_SERVER)],
                "env": {"RISCV_CPU_CONFIG": config},
            }
        },
        allowed_tools=["mcp__riscv__*"],
        permission_mode="acceptEdits",
        max_turns=30,
    )
