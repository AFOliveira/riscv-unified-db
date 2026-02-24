#!/usr/bin/env python3

# Copyright (c) Synopsys, Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""CLI entry point for RISC-V ISA specialized agents.

Routes to one of three agents:
  explore    - Fast ISA lookups (Haiku)
  compliance - Custom extension compliance checking (Sonnet)
  review     - YAML spec file code review (Sonnet)

Each agent uses the RISC-V UDB MCP server for structured ISA data access.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    query,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_SERVER = REPO_ROOT / "tools" / "mcp_gen_server" / "server.py"


def mcp_server_config(config: str) -> dict:
    """Build MCP server configuration for the given CPU config."""
    return {
        "riscv": {
            "type": "stdio",
            "command": sys.executable,
            "args": [str(MCP_SERVER)],
            "env": {"RISCV_CPU_CONFIG": config},
        }
    }


async def run_one_shot(prompt: str, options) -> None:
    """Run a single prompt and stream the response."""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)


async def run_interactive(options) -> None:
    """Run an interactive REPL loop."""
    print("RISC-V ISA Agent (interactive mode). Type 'quit' to exit.\n")
    while True:
        try:
            prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not prompt or prompt.lower() in ("quit", "exit", "q"):
            break
        await run_one_shot(prompt, options)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="riscv-agent",
        description="Specialized RISC-V ISA agents powered by Claude",
    )
    parser.add_argument(
        "--config",
        default="rv64",
        help="CPU configuration name (default: rv64)",
    )
    sub = parser.add_subparsers(dest="agent", required=True)

    # --- explore ---
    p_explore = sub.add_parser(
        "explore",
        help="Fast ISA lookups and queries",
    )
    p_explore.add_argument("prompt", nargs="?", help="One-shot question")

    # --- compliance ---
    p_compliance = sub.add_parser(
        "compliance",
        help="Custom extension compliance checking",
    )
    p_compliance.add_argument("prompt", nargs="?", help="One-shot question")

    # --- review ---
    p_review = sub.add_parser(
        "review",
        help="YAML spec file code review",
    )
    p_review.add_argument("prompt", nargs="?", help="File path or one-shot question")

    args = parser.parse_args()

    # Import the agent module and build options
    if args.agent == "explore":
        from agents.explorer import build_options
    elif args.agent == "compliance":
        from agents.compliance import build_options
    elif args.agent == "review":
        from agents.reviewer import build_options
    else:
        parser.error(f"Unknown agent: {args.agent}")

    options = build_options(args.config)

    if args.prompt:
        asyncio.run(run_one_shot(args.prompt, options))
    else:
        asyncio.run(run_interactive(options))


if __name__ == "__main__":
    main()
