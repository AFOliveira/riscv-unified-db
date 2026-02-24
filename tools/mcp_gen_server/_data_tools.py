# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International

"""
Search and read tool functions for additional RISC-V data types:
parameters, exception codes, interrupt codes, profiles, profile releases,
profile families, and register files.

Each async handler takes (args, paths, load_yaml) where:
  - args: dict of tool arguments from the MCP client
  - paths: list of Path objects to iterate over (provided by the caller)
  - load_yaml: callable(Path) -> dict that loads and caches YAML files
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _extract_defined_by(data: dict) -> list[str]:
    """Extract extension names from a definedBy field (str, list, or dict with anyOf/allOf)."""
    defined = data.get("definedBy")
    if defined is None:
        return []
    if isinstance(defined, str):
        return [defined]
    if isinstance(defined, list):
        return [str(x) for x in defined]
    if isinstance(defined, dict):
        for k in ("anyOf", "allOf", "oneOf"):
            if k in defined and isinstance(defined[k], list):
                return [str(x) for x in defined[k]]
    return []


def _matches_term(term: str | None, p: Path, rel: str) -> bool:
    """Return True if term is None or matches the filename/path."""
    if not term:
        return True
    lower = term.lower()
    return lower in p.stem.lower() or lower in rel.lower()


def _schema_summary(schema: Any) -> Any:
    """Return a compact summary of a parameter schema."""
    if not isinstance(schema, dict):
        return schema
    # For simple schemas, return type + constraints
    result: dict[str, Any] = {}
    for key in ("type", "minimum", "maximum", "enum", "const", "default"):
        if key in schema:
            result[key] = schema[key]
    if "oneOf" in schema:
        result["oneOf"] = f"({len(schema['oneOf'])} variants)"
    if "allOf" in schema:
        result["allOf"] = f"({len(schema['allOf'])} constraints)"
    return result if result else schema


# ---------------------------------------------------------------------------
# 1. Parameters
# ---------------------------------------------------------------------------


async def search_params(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Search parameter YAMLs by term/name."""
    term = args.get("term")
    limit = int(args.get("limit") or 50)
    results: list[dict[str, Any]] = []

    for p in paths:
        rel = str(p.relative_to(REPO_ROOT))
        if not _matches_term(term, p, rel):
            continue
        try:
            data = load_yaml(p)
        except Exception:
            continue
        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "definedBy": _extract_defined_by(data),
            "schema": _schema_summary(data.get("schema")),
        }
        results.append(info)
        if len(results) >= limit:
            break

    return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# 2. Exception Codes
# ---------------------------------------------------------------------------


async def search_exception_codes(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Search exception code YAMLs by term/name/num."""
    term = args.get("term")
    num = args.get("num")
    limit = int(args.get("limit") or 50)
    results: list[dict[str, Any]] = []

    for p in paths:
        rel = str(p.relative_to(REPO_ROOT))
        if not _matches_term(term, p, rel):
            continue
        try:
            data = load_yaml(p)
        except Exception:
            continue
        # Filter by num if specified
        if num is not None and data.get("num") != int(num):
            continue
        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "num": data.get("num"),
            "display_name": data.get("display_name"),
            "definedBy": _extract_defined_by(data),
        }
        results.append(info)
        if len(results) >= limit:
            break

    return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# 3. Interrupt Codes
# ---------------------------------------------------------------------------


async def search_interrupt_codes(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Search interrupt code YAMLs by term/name/num."""
    term = args.get("term")
    num = args.get("num")
    limit = int(args.get("limit") or 50)
    results: list[dict[str, Any]] = []

    for p in paths:
        rel = str(p.relative_to(REPO_ROOT))
        if not _matches_term(term, p, rel):
            continue
        try:
            data = load_yaml(p)
        except Exception:
            continue
        if num is not None and data.get("num") != int(num):
            continue
        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "num": data.get("num"),
            "display_name": data.get("display_name"),
            "definedBy": _extract_defined_by(data),
        }
        results.append(info)
        if len(results) >= limit:
            break

    return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# 4. Profiles
# ---------------------------------------------------------------------------


