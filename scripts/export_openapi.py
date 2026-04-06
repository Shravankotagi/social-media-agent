"""
scripts/export_openapi.py — Exports the OpenAPI 3.0 spec to openapi.json.

Usage:
    python scripts/export_openapi.py

Output: docs/openapi.json
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
from app.main import app

output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "openapi.json")
os.makedirs(os.path.dirname(output_path), exist_ok=True)

spec = app.openapi()
with open(output_path, "w") as f:
    json.dump(spec, f, indent=2)

print(f"✅ OpenAPI spec exported to {output_path}")
print(f"   Endpoints: {len(spec['paths'])} paths")
print(f"   Schemas:   {len(spec.get('components', {}).get('schemas', {}))} models")
