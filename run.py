#!/usr/bin/env python3
"""Run the SchemaRAG-IFC schema serialization on your own IFC file.

Usage:
    python run.py path/to/model.ifc SEED_CLASS [SEED_CLASS ...]

Example:
    python run.py path/to/model.ifc IfcFlowSegment
    python run.py path/to/model.ifc IfcFlowSegment IfcFlowFitting

Prints one JSON object {seed: [summaries...]} to stdout; redirect to save.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import ifcopenshell
from serialization import extract


def main() -> int:
    parser = argparse.ArgumentParser(description="SchemaRAG-IFC schema serialization")
    parser.add_argument("ifc_path", help="path to an .ifc file")
    parser.add_argument("seeds", nargs="+", metavar="SEED_CLASS",
                        help="one or more IFC seed entity classes to serialize")
    args = parser.parse_args()

    model = ifcopenshell.open(args.ifc_path)
    result = extract(model, seeds=args.seeds)
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
