# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International

"""Enriched search functions and relational query tools for the MCP server."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Shared helpers (mirrored from server.py so this module is self-contained)
# ---------------------------------------------------------------------------


def _extract_defined_by(data: dict) -> list[str]:
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


def _extension_in_path(rel_parts: list[str]) -> str | None:
    for i, part in enumerate(rel_parts):
        if part == "inst" and i + 1 < len(rel_parts):
            return rel_parts[i + 1]
    return None


def _csr_extensions(data: dict) -> set[str]:
    exts: set[str] = set()
    top = data.get("definedBy")
    if isinstance(top, str):
        exts.add(top)
    elif isinstance(top, list):
        exts.update(str(x) for x in top)
    fields = data.get("fields")
    if isinstance(fields, dict):
        for fld in fields.values():
            if isinstance(fld, dict) and "definedBy" in fld:
                db = fld.get("definedBy")
                if isinstance(db, str):
                    exts.add(db)
                elif isinstance(db, list):
                    exts.update(str(x) for x in db)
    return exts


def _extract_requirements(req_data: Any) -> set[str]:
    """Recursively extract extension names from a requires/implies structure."""
    names: set[str] = set()
    if isinstance(req_data, dict):
        if "extension" in req_data:
            ext = req_data["extension"]
            if isinstance(ext, dict) and "name" in ext:
                names.add(ext["name"])
            elif isinstance(ext, str):
                names.add(ext)
        # Handle direct extension name reference (requires_entry can be a
        # plain extension name string wrapped in a dict with "name" key)
        if "name" in req_data and "extension" not in req_data:
            name_val = req_data.get("name")
            # Distinguish extension requirement dicts from other dicts by
            # checking that it looks like {name: <str>, version?: ...}
            if isinstance(name_val, str) and len(req_data) <= 2:
                names.add(name_val)
        for key in ("allOf", "anyOf", "oneOf"):
            if key in req_data and isinstance(req_data[key], list):
                for item in req_data[key]:
                    names |= _extract_requirements(item)
    elif isinstance(req_data, list):
        for item in req_data:
            names |= _extract_requirements(item)
    elif isinstance(req_data, str):
        # A bare extension name string
        names.add(req_data)
    return names


# ---------------------------------------------------------------------------
# 1. search_instructions_enriched
# ---------------------------------------------------------------------------


async def search_instructions_enriched(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Enhanced instruction search that also returns access, encoding.variables,
    and data_independent_timing."""
    term = args.get("term")
    keys = args.get("keys") or []
    extensions = args.get("extensions") or []
    limit = int(args.get("limit") or 50)

    if term is not None and not isinstance(term, str):
        raise ValueError("'term' must be a string if provided")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError("'keys' must be a list of strings")
    if not isinstance(extensions, list) or not all(isinstance(e, str) for e in extensions):
        raise ValueError("'extensions' must be a list of strings")

    ext_set = set(extensions)
    results: list[dict[str, Any]] = []
    count = 0
    gen_dir = REPO_ROOT / "gen"

    for p in paths:
        rel = p.relative_to(REPO_ROOT)
        rel_str = str(rel)

        if term:
            namepart = p.stem.lower()
            if term.lower() not in namepart and term.lower() not in rel_str.lower():
                continue

        try:
            data = load_yaml(p)
        except Exception:
            continue

        if keys and not all(k in data for k in keys):
            continue

        defined_by = _extract_defined_by(data)
        ext_from_path = _extension_in_path(
            rel.relative_to(gen_dir).parts if rel.is_relative_to(gen_dir) else rel.parts
        )

        if ext_set:
            present = set(defined_by)
            if ext_from_path:
                present.add(ext_from_path)
            if present.isdisjoint(ext_set):
                continue

        # Build encoding info
        encoding = None
        enc_raw = data.get("encoding")
        if isinstance(enc_raw, dict):
            variables = []
            for var in enc_raw.get("variables", []):
                if isinstance(var, dict):
                    variables.append({"name": var.get("name"), "location": var.get("location")})
            encoding = {
                "match": enc_raw.get("match"),
                "variables": variables,
            }

        info: dict[str, Any] = {
            "path": rel_str,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "assembly": data.get("assembly"),
            "encoding": encoding,
            "definedBy": defined_by,
            "extensionInPath": ext_from_path,
            "access": data.get("access"),
            "data_independent_timing": data.get("data_independent_timing"),
        }
        results.append(info)
        count += 1
        if count >= limit:
            break

    return {"count": count, "results": results}


