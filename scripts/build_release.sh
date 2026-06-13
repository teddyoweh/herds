#!/usr/bin/env bash
# Build the dashboard, bundle it into the package, and build the wheel.
# Produces dist/*.whl with the full UI baked in (pip install → herds host → UI).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "→ building dashboard (static export)…"
( cd web && NEXT_PUBLIC_HERDS_API="" pnpm build )

echo "→ bundling dashboard into package…"
rm -rf src/herds/web_dist
cp -R web/out src/herds/web_dist

echo "→ building wheel…"
rm -rf dist
uv build

echo "✓ done: $(ls dist/*.whl)"
echo "  install:  uv tool install --force dist/*.whl   (or  pip install dist/*.whl)"
