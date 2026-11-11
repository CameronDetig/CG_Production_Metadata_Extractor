# CI/CD

Workflows live in `.github/workflows/`. AWS access uses GitHub OIDC with a separate role per purpose; there are no stored AWS secrets. Infrastructure is owned by `infra/` (see [infra/README.md](../infra/README.md)). Live settings are recorded in [infra/INVENTORY.md](../infra/INVENTORY.md).

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `infra-checks.yml` ("Infrastructure checks") | Every pull request | `validate` job: Terraform `fmt`, `init`, `validate` for `infra/` and `infra/bootstrap/`, the release-tooling unit tests in `infra/tools/`, and the sequence-gap regression. |
| `release.yml` ("Plan extractor release") | Push to `main` touching `src/**`, `Dockerfile`, `requirements.txt`, `scripts/fetch_blender_build_assets.ps1`, `infra/**` or `.github/workflows/**`; manual dispatch | `build` job: on a push that changes application files, builds the image and pushes `sha-<commit>` and `v<N>` to ECR (or reuses an existing `sha-` tag). `plan` job: saves a private Terraform plan to S3. **Never applies anything.** A manual dispatch skips the build and plans against the image already deployed. |
| `approve-release.yml` ("Approve production release") | Manual dispatch with a plan run ID | `apply` job (`production` environment): `release.py verify`, checks out the planned commit, `apply` of the saved plan, then `smoke`. |
| `scan.yml` ("Submit metadata scan") | Manual dispatch | Submits one explicitly chosen Batch scan (`production-scan` environment). Scans are never part of a release. |

## Two-stage release

1. Merging application or infra changes to `main` runs "Plan extractor release": build, push, plan. Nothing in production changes.
2. A human reviews the run summary (affected resources) and then dispatches "Approve production release" with that plan run ID.
3. `infra/tools/release.py` (`verify`, then `apply`):
   - checks provenance: a successful release-plan run on `main` of this repository, a manifest whose commit matches the run, a plan under 24 hours old, and a matching file hash;
   - **rejects a superseded plan**: it compares the planned commit to `main` through the GitHub compare API and refuses if `src/`, `infra/`, `Dockerfile`, `requirements.txt`, the Blender fetch script or the two release workflows changed since. A compare of 300 or more files counts as superseded. Docs and `testing/` changes do not invalidate a plan (`RELEASE_PATHS` in `release.py`);
   - refuses any plan that destroys or replaces a resource (`plan_changes`);
   - applies the exact saved plan, with no re-plan.
4. `release.py smoke` checks that the active Batch job definition uses the image Terraform's state expects. A smoke failure fails the run but does not roll anything back.

Keep this two-stage flow. Do not collapse it into an automatic apply. Editing a release workflow or `infra/` supersedes any pending plan, so merge such changes when no plan is waiting for approval.

## AWS roles

| Role | Used by | Trust (OIDC `sub`) |
|---|---|---|
| `github-cg-extractor-build` | `release.yml` `build` job | `ref:refs/heads/main` |
| `github-cg-extractor-plan` | `release.yml` `plan` job | `ref:refs/heads/main` |
| `github-cg-extractor-apply` | `approve-release.yml` | `environment:production` |
| `github-cg-extractor-scan` | `scan.yml` | `environment:production-scan` |

The roles are defined in `infra/bootstrap/`, a separate Terraform stack with its own state (`state/bootstrap.tfstate`) that an operator applies locally. CI cannot change it.

## Constraints

- **Do not add `environment:` to a job whose role trust pins `ref:refs/heads/main`** (`build`, `plan`). A job environment changes the OIDC `sub` to `environment:<name>` and the role would reject it. Change the trust policy in the same release if you need one.
- Every job has `timeout-minutes`. Runners are pinned to `ubuntu-26.04`; bump deliberately when the image is retired.
- Plan and apply share the non-cancelling `terraform-production` concurrency group, so runs queue instead of overlapping.
- The image build needs at least 25 GB of free disk and fetches Blender packages from a private S3 bucket (see [blender_build_assets.md](blender_build_assets.md)). That is why there is no image build on pull requests: it would need AWS credentials on PR runs.
- The `production` and `production-scan` GitHub environments have no required reviewers, so approval is a deliberate manual dispatch, not a recorded reviewer sign-off.

## ECR

Repository `cg-metadata-extractor` (defined in `infra/resources.tf`):
- Each image has two tags, `sha-<commit>` and `v<N>`. Tags are **immutable**: pushing an existing tag fails. `release.yml` reuses an existing `sha-` tag instead of rebuilding and only adds the `v<N>` tag. Releases pin the image by digest.
- Basic scan-on-push is on (free). Findings are informational and do not block a release.
- The lifecycle policy keeps the last 3 `v`-prefixed images.
- The tag-reuse path only runs on a push that changes application files. A manual plan dispatch skips the build, so it does not exercise it.

## Branch protection

A repository ruleset, "main protection", is active on `main`. It blocks deletion and force-push and requires the `validate` check. It does **not** require pull requests, and repository admins can bypass it, so the owner can still push directly. Anyone without bypass cannot push straight to `main`, since the check cannot have run yet. The PR trigger of `infra-checks.yml` is deliberately unfiltered by path: a required check from a path-filtered workflow never reports on unrelated PRs and would block them. Any new required check must run on every PR too.

## Troubleshooting a failed release

- **Apply errors are hidden.** `release.py` writes Terraform's output to `infra/.private/last-error.log` on the runner and prints only "terraform apply failed". To find the real cause, look up the failing call in CloudTrail (for example `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=RegisterJobDefinition`) or reproduce the apply locally.
- **A failed create leaves a tainted resource.** If AWS creates a resource but Terraform's read-back is denied, the resource is marked tainted. Every later plan wants to replace it, and `release.py` refuses the plan with "Destruction/replacement requires a separate migration". Check `terraform state` for `tainted`, fix the cause, then `terraform untaint '<address>'` if the live resource is correct.
- **A failed update can still write new values into state.** The AWS provider saves the planned values even when the update call fails. State then disagrees with AWS, plans (which run with `-refresh=false`) show no change, and `release.py smoke` fails with "Batch job definition does not match the applied Terraform state". Run `terraform apply -refresh-only` to reconcile state with AWS, then plan again.
- **Missing IAM permissions surface late.** The plan and apply roles use hand-scoped policies. Two that were missing and had to be added: `ssm:DescribeParameters` (Terraform reads an SSM parameter back after creating it) and Batch `RegisterJobDefinition` on the revision-less ARN `job-definition/cg-metadata-job`.
- **Local Terraform on macOS.** The checked-in lock files list only Windows and Linux provider hashes, so `-lockfile=readonly` fails locally. Run `terraform init` without it, then `git checkout` the lock files so they are not committed. Terraform's S3 backend does not read an `aws login` session; export credentials with `eval "$(aws configure export-credentials --format env)"`.