async def search_profiles(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Search profile YAMLs by term/mode/base."""
    term = args.get("term")
    mode = args.get("mode")
    base = args.get("base")
    limit = int(args.get("limit") or 50)
    results: list[dict[str, Any]] = []

    for p in paths:
        rel = str(p.relative_to(REPO_ROOT))
        if not _matches_term(term, p, rel):
            continue
        try:
            data = load_yaml(p)
        except Exception:
            continue
        # Filter by mode (e.g. "S", "U", "M")
        if mode is not None and data.get("mode") != mode:
            continue
        # Filter by base (e.g. 32 or 64)
        if base is not None and data.get("base") != int(base):
            continue
        extensions = data.get("extensions")
        ext_count = 0
        if isinstance(extensions, dict):
            # Exclude keys starting with '$' (like $child_of, $parent_of)
            ext_count = sum(1 for k in extensions if not k.startswith("$"))
        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "mode": data.get("mode"),
            "base": data.get("base"),
            "extensions_count": ext_count,
        }
        results.append(info)
        if len(results) >= limit:
            break

    return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# 5. Profile Releases
# ---------------------------------------------------------------------------


async def search_profile_releases(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Search profile release YAMLs by term/state."""
    term = args.get("term")
    state = args.get("state")
    limit = int(args.get("limit") or 50)
    results: list[dict[str, Any]] = []

    for p in paths:
        rel = str(p.relative_to(REPO_ROOT))
        if not _matches_term(term, p, rel):
            continue
        try:
            data = load_yaml(p)
        except Exception:
            continue
        if state is not None and data.get("state") != state:
            continue
        profiles = data.get("profiles")
        profiles_count = len(profiles) if isinstance(profiles, list) else 0
        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "marketing_name": data.get("marketing_name"),
            "state": data.get("state"),
            "ratification_date": data.get("ratification_date"),
            "profiles_count": profiles_count,
        }
        results.append(info)
        if len(results) >= limit:
            break

    return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# 6. Profile Families
# ---------------------------------------------------------------------------


async def search_profile_families(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Search profile family YAMLs by term."""
    term = args.get("term")
    limit = int(args.get("limit") or 50)
    results: list[dict[str, Any]] = []

    for p in paths:
        rel = str(p.relative_to(REPO_ROOT))
        if not _matches_term(term, p, rel):
            continue
        try:
            data = load_yaml(p)
        except Exception:
            continue
        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "processor_kind": data.get("processor_kind"),
            "marketing_name": data.get("marketing_name"),
        }
        results.append(info)
        if len(results) >= limit:
            break

    return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# 7. Register Files — search
# ---------------------------------------------------------------------------


async def search_register_files(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Search register file YAMLs by term."""
    term = args.get("term")
    limit = int(args.get("limit") or 50)
    results: list[dict[str, Any]] = []

    for p in paths:
        rel = str(p.relative_to(REPO_ROOT))
        if not _matches_term(term, p, rel):
            continue
        try:
            data = load_yaml(p)
        except Exception:
            continue
        registers = data.get("registers")
        reg_count = len(registers) if isinstance(registers, list) else 0
        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "definedBy": _extract_defined_by(data),
            "register_class": data.get("register_class"),
            "register_length": data.get("register_length"),
            "register_count": reg_count,
        }
        results.append(info)
        if len(results) >= limit:
            break

    return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# 8. Register Files — read (full detail)
# ---------------------------------------------------------------------------


