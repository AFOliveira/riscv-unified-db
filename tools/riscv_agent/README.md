<!--
Copyright (c) Synopsys, Inc.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# RISC-V ISA Agents

Three specialized agents built on the Claude Agent SDK, each backed by the
RISC-V UDB MCP server for structured ISA data access.

## Prerequisites

- Python 3.10+
- Claude Agent SDK: `pip install claude-agent-sdk`
- MCP server dependencies: `pip install "mcp[cli]" pyyaml`
- Pre-generated ISA data in `gen/` (run `./do gen:resolved_arch`)

## Agents

### ISA Explorer (`explore`)

Fast lookups for instructions, CSRs, extensions, parameters, and profiles.
Uses Haiku for speed and low cost.

```bash
# One-shot query
python tools/riscv_agent/agent.py explore "What instructions does Zicsr add?"

# With a specific config
python tools/riscv_agent/agent.py --config qc_iu explore "List all custom instructions"

# Interactive mode
python tools/riscv_agent/agent.py explore
```

### Compliance Checker (`compliance`)

Analyzes custom extensions for RISC-V encoding convention issues: opcode space
violations, register positions, encoding collisions, assembly consistency.
Uses Sonnet for deep reasoning. Has Bash access to run the Ruby compliance
checker.

```bash
# One-shot analysis
python tools/riscv_agent/agent.py --config qc_iu compliance "Check Xqci opcode space"

# Interactive mode
python tools/riscv_agent/agent.py --config qc_iu compliance
```

### Code Reviewer (`review`)

Reviews YAML spec files for correctness, completeness, and convention adherence:
definedBy consistency, encoding format, SPDX headers, schema compliance.
Uses Sonnet with Read/Glob/Grep access to inspect files.

```bash
# Review a specific file
python tools/riscv_agent/agent.py review "Review spec/custom/isa/qc_iu/inst/Xqcilo/qc.lb.yaml"

# Review all custom specs for a config
python tools/riscv_agent/agent.py --config qc_iu review "Review all custom instruction specs"

# Interactive mode
python tools/riscv_agent/agent.py review
```

## Architecture

```
tools/riscv_agent/
├── agent.py              # CLI entry point + shared infra
├── agents/
│   ├── explorer.py       # ISA Explorer (Haiku + MCP tools)
│   ├── compliance.py     # Compliance Checker (Sonnet + MCP + Bash)
│   └── reviewer.py       # Code Reviewer (Sonnet + MCP + Read/Glob/Grep)
└── README.md
```

Each agent module exports:
- `SYSTEM_PROMPT` — the agent's specialized system prompt
- `build_options(config)` — returns `ClaudeAgentOptions` with appropriate model,
  tools, and MCP server configuration

The CLI dispatcher (`agent.py`) handles argument parsing, agent routing, and
provides both one-shot and interactive execution modes.
