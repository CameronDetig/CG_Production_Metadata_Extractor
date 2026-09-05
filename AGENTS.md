# Repository Guidelines

## Project Structure & Module Organization

`src/scanner.py` coordinates scanning, `src/storage_adapter.py` abstracts local/S3 storage, and `src/database.py` defines persistence. Format-specific handlers live in `src/extractors/`; Blender subprocess scripts are in `src/extractors/blender_scripts/`. `src/embedders/` generates embeddings, and `src/sequence_detector.py` groups numbered assets. `testing/` contains tests and diagnostics; `scripts/` and `docs/` cover operations and setup.

`asset_downloader/` contains the gallery CLI and S3 unzip helper as ordinary source code, with separate dependencies and a nested contributor guide. Keep source assets in `cg-production-data/`, generated thumbnails in `cg-production-data-thumbnails/`, and runtime database/output directories out of commits.

## Build, Test, and Development Commands

Run these commands from this submodule's root:

- `python -m pip install -r asset_downloader/requirements.txt` installs downloader-only dependencies. Run `python asset_downloader/download_assets.py <gallery-url> --dir cg-production-data/shows/<project>` with `USER_COOKIE` in the root `.env`; align scanner `DATA_PATH` with that directory. Downloading, unpacking, and scanning remain separate steps.

- `python -m pip install -r requirements.txt` installs Python dependencies in your virtual environment. Native tools such as Blender and FFmpeg require separate setup; see `docs/local_testing_guide.md`.
- `docker compose build` builds the extraction image and its native dependencies.
- `docker compose up` starts PostgreSQL with pgvector and the scanner. Check Compose's `DATA_PATH` first; it currently targets the Sintel directory.
- `docker compose logs -f metadata-extractor` follows scanner output.
- `python -m unittest discover -s testing -p test_gap_splitting.py` runs isolated sequence-gap regressions.
- `python testing/test_sequence_detector.py` runs sequence-detection diagnostics; inspect the printed results.

## Coding Style & Naming Conventions

Use four spaces, `snake_case` modules/functions, `PascalCase` classes, and uppercase constants. Preserve type hints and module logging. Name new handlers `<type>_extractor.py`; wire supported extensions into the scanner and update database models when metadata changes. Keep storage-specific logic in adapters. No shared formatter or linter configuration is checked in.

## Testing Guidelines

Tests combine `unittest` and standalone diagnostic scripts; no coverage threshold is enforced. Add `test_*.py` regressions under `testing/` for sequence boundaries, metadata fields, and thumbnail paths. Use small fixtures and mock storage for isolated tests. Database, S3, Blender, and embedding checks need their respective services, binaries, or models; report skipped checks explicitly.

## Commit & Pull Request Guidelines

History uses short descriptive messages, for example `Fixed thumbnail naming issue`. Explain affected formats, schema/configuration changes, and validation in PRs. Commit component changes here before updating the parent repository's submodule reference; publish the referenced commit first.

## Configuration & Compatibility

Keep secrets in local environment configuration. Review `STORAGE_TYPE`, `DATABASE_URL`, and thumbnail paths before scanning. Coordinate schema and embedding changes with the LLM assistant. Preserve sequential Blender processing and version selection in `src/extractors/blender_version_mapping.json`.
