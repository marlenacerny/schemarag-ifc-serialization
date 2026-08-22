"""Schema serialization: Algorithm 1 (grouping) and Algorithm 2 (SCHEMA/WALK).

Given the localized path groups from :mod:`context_graph`, this module walks the target
instances, aggregates their values (strings -> deduplicated list; numerics ->
{min, median, max}), applies property-set grouping by Name, and flattens each summary
into JSONPath expressions. Output matches the listings in Appendix A / B.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Sequence, Tuple

import ifcopenshell

from context_graph import ContextGraph

# Housekeeping / geometric attributes with no descriptive semantics.
SKIP_ATTRS = {"id", "type", "GlobalId", "OwnerHistory", "ObjectPlacement",
              "Representation", "RepresentationMaps", "Representations"}

MAX_WALK_DEPTH = 6          # guard against pathological schemas
MAX_VALUES_PER_ATTR = 25    # truncate very long value lists


# --------------------------------------------------------------------------- #
# Algorithm 2: recursive attribute walk (SCHEMA / WALK)
# --------------------------------------------------------------------------- #
def _wrapped(v) -> bool:
    return isinstance(v, ifcopenshell.entity_instance) and hasattr(v, "wrappedValue")


def _atomic(v) -> bool:
    return _wrapped(v) or not isinstance(v, ifcopenshell.entity_instance)


def _unwrap(v):
    return v.wrappedValue if _wrapped(v) else v


def _each(v):
    if isinstance(v, (list, tuple)):
        yield from v
    else:
        yield v


def _walk(inst, path: Tuple[str, ...], sigma: Dict[Tuple[str, ...], List[Any]],
          visited: frozenset, depth: int) -> None:
    if depth >= MAX_WALK_DEPTH:
        return
    for attr, value in inst.get_info(recursive=False).items():
        if attr in SKIP_ATTRS or value is None:  # null-attribute handling
            continue
        key = path + (attr,)
        for v in _each(value):
            if v is None:
                continue
            if _atomic(v):
                sigma.setdefault(key, []).append(_unwrap(v))
            elif v.id() not in visited:  # cycle / duplicate-path handling
                _walk(v, key, sigma, visited | {v.id()}, depth + 1)


def _schema_for_class(instances) -> Dict[Tuple[str, ...], List[Any]]:
    sigma: Dict[Tuple[str, ...], List[Any]] = {}
    for inst in instances:
        _walk(inst, tuple(), sigma, frozenset({inst.id()}), 0)
    return sigma


# --------------------------------------------------------------------------- #
# Value aggregation + serialization (Section 3.2.2, matches Appendix A)
# --------------------------------------------------------------------------- #
def _aggregate(values: List[Any]) -> Any:
    """Numeric attrs -> {min, median, max}; otherwise a deduplicated string list."""
    numeric = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if values and len(numeric) == len(values):
        return {"min": min(numeric), "median": round(statistics.median(numeric), 2), "max": max(numeric)}
    uniq = sorted({str(v) for v in values})
    return uniq[:MAX_VALUES_PER_ATTR] + (["..."] if len(uniq) > MAX_VALUES_PER_ATTR else [])


def _nest(sigma: Dict[Tuple[str, ...], List[Any]]) -> Dict[str, Any]:
    root: Dict[str, Any] = {}
    for path, values in sigma.items():
        node = root
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = _aggregate(values)
    return root


def _wrap_property(agg: Any) -> Any:
    """Numeric props stay bare {min,median,max}; others get a 'values' key (Listing 2)."""
    return agg if isinstance(agg, dict) else {"values": agg}


def _propertyset_schema(instances) -> Dict[str, Any]:
    """Property-set grouping by Name, rendered as HasPropertySets.items[i] (Listing 2)."""
    by_name: Dict[str, Dict[str, List[Any]]] = {}
    order: List[str] = []
    for pset in sorted(instances, key=lambda p: (getattr(p, "Name", None) or "", p.id())):
        name = getattr(pset, "Name", None) or "<unnamed>"
        if name not in by_name:
            by_name[name] = {}
            order.append(name)
        for prop in getattr(pset, "HasProperties", None) or []:
            pname = getattr(prop, "Name", None)
            nominal = getattr(prop, "NominalValue", None)
            if pname is None or nominal is None:
                continue
            by_name[name].setdefault(pname, []).append(_unwrap(nominal))

    items = [
        {"class": "IfcPropertySet", "name": name, "item_index": i,
         "HasProperties": {p: _wrap_property(_aggregate(v)) for p, v in by_name[name].items()}}
        for i, name in enumerate(order)
    ]
    return {"HasPropertySets": {"class": "IfcPropertySet", "items": items}}


def _flatten_paths(node: Any, prefix: str = "$.schema") -> List[str]:
    """Emit a JSONPath only at value-bearing leaves (lists / {min,median,max})."""
    paths: List[str] = []
    if isinstance(node, dict):
        if set(node.keys()) == {"min", "median", "max"}:
            paths.append(prefix)
        else:
            for key, value in node.items():
                paths.extend(_flatten_paths(value, f"{prefix}.{key}"))
    elif isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node):  # items[] array
            for i, item in enumerate(node):
                paths.extend(_flatten_paths(item, f"{prefix}[{i}]"))
        else:
            paths.append(prefix)
    return paths  # scalar metadata (class/name/item_index) is not emitted


def _serialize_group(seed_class: str, group: Dict[str, Any]) -> Dict[str, Any]:
    if group["target_class"] == "IfcPropertySet":
        schema = _propertyset_schema(group["instances"])
    else:
        schema = {group["target_class"]: _nest(_schema_for_class(group["instances"]))}
    return {
        "seed": seed_class,
        "source_path": [list(step) for step in group["chain"]],
        "hop": group["hop"],
        "target_class": group["target_class"],
        "schema": schema,
        "paths": _flatten_paths(schema),
    }


def extract(model, seeds: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Context Extraction for one model: seed class -> list of path-group summaries."""
    graph = ContextGraph(model, seeds)
    return {seed: [_serialize_group(seed, g) for g in graph.path_groups(seed)] for seed in seeds}
