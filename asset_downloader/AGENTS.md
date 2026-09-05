# Repository Guidelines

## Project Structure & Module Organization

`download_assets.py` is the command-line entry point for recursively visiting Blender Studio galleries and downloading assets. `lambda_unzip_function/unzip_lambda.py` handles S3 ZIP extraction; its deployment instructions live alongside it. `images/` contains README illustrations. Downloaded assets default to `cg-production-data/<project-name>/` and should remain untracked.

## Build, Test, and Development Commands

Run commands from the metadata extractor repository root in an isolated Python environment:

- `python -m pip install -r asset_downloader/requirements.txt` installs only downloader dependencies.
- Add `USER_COOKIE` to the extractor-root `.env` using `asset_downloader/.env.example`; preserve existing settings and leave `asset_downloader/.env` absent. Cookie validation happens before argument parsing.
- `python asset_downloader/download_assets.py https://studio.blender.org/projects/<project>/<gallery-id>/` downloads a gallery tree.
- Append `--dir "cg-production-data/sample/"` to choose an output directory.
- `python -m py_compile asset_downloader/download_assets.py asset_downloader/lambda_unzip_function/unzip_lambda.py` checks syntax without executing downloads or S3 operations.

There is no build step. The Lambda helper uses `boto3`, which is not included in the downloader's requirements file.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions and variables, and uppercase module constants. Keep gallery traversal, HTML parsing, file downloading, and Lambda handling distinct. Follow existing Requests session usage and streamed file writes. No formatter or linter configuration is checked in.

## Testing Guidelines

No automated test suite or coverage threshold is checked in. For behavior changes, add focused `test_*.py` tests with mocked HTTP/S3 calls and temporary output directories. Cover repeated galleries, existing files, HTTP failures, and unsafe ZIP entry paths. Importing the downloader requires a configured cookie; importing the Lambda helper creates an S3 client.

Use a small gallery for manual verification. The Lambda handler uploads extracted objects and deletes the original ZIP, so integration checks need disposable fixtures.

## Commit & Pull Request Guidelines

Original history uses descriptive subjects such as `Move USER_COOKIE out of source and into .env`, without a strict prefix convention. This directory is now part of the extractor repository. Commit there, describe validation in PRs, then update the parent submodule reference after publication. See README import provenance.

## Security & Configuration

Never commit or log session cookies. Preserve ZIP traversal checks and scoped S3 permissions. Follow the README's Blender Studio subscription guidance and retain asset attribution.
