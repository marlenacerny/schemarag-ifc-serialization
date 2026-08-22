# SchemaRAG-IFC: Context Extraction Module

Reference implementation of the **Context Extraction** stage (Section 3.2) from:

> M. A. Cerny and J. Schneider, "SchemaRAG-IFC: Context-Aware Semantic Normalization in Heterogeneous BIM Data," *Preprint submitted to Elsevier*, 2026.

This module implements Algorithm 1 (Seed-Centric IFC Schema Serialization) and Algorithm 2 (recursive attribute walk), producing compact schema-level JSON summaries suitable for downstream LLM-based retrieval and normalization.

## Overview

Given an IFC file and one or more seed entity classes, the pipeline:

1. **Parses** class-level relationships via `ifcopenshell`
2. **Prunes** to descriptive relations (`IfcRelDefines*`, `IfcRelAssociates*`, `IfcRelAssigns*`)
3. **Traverses** a two-hop localized graph per seed class
4. **Serializes** reachable classes into hierarchical schema summaries with JSONPath-style attribute paths

## Usage

```bash
python run.py path/to/model.ifc IfcFlowSegment
```

Multiple seeds:

```bash
python run.py path/to/model.ifc IfcFlowSegment IfcFlowFitting
```

Output is JSON to stdout. Redirect to save:

```bash
python run.py path/to/model.ifc IfcFlowSegment > output.json
```

## Requirements

```
pip install -r requirements.txt
```

Requires Python ≥ 3.9 and `ifcopenshell ≥ 0.7.0`.

## Project Structure

```
├── run.py                  # CLI entry point
├── src/
│   ├── context_graph.py    # Graph parsing, pruning, two-hop traversal (Section 3.2.1)
│   └── serialization.py    # Schema serialization and path flattening (Section 3.2.2)
├── requirements.txt
└── README.md
```

## Output Format

Each seed class produces a list of path-group summaries. Each summary contains:

- `source_path` — traversal chain as list of `(SubjectClass, RelationType, ObjectClass)` triples
- `schema` — hierarchical attribute summary with aggregated values
- `paths` — flattened JSONPath expressions for LLM consumption

String attributes are deduplicated into value lists; numeric attributes are summarized as `{min, median, max}`. Property sets are grouped by their `Name` attribute.

## Citation

```bibtex
@article{cerny2026schemarag,
  title={SchemaRAG-IFC: Context-Aware Semantic Normalization in Heterogeneous BIM Data},
  author={Cerny, Marlena A. and Schneider, Johannes},
  journal={Preprint submitted to Elsevier},
  year={2026}
}
```

## License

See repository license file.
