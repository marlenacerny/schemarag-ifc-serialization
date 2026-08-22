"""Context graph: parsing, pruning, and two-hop localized traversal (Section 3.2.1).

Builds a pruned relationship graph over one IFC model as directed
``related_object -> relating_end`` edges, then forms, per seed instance, the localized
two-hop candidate pool (Algorithm 1, lines 3-6). Only ``IfcRelDefines*`` /
``IfcRelAssociates*`` / ``IfcRelAssigns*`` relationships are kept; inverse traversal is
not applied; edges to other seed classes are excluded.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

import ifcopenshell

# Relationship families that describe semantics (Section 3.2.1, "Pruning").
KEPT_RELATION_PREFIXES: Tuple[str, ...] = ("IfcRelDefines", "IfcRelAssociates", "IfcRelAssigns")

# One directed step of a traversal chain: (subject class, relation, object class).
Triple = Tuple[str, str, str]


def _relating_end(rel):
    """First non-null 'Relating*' attribute of an IfcRel* relationship, or None."""
    for key, value in rel.get_info(recursive=False).items():
        if key.startswith("Relating") and value is not None:
            return value
    return None


class ContextGraph:
    """Pruned relationship graph over one IFC model (related -> relating edges)."""

    def __init__(self, model, seeds: Sequence[str]):
        self.model = model
        self.seed_classes = tuple(seeds)
        self._index: Dict[int, List[Tuple[str, Any]]] = {}
        for rel in model.by_type("IfcRelationship"):
            if not rel.is_a().startswith(KEPT_RELATION_PREFIXES):
                continue  # pruning: drop spatial/topological/geometric relations
            relating = _relating_end(rel)
            if relating is None:
                continue
            for obj in rel.get_info(recursive=False).get("RelatedObjects") or []:
                if obj is not None:  # directed edge, no inverse traversal
                    self._index.setdefault(obj.id(), []).append((rel.is_a(), relating))

    def _foreign_seed(self, inst, current: str) -> bool:
        return any(o != current and inst.is_a(o) for o in self.seed_classes)

    def path_groups(self, seed_class: str) -> List[Dict[str, Any]]:
        """One group per distinct traversal chain (candidate pool Q, Algorithm 1)."""
        groups: Dict[Tuple[Triple, ...], Dict[str, Any]] = {}
        seen: Dict[Tuple[Triple, ...], set] = {}

        def add(chain, target, hop):
            g = groups.get(chain)
            if g is None:
                g = {"chain": chain, "target_class": chain[-1][2], "hop": hop, "instances": []}
                groups[chain] = g
                seen[chain] = set()
            if target.id() not in seen[chain]:
                seen[chain].add(target.id())
                g["instances"].append(target)

        for seed in self.model.by_type(seed_class):
            sid, scls = seed.id(), seed.is_a()
            for rel1, t1 in self._index.get(sid, []):
                if t1.id() == sid or self._foreign_seed(t1, seed_class):
                    continue
                chain1 = ((scls, rel1, t1.is_a()),)
                add(chain1, t1, 1)
                for rel2, t2 in self._index.get(t1.id(), []):
                    if t2.id() == sid or self._foreign_seed(t2, seed_class):
                        continue  # cycle guard + foreign-seed exclusion
                    add(chain1 + ((t1.is_a(), rel2, t2.is_a()),), t2, 2)

        return sorted(groups.values(), key=lambda g: (g["hop"], str(g["chain"])))
