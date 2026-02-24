<!--
Copyright (c) Synopsys, Inc.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# RISC-V Unified Database MCP Server

Standalone MCP server for querying pre-generated YAML architecture data in `gen/`.

**Note:** Users must generate data first (e.g., `./do gen:resolved_arch`) before using this server.

## Features

The server provides organized access to:

- **Instructions**: Search and retrieve instruction definitions with advanced filtering
- **CSRs**: Query Control and Status Registers
- **Extensions**: Browse architecture extensions with optional instruction/CSR details
- **IDL Functions**: Search function documentation and find usages
- **Multi-Domain Search**: Search across instructions, CSRs, and extensions simultaneously
- **Parameters**: Search configurable architecture parameters
- **Exception/Interrupt Codes**: Lookup trap and interrupt code definitions
- **Profiles**: Search profile, profile release, and profile family definitions
- **Register Files**: Search and read register file definitions
- **Enriched Search**: Instruction and CSR search with encoding variables and field summaries
- **Config Manifest**: Full overview of the active CPU configuration
- **Extension Dependencies**: Resolve transitive dependency trees

### Advanced Search Capabilities

- **Regex Support**: Use regular expressions for powerful pattern matching
- **Fuzzy Matching**: Typo-tolerant searches with adjustable similarity thresholds
- **Field-Specific Search**: Target specific fields (e.g., assembly syntax, encoding patterns)
- **XLEN Filtering**: Filter by 32-bit or 64-bit architecture support
- **Combined Queries**: Search multiple domains at once with unified results

## Prerequisites

- Python 3.10+
- Virtual environment with `mcp[cli]` and `pyyaml` installed
- Pre-generated data in `gen/` directory

## Setup

1. Create venv and install dependencies:

   ```bash
   python3 -m venv .venv_mcp
   . .venv_mcp/bin/activate
   pip install "mcp[cli]" pyyaml
   ```

2. Generate data (if not already done):

   ```bash
   ./do gen:resolved_arch
   ```

3. Run the server:

   ```bash
   # From repo root (default config: rv64)
   . .venv_mcp/bin/activate && python3 tools/mcp_gen_server/server.py

   # With a specific CPU configuration
   RISCV_CPU_CONFIG=qc_iu python3 tools/mcp_gen_server/server.py
   ```

4. The server speaks MCP over stdio. Use an MCP-compatible client to connect.

## Configuration

Set `RISCV_CPU_CONFIG` to select the CPU configuration (default: `rv64`).
The server reads from `gen/resolved_spec/<config>/`.

## Available Tools

### Low-Level YAML Access

- **list_gen_yaml**: Lists all YAML files under gen/
- **read_gen_yaml**: Reads and parses a specific YAML file

### Instruction Tools

- **search_instructions**: Advanced search with regex, fuzzy matching, field-specific search, XLEN filtering
- **search_instructions_enriched**: Search with enriched results (access modes, encoding variables, data-independent timing)

### CSR Tools

- **search_csrs**: Advanced search with same capabilities as instructions
- **search_csrs_enriched**: Search with enriched results (register length, field summaries)

### Extension Tools

- **search_extensions**: List all or get specific extension details
- **extension_deps**: Resolve direct and transitive extension dependencies

### Multi-Domain Search

- **search_all**: Search across instructions, CSRs, and extensions simultaneously

### Function/IDL Tools

- **search_functions**: Search IDL function documentation
- **read_function_doc**: Get complete function documentation
- **find_function_usages**: Find where functions are used

### Data Tools

- **search_params**: Search architecture parameters (ARCH_ID_VALUE, ASID_WIDTH, etc.)
- **search_exception_codes**: Search synchronous exception codes
- **search_interrupt_codes**: Search asynchronous interrupt codes
- **search_profiles**: Search RISC-V profiles (RVA20S64, RVA23U64, etc.)
- **search_profile_releases**: Search profile releases with ratification state
- **search_profile_families**: Search profile families (RVA, RVB, etc.)
- **search_register_files**: Search register file definitions (X, F, V)
- **read_register_file**: Read full register file details by name

### Relational Tools

- **config_manifest**: Full overview of the active CPU configuration
- **extension_deps**: Resolve extension dependency tree

## Tool Summary

| Tool                           | Purpose                                        |
| ------------------------------ | ---------------------------------------------- |
| `list_gen_yaml`                | List all YAML files under gen/                 |
| `read_gen_yaml`                | Read specific YAML file                        |
| `search_instructions`          | Search instructions with filters               |
| `search_instructions_enriched` | Enriched instruction search                    |
| `search_csrs`                  | Search CSRs with filters                       |
| `search_csrs_enriched`         | Enriched CSR search                            |
| `search_extensions`            | List/query extensions from YAML                |
| `search_all`                   | Multi-domain search                            |
| `search_functions`             | Search IDL functions                           |
| `read_function_doc`            | Get function documentation                     |
| `find_function_usages`         | Find function usage in code                    |
| `search_params`                | Search architecture parameters                 |
| `search_exception_codes`       | Search exception codes                         |
| `search_interrupt_codes`       | Search interrupt codes                         |
| `search_profiles`              | Search profiles                                |
| `search_profile_releases`      | Search profile releases                        |
| `search_profile_families`      | Search profile families                        |
| `search_register_files`        | Search register files                          |
| `read_register_file`           | Read register file details                     |
| `config_manifest`              | Full config overview                           |
| `extension_deps`               | Extension dependency tree                      |
