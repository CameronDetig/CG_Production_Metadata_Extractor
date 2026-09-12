# Blender build assets

The image uses pinned Linux AMD64 Blender archives mirrored in a private S3
bucket. GitHub Actions downloads and verifies the archives before invoking
Docker, so AWS credentials never enter the Docker build or its layers.

## Required archives

Download these exact files through a browser:

| Version | Archive | Official directory |
| --- | --- | --- |
| 2.49b | `blender-2.49b-linux-glibc236-py26-x86_64.tar.bz2` | <https://download.blender.org/release/Blender2.49b/> |
| 2.79b | `blender-2.79b-linux-glibc219-x86_64.tar.bz2` | <https://download.blender.org/release/Blender2.79/> |
| 3.6.9 | `blender-3.6.9-linux-x64.tar.xz` | <https://download.blender.org/release/Blender3.6/> |
| 4.5.5 LTS | `blender-4.5.5-linux-x64.tar.xz` | <https://download.blender.org/release/Blender4.5/> |

Use the Linux x86_64/x64 tar archive, not a Windows installer or archive. Keep
the filenames unchanged because the Dockerfile and version mapping pin these
paths.

## Provision and upload

The bootstrap Terraform creates the private bucket
`cg-extractor-build-artifacts-001879457662-us-east-1`. It enables versioning,
S3-managed encryption, Block Public Access, bucket-owner-enforced ownership,
and HTTPS-only access. Apply the bootstrap update before uploading:

```powershell
terraform -chdir=infra/bootstrap init "-backend-config=backend.hcl"
terraform -chdir=infra/bootstrap plan "-out=bootstrap.tfplan"
terraform -chdir=infra/bootstrap show bootstrap.tfplan
terraform -chdir=infra/bootstrap apply bootstrap.tfplan
```

Place all four downloads in one local directory and upload them. The script
generates `SHA256SUMS` from the downloaded bytes and uploads it alongside the
archives:

```powershell
.\scripts\upload_blender_build_assets.ps1 -SourceDirectory "$env:USERPROFILE\Downloads\blender-build-assets"
```

The resulting S3 keys are:

```text
s3://cg-extractor-build-artifacts-001879457662-us-east-1/blender/blender-2.49b-linux-glibc236-py26-x86_64.tar.bz2
s3://cg-extractor-build-artifacts-001879457662-us-east-1/blender/blender-2.79b-linux-glibc219-x86_64.tar.bz2
s3://cg-extractor-build-artifacts-001879457662-us-east-1/blender/blender-3.6.9-linux-x64.tar.xz
s3://cg-extractor-build-artifacts-001879457662-us-east-1/blender/blender-4.5.5-linux-x64.tar.xz
s3://cg-extractor-build-artifacts-001879457662-us-east-1/blender/SHA256SUMS
```

## Local build

Fetch the same verified inputs and build the image:

```powershell
.\scripts\fetch_blender_build_assets.ps1 -BucketName cg-extractor-build-artifacts-001879457662-us-east-1
docker buildx build --platform linux/amd64 --provenance=false --sbom=false --no-cache --progress=plain --load -t cg-metadata-extractor:local .
```

`build-assets/blender/` is intentionally ignored by Git. Do not add it to
`.dockerignore`; Docker must receive the archives in its build context.

## Bucket naming

The AWS account ID in the bucket name is not required. S3 general-purpose
bucket names must be unique in their namespace, so the account ID and Region
make collisions unlikely and make ownership obvious. If the bucket is renamed,
update the bucket resource and IAM resource in `infra/bootstrap/main.tf.json`,
the `BLENDER_ARTIFACT_BUCKET` workflow environment value, and the upload
script's default.
