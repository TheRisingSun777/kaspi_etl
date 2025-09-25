# Analysis Bundle Instructions

Use `scripts/create_analysis_bundle.sh` to build a trimmed ZIP of the project for
external review (e.g., ChatGPT code analysis). The script creates
`kaspi_etl_analysis_bundle.zip` in the repo root and ensures the archive stays
under the 450 MB file-size limit.

## How to build the bundle

```bash
./scripts/create_analysis_bundle.sh
```

If the archive already exists, the script replaces it. A warning is emitted if
the bundle exceeds the size limit.

## What’s inside the ZIP

- Core applications and ETL scripts (`apps/kaspi_offers_dashboard` source,
  `scripts/`, `services/`, `utils/`)
- Documentation (`docs/`, including `docs/ops/kaspi` tooling docs and scripts)
- Configuration and metadata files (`requirements.txt`, project guides, prompts)

## Key exclusions to keep the bundle lean

- Python virtual environment: `venv/`
- Dependency caches: any `node_modules/`, Next.js build outputs (`.next/`,
  `.turbo/`), temporary assistant bundles
- Large Kaspi artifacts: `docs/ops/kaspi/Kaspi_orders/Archive/`, `Today/`, and
  `input/` directories, as well as generated ZIP/PDF files inside
  `Kaspi_orders`
- Git metadata and compiled Python bytecode (`.git/`, `*.pyc`, `__pycache__/`)

These exclusions keep the ZIP focused on source code and operational context
while avoiding bulky or reproducible assets.
