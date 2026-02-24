# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International

"""MCP tool descriptions optimized for AI agent consumption.

Each description explains WHEN and WHY to use the tool, not just what it does.
Import TOOL_DESCRIPTIONS and use as: Tool(description=TOOL_DESCRIPTIONS["tool_name"], ...)
"""

TOOL_DESCRIPTIONS = {
    # -- Config management --------------------------------------------------
    "list_configs": (
        "Lists all available CPU configurations (both generated and "
        "available-to-generate). Use this to discover what hardware targets "
        "exist before switching configs. Returns each config's name, whether "
        "its ISA data has been generated, and whether it is currently active."
    ),
    "get_config": (
        "Returns the currently active CPU configuration name, its generated "
        "data path, and cache status. Call this at the start of a session to "
        "understand which hardware target you are querying. All other tools "
        "operate against the active config."
    ),
    "switch_config": (
        "Switches the active CPU configuration. All subsequent queries will "
        "use the new config's generated ISA data. Use when you need to "
        "explore a different hardware target (e.g., moving from rv64 to "
        "rv32 or a custom SoC config). The config must already be generated "
        "or you must call generate_config first."
    ),
    "generate_config": (
        "Generates resolved ISA data for a CPU configuration that hasn't "
        "been generated yet. Runs the Ruby resolver and takes a few minutes. "
        "Only needed if list_configs shows a config as not yet generated. "
        "Pass force=true to regenerate an existing config."
    ),
    # -- Data browsing ------------------------------------------------------
    "list_gen_yaml": (
        "Lists raw YAML file paths under the active config's generated data "
        "directory. This is a low-level tool -- prefer the typed search "
        "tools (search_instructions, search_csrs, etc.) for structured "
        "results. Use this only when you need to browse the file tree or "
        "find files that don't fit other tool categories."
    ),
    "read_gen_yaml": (
        "Reads and parses a specific YAML file by its repo-relative path, "
        "returning the full contents as JSON. Use when you need complete raw "
        "data for a specific file -- typically after finding it via a search "
        "tool. Accepts paths like gen/resolved_spec/rv64/inst/I/add.yaml."
    ),
    # -- Instruction tools --------------------------------------------------
    "search_instructions": (
        "Searches RISC-V instructions by name, extension, or required YAML "
        "keys. Returns encoding, assembly syntax, and extension info for "
        "each match. Use when you need to find instructions, understand "
        "their encodings, or list all instructions provided by an extension. "
        "Filter by extension names to narrow results."
    ),
    # -- CSR tools ----------------------------------------------------------
    "search_csrs": (
        "Searches Control and Status Registers by name or extension. "
        "Returns address, privilege mode, field layouts, and access types. "
        "Essential for firmware and driver development -- CSRs are how "
        "software configures and monitors hardware. Filter by extension "
        "names to find CSRs introduced by a specific ISA feature."
    ),
    # -- Extension tools ----------------------------------------------------
    "list_extensions": (
        "Lists all RISC-V extensions available in the active config with "
        "their names, long names, and YAML paths. Use to get an overview of "
        "what ISA features the CPU supports. For details on a specific "
        "extension, follow up with read_extension or extension_summary."
    ),
    "read_extension": (
        "Reads complete details of a specific extension by name, including "
        "version history, dependencies, and description. Use when you need "
        "the full metadata for one extension (not its instructions/CSRs -- "
        "use extension_summary for that)."
    ),
    "extension_summary": (
        "Gets an extension's instructions and CSRs in one call. Use when "
        "you need to understand everything an extension provides -- its "
        "metadata plus the lists of instructions and CSRs it defines. More "
        "efficient than calling search_instructions and search_csrs "
        "separately with an extension filter."
    ),
    "extension_deps": (
        "Resolves the full dependency tree for a named extension, showing "
        "all transitive requirements. Use when you need to know what other "
        "extensions must be present for a given extension to work, or to "
        "verify that a config satisfies all dependencies."
    ),
    # -- Parameter tools ----------------------------------------------------
    "search_params": (
        "Searches implementation parameters (e.g., XLEN, VLEN, page sizes, "
        "cache line sizes). Parameters define the configurable aspects of a "
        "RISC-V implementation -- what is fixed vs. tunable. Essential for "
        "understanding hardware capabilities and writing portable code."
    ),
    # -- Exception / Interrupt tools ----------------------------------------
    "search_exception_codes": (
        "Searches synchronous exception (trap) codes. Returns code numbers "
        "and descriptive names. Use when building trap handlers, debugging "
        "exception behavior, or mapping mcause values to exception types."
    ),
    "search_interrupt_codes": (
        "Searches asynchronous interrupt codes. Returns code numbers and "
        "descriptive names. Use when building interrupt handlers or "
        "understanding which interrupt sources the platform supports."
    ),
    # -- Profile tools ------------------------------------------------------
    "search_profiles": (
        "Searches RISC-V profiles (e.g., RVA22U64, RVA23S64). Profiles "
        "define standard sets of mandatory and optional extensions for "
        "software compatibility. Use when checking whether a config meets "
        "compliance requirements for a target profile."
    ),
    "search_profile_releases": (
        "Searches profile releases (e.g., RVA20, RVA22). A release groups "
        "related profiles and carries ratification status. Use to find "
        "which profile generation applies or to check ratification dates."
    ),
    "search_profile_families": (
        "Searches profile families (e.g., RVA for Application processors, "
        "RVI for base). Families are the top-level grouping for profiles. "
        "Use to discover which profile families exist."
    ),
    # -- Register file tools ------------------------------------------------
    "search_register_files": (
        "Searches register file definitions (integer x0-x31, "
        "floating-point f0-f31, vector v0-v31). Returns register names, "
        "ABI mnemonics, and calling convention info. Use for understanding "
        "the register architecture of the active config."
    ),
    "read_register_file": (
        "Reads complete register file details by name, including every "
        "register, its ABI name, role description, and whether it is "
        "caller-saved or callee-saved. Use for detailed calling-convention "
        "reference or register allocation work."
    ),
    # -- Relational tools ---------------------------------------------------
    "config_manifest": (
        "Returns a complete overview of the active CPU configuration: all "
        "extensions with versions, instruction/CSR/parameter counts, "
        "exception codes, interrupt codes, and profile compliance. CALL "
        "THIS FIRST when starting work on a new config -- it gives you the "
        "full picture in one request and helps you decide what to explore."
    ),
    # -- Function / IDL tools -----------------------------------------------
    "list_functions": (
        "Lists all IDL (Instruction Description Language) function names "
        "from generated documentation. Use to discover what helper "
        "functions exist in the ISA formal model."
    ),
    "read_function_doc": (
        "Reads the full documentation for a specific IDL function by name. "
        "Returns the function signature, description, and behavioral "
        "specification. Use after finding a function name via "
        "list_functions or search_functions."
    ),
    "search_functions": (
        "Searches IDL function documentation by a text term, matching "
        "against both function names and body text. Use when you know a "
        "concept but not the exact function name."
    ),
    "find_function_usages": (
        "Finds instructions whose operation() or sail() code calls a "
        "specific IDL function. Use to understand which instructions "
        "depend on a given function, or to trace the impact of a function "
        "change across the ISA."
    ),
    # -- Stats --------------------------------------------------------------
    "server_stats": (
        "Returns server statistics: counts of instructions, CSRs, and "
        "extensions for the active config, plus cache utilization info. "
        "Use for a quick health check or to gauge the size of the dataset."
    ),
}