# ---------------------------------------------------------------------------
# 2. search_csrs_enriched
# ---------------------------------------------------------------------------


async def search_csrs_enriched(
    args: dict[str, Any],
    paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Enhanced CSR search that also returns length and field summaries."""
    term = args.get("term")
    keys = args.get("keys") or []
    extensions = args.get("extensions") or []
    limit = int(args.get("limit") or 50)

    if term is not None and not isinstance(term, str):
        raise ValueError("'term' must be a string if provided")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError("'keys' must be a list of strings")
    if not isinstance(extensions, list) or not all(isinstance(e, str) for e in extensions):
        raise ValueError("'extensions' must be a list of strings")

    ext_set = set(extensions)
    results: list[dict[str, Any]] = []
    count = 0

    for p in paths:
        rel = str(p.relative_to(REPO_ROOT))

        if term:
            if term.lower() not in p.stem.lower() and term.lower() not in rel.lower():
                continue

        try:
            data = load_yaml(p)
        except Exception:
            continue

        if keys and not all(k in data for k in keys):
            continue

        csr_exts = _csr_extensions(data)
        if ext_set and csr_exts.isdisjoint(ext_set):
            continue

        # Summarise fields
        field_summaries: list[dict[str, Any]] = []
        fields_raw = data.get("fields")
        if isinstance(fields_raw, dict):
            for fname, fdata in fields_raw.items():
                if not isinstance(fdata, dict):
                    continue
                summary: dict[str, Any] = {"name": fname}
                if "location" in fdata:
                    summary["location"] = fdata["location"]
                else:
                    if "location_rv32" in fdata:
                        summary["location_rv32"] = fdata["location_rv32"]
                    if "location_rv64" in fdata:
                        summary["location_rv64"] = fdata["location_rv64"]
                # type can be a string or a code block (type())
                if "type" in fdata:
                    summary["type"] = fdata["type"]
                elif "type()" in fdata:
                    summary["type"] = "type()"
                field_summaries.append(summary)

        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "address": data.get("address"),
            "priv_mode": data.get("priv_mode"),
            "definedBy": list(csr_exts),
            "length": data.get("length"),
            "fields": field_summaries,
        }
        results.append(info)
        count += 1
        if count >= limit:
            break

    return {"count": count, "results": results}


# ---------------------------------------------------------------------------
# 3. config_manifest
# ---------------------------------------------------------------------------


async def config_manifest(
    args: dict[str, Any],
    config_name: str,
    path_iterators: dict[str, list[Path]],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Return a complete overview of a CPU configuration.

    path_iterators is a dict mapping data type names to their resolved paths
    (already using fallback-aware iteration from ConfigManager).
    """

    # Extensions
    ext_names: list[str] = []
    for p in path_iterators.get("ext", []):
        try:
            data = load_yaml(p)
        except Exception:
            continue
        name = data.get("name")
        if isinstance(name, str):
            ext_names.append(name)

    # Exception codes
    exception_codes: list[dict[str, Any]] = []
    for p in path_iterators.get("exception_code", []):
        try:
            data = load_yaml(p)
        except Exception:
            continue
        exception_codes.append({"name": data.get("name"), "num": data.get("num")})

    # Interrupt codes
    interrupt_codes: list[dict[str, Any]] = []
    for p in path_iterators.get("interrupt_code", []):
        try:
            data = load_yaml(p)
        except Exception:
            continue
        interrupt_codes.append({"name": data.get("name"), "num": data.get("num")})

    # Profiles
    profile_names: list[str] = []
    for p in path_iterators.get("profile", []):
        try:
            data = load_yaml(p)
        except Exception:
            continue
        name = data.get("name")
        if isinstance(name, str):
            profile_names.append(name)

    # Register files
    reg_file_names: list[str] = []
    for p in path_iterators.get("register_file", []):
        try:
            data = load_yaml(p)
        except Exception:
            continue
        name = data.get("name")
        if isinstance(name, str):
            reg_file_names.append(name)

    return {
        "config_name": config_name,
        "extensions": ext_names,
        "instruction_count": len(path_iterators.get("inst", [])),
        "csr_count": len(path_iterators.get("csr", [])),
        "param_count": len(path_iterators.get("param", [])),
        "exception_codes": exception_codes,
        "interrupt_codes": interrupt_codes,
        "profiles": profile_names,
        "register_files": reg_file_names,
    }


# ---------------------------------------------------------------------------
# 4. extension_deps
# ---------------------------------------------------------------------------


async def extension_deps(
    args: dict[str, Any],
    ext_paths: list[Path],
    load_yaml: Callable[[Path], dict],
) -> dict[str, Any]:
    """Walk an extension's requires/implies to find transitive dependencies."""
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("'name' is required")

    # Build a lookup: extension name -> loaded YAML data
    ext_by_name: dict[str, dict] = {}
    for p in ext_paths:
        try:
            data = load_yaml(p)
        except Exception:
            continue
        ename = data.get("name")
        if isinstance(ename, str):
            ext_by_name[ename] = data

    if name not in ext_by_name:
        return {
            "extension": name,
            "error": f"Extension '{name}' not found",
            "direct_deps": [],
            "transitive_deps": [],
            "all_deps_flat": [],
        }

    def _get_deps(ext_name: str) -> set[str]:
        """Get direct dependency names for an extension."""
        data = ext_by_name.get(ext_name)
        if data is None:
            return set()
        deps: set[str] = set()
        versions = data.get("versions")
        if isinstance(versions, list):
            for ver in versions:
                if not isinstance(ver, dict):
                    continue
                # Walk 'requires'
                req = ver.get("requires")
                if req is not None:
                    deps |= _extract_requirements(req)
                # Walk 'implies'
                imp = ver.get("implies")
                if imp is not None:
                    deps |= _extract_requirements(imp)
        return deps

    direct_deps = _get_deps(name)

    # BFS for transitive deps
    visited: set[str] = set()
    queue = list(direct_deps)
    transitive: set[str] = set()

    while queue:
        current = queue.pop(0)
        if current in visited or current == name:
            continue
        visited.add(current)
        if current not in direct_deps:
            transitive.add(current)
        child_deps = _get_deps(current)
        for dep in child_deps:
            if dep not in visited and dep != name:
                queue.append(dep)
                if dep not in direct_deps:
                    transitive.add(dep)

    all_flat = sorted(direct_deps | transitive)

    return {
        "extension": name,
        "direct_deps": sorted(direct_deps),
        "transitive_deps": sorted(transitive),
        "all_deps_flat": all_flat,
    }


# ---------------------------------------------------------------------------
# 5. MCP Tool definitions
# ---------------------------------------------------------------------------

TOOL_SEARCH_INSTRUCTIONS = {
    "name": "search_instructions",
    "description": (
        "Search instruction YAMLs by filename and keys; optionally filter by "
        "defining extensions. Returns enriched results including access modes, "
        "encoding variables, and data-independent timing."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "term": {
                "type": "string",
                "description": "substring to match in filename/path",
            },
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "top-level YAML keys that must exist",
            },
            "extensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "extension symbols to match (definedBy or path)",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "default": 50,
            },
        },
    },
}

TOOL_SEARCH_CSRS = {
    "name": "search_csrs",
    "description": (
        "Search CSR YAMLs by name/path, filter by top-level keys and extensions. "
        "Returns enriched results including register length and field summaries."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "term": {"type": "string"},
            "keys": {"type": "array", "items": {"type": "string"}},
            "extensions": {"type": "array", "items": {"type": "string"}},
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "default": 50,
            },
        },
    },
}

TOOL_CONFIG_MANIFEST = {
    "name": "config_manifest",
    "description": (
        "Get a complete overview of the active CPU configuration including all "
        "extensions, instruction/CSR counts, exception codes, and profiles. "
        "Call this first when exploring a new config."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
    },
}

TOOL_EXTENSION_DEPS = {
    "name": "extension_deps",
    "description": (
        "Resolve the dependency tree for a RISC-V extension. "
        "Returns direct and transitive dependencies."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Extension name to resolve dependencies for",
            },
        },
        "required": ["name"],
    },
}