async def read_register_file(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Read a single register file by name, including all register details."""
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("'name' is required")

    for p in paths:
        try:
            data = load_yaml(p)
        except Exception:
            continue
        if data.get("name") != name:
            continue

        # Build detailed register list
        registers_raw = data.get("registers", [])
        registers: list[dict[str, Any]] = []
        if isinstance(registers_raw, list):
            for reg in registers_raw:
                if not isinstance(reg, dict):
                    continue
                registers.append(
                    {
                        "name": reg.get("name"),
                        "abi_mnemonics": reg.get("abi_mnemonics", []),
                        "caller_saved": reg.get("caller_saved"),
                        "callee_saved": reg.get("callee_saved"),
                        "roles": reg.get("roles", []),
                        "description": reg.get("description"),
                    }
                )

        return {
            "path": str(p.relative_to(REPO_ROOT)),
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "description": data.get("description"),
            "definedBy": _extract_defined_by(data),
            "register_class": data.get("register_class"),
            "register_length": data.get("register_length"),
            "register_count": len(registers),
            "registers": registers,
        }

    return {"path": None, "register_file": None}


# ---------------------------------------------------------------------------
# Tool definitions (MCP Tool schemas)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_params",
        "description": (
            "Search architecture parameter YAMLs (param/ directory). "
            "Use this to find configurable parameters like ARCH_ID_VALUE, "
            "ASID_WIDTH, CACHE_BLOCK_SIZE, etc. Parameters define "
            "implementation-specific constants and their valid ranges."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Substring to match in parameter filename or path",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "search_exception_codes",
        "description": (
            "Search exception code YAMLs (exception_code/ directory). "
            "Use this to find trap exception codes like Breakpoint, "
            "IllegalInstruction, LoadAccessFault, etc. Each code has a "
            "numeric value (num) and the extension that defines it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Substring to match in exception code filename or path",
                },
                "num": {
                    "type": "integer",
                    "description": "Filter by exact exception code number",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "search_interrupt_codes",
        "description": (
            "Search interrupt code YAMLs (interrupt_code/ directory). "
            "Use this to find interrupt codes like MachineTimer, "
            "MachineSoftware, SupervisorExternal, LocalCounterOverflow, etc. "
            "Each code has a numeric value (num) and the extension that defines it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Substring to match in interrupt code filename or path",
                },
                "num": {
                    "type": "integer",
                    "description": "Filter by exact interrupt code number",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "search_profiles",
        "description": (
            "Search RISC-V profile YAMLs (profile/ directory). "
            "Use this to find profiles like RVA20S64, RVA23U64, MP-S-64, etc. "
            "Profiles define sets of mandatory/optional extensions for a given "
            "privilege mode (S/U/M) and base ISA width (32/64)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Substring to match in profile filename or path",
                },
                "mode": {
                    "type": "string",
                    "description": "Filter by privilege mode: S, U, or M",
                    "enum": ["S", "U", "M"],
                },
                "base": {
                    "type": "integer",
                    "description": "Filter by base ISA width: 32 or 64",
                    "enum": [32, 64],
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "search_profile_releases",
        "description": (
            "Search profile release YAMLs (profile_release/ directory). "
            "Use this to find profile releases like RVA20, RVA22, RVA23, etc. "
            "A release groups profiles together under a ratification state "
            "(ratified or development) and date."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Substring to match in profile release filename or path",
                },
                "state": {
                    "type": "string",
                    "description": "Filter by ratification state: ratified or development",
                    "enum": ["ratified", "development"],
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "search_profile_families",
        "description": (
            "Search profile family YAMLs (profile_family/ directory). "
            "Use this to find profile families like RVA, RVB, RVI, Mock, etc. "
            "A family groups related profile releases and defines the "
            "processor kind (e.g. Application, Microcontroller)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Substring to match in profile family filename or path",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "search_register_files",
        "description": (
            "Search register file YAMLs (register_file/ directory). "
            "Use this to find register files like X (integer), F (floating-point), "
            "V (vector). Each register file defines the register class, length, "
            "and the list of individual registers with their ABI names and roles."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Substring to match in register file filename or path",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "read_register_file",
        "description": (
            "Read full details of a single register file by name (e.g. 'F', 'X', 'V'). "
            "Returns all register details including ABI mnemonics, caller/callee saved "
            "status, roles, and descriptions. Use search_register_files first to discover "
            "available register file names."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Exact register file name (e.g. 'F', 'X', 'V')",
                },
            },
            "required": ["name"],
        },
    },
]

# Map tool name -> (handler function, subdirectory under config root)
TOOL_HANDLERS: dict[str, tuple[Any, str]] = {
    "search_params": (search_params, "param"),
    "search_exception_codes": (search_exception_codes, "exception_code"),
    "search_interrupt_codes": (search_interrupt_codes, "interrupt_code"),
    "search_profiles": (search_profiles, "profile"),
    "search_profile_releases": (search_profile_releases, "profile_release"),
    "search_profile_families": (search_profile_families, "profile_family"),
    "search_register_files": (search_register_files, "register_file"),
    "read_register_file": (read_register_file, "register_file"),
}
