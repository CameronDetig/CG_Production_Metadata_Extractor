> Historical manual setup reference. Use the [Terraform adoption and release guide](../infra/README.md) for current deployment. Live configuration is recorded in `infra/INVENTORY.md`; older settings below may differ.

# AWS Deployment Guide

This guide covers deploying the CG Production Metadata Extractor to AWS Batch with S3 storage and RDS PostgreSQL database.


## Quick Reference: Critical Configuration Checklist

Before running your job, verify these are properly configured:

✅ **Container Image:**
- [ ] Docker image built with updated Dockerfile
- [ ] Image pushed to ECR
- [ ] Job definition points to correct ECR URI

✅ **Environment Variables in Job Definition:**
- [ ] `STORAGE_TYPE=s3` (NOT local)
- [ ] `ASSET_BUCKET_NAME=cg-production-data`
- [ ] `S3_PREFIX=shows/` (or empty for root)
- [ ] `THUMBNAIL_BUCKET_NAME=cg-production-data-thumbnails`
- [ ] `AWS_REGION=us-east-1` (match your bucket region)
- [ ] `DATABASE_URL=postgresql://user:password@rds-endpoint:5432/postgres`

✅ **IAM Permissions:**
- [ ] IAM role attached to job definition
- [ ] Role has `s3:GetObject` and `s3:ListBucket` on your bucket
- [ ] Role has `AmazonECSTaskExecutionRolePolicy`

✅ **Networking:**
- [ ] RDS security group allows inbound from Batch compute environment
- [ ] RDS and Batch are in same VPC (or VPC peering configured)




## Architecture Overview

```
┌─────────────────┐
│   S3 Bucket     │ ← Production files (images, videos, .blend)
│  (input data)   │
└────────┬────────┘
         │
         ↓ AWS Batch triggers job
┌─────────────────┐
│  AWS Batch Job  │ ← Container downloads files temporarily
│  (this scanner) │
└────────┬────────┘
         │
         ↓ writes metadata
┌─────────────────┐
│  RDS PostgreSQL │ ← Metadata stored permanently
│   (database)    │
└─────────────────┘
```

You will need an AWS Account with appropriate permissions

On your local machine, install AWS CLI (Command Line Interface) for managing AWS services

Download and run the MSI installer: https://aws.amazon.com/cli/

verify installation:
```
aws --version
```

Configure AWS Credentials:
```
aws configure
# Enter your:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (e.g., us-east-1)
# - Default output format (json)
```

Get your AWS Account ID:
```
aws sts get-caller-identity --query Account --output text
```

Make sure you have docker installed and running: https://www.docker.com/

## Step 1: Set Up RDS PostgreSQL Database

### Create RDS Instance

1. Go to AWS RDS Console
2. Click "Create database"
3. For Engine type, choose "PostgreSQL" (not "Aurora (PostgreSQL Compatible)")
4. Template: for minimal cost, choose "Sandbox" 
5. Select "Single AZ (Availability Zone)"
6. Configure:
   - DB instance identifier: `cg-metadata-db`
   - Master username: `postgres`
   - Master password: (create a password and save for use later)
   - Select instance size (e.g., burstable classes: db.t4g.micro for testing)
   - VPC: Default or custom (if you have a custom VPC, make sure to select it)
   - Public access: No (for security and to avoid the ~$3.60/month AWS charge for an in-use public IPv4 address)
7. Create database

> [!NOTE]
> **Connecting locally without public access:** Batch jobs and the chatbot Lambda already reach the database over their VPC security groups. For ad-hoc access from your laptop (e.g. pgAdmin), use an SSH tunnel through a bastion/EC2 instance in the same VPC, AWS Systems Manager Session Manager port forwarding, or temporarily re-enable public access for the session and disable it again afterward.


To make it easier to connect to the database from your local machine, you can set the public access setting to "publicly available".


### Initialize Database Schema

The application will automatically create tables on first run using SQLAlchemy. No manual schema creation needed!

### Get Connection String

Format: `postgresql://username:password@endpoint:5432/database`

Example: `postgresql://postgres:mypassword@cg-metadata-db.abc123.us-east-1.rds.amazonaws.com:5432/postgres`

## Step 2: Set Up S3 Bucket

### Create S3 Bucket

```bash
aws s3 mb s3://my-cg-production-files --region us-east-1
```

### Upload Production Files

```bash
aws s3 sync ./local-data s3://my-cg-production-files/production-files/
```

### Verify Files

```bash
aws s3 ls s3://my-cg-production-files/production-files/ --recursive
```

### Create Thumbnail Bucket

Store thumbnails in a separate bucket:

```bash
aws s3 mb s3://my-cg-thumbnails --region us-east-1
```


## Step 3: Build and Push Docker Image to ECR

### Create ECR Repository

```bash
aws ecr create-repository --repository-name cg-metadata-extractor --region us-east-1
```

### Build and Push Image

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t cg-metadata-extractor .

# Tag image
docker tag cg-metadata-extractor:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/cg-metadata-extractor:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/cg-metadata-extractor:latest
```

## Step 4: Create IAM Role for Batch Job

### Create IAM Policy

Create a policy named `CGMetadataExtractorPolicy` with these permissions:

This will allows the batch process access to the s3 container with the files.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": [
                "arn:aws:s3:::cg-production-data",
                "arn:aws:s3:::cg-production-data/*",
                "arn:aws:s3:::cg-production-data-thumbnails",
                "arn:aws:s3:::cg-production-data-thumbnails/*",
                "arn:aws:s3:::cg-production-data-testing",
                "arn:aws:s3:::cg-production-data-testing/*",
                "arn:aws:s3:::cg-production-data-thumbnails-testing",
                "arn:aws:s3:::cg-production-data-thumbnails-testing/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": "secretsmanager:GetSecretValue",
            "Resource": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:cg-metadata-db/database-url-*"
        }
    ]
}
```

> [!NOTE]
> **Bucket Configuration:**
> - The first statement allows **read access** to your production files bucket
> - The second statement allows **write access** to upload thumbnails to a separate bucket with public-read ACL for CDN access
> - The third statement lets the job read the `DATABASE_URL` secret at container start (see Step 5) — scoped to that one secret only, not `secretsmanager:*`


### Create IAM Role

1. Go to IAM Console → Roles → Create Role
2. Select "AWS service" → "Elastic Container Service Task"
3. Attach policies:
   - `CGMetadataExtractorPolicy` (created above)
   - `AmazonECSTaskExecutionRolePolicy` (AWS managed)
4. Name: `CGMetadataExtractorRole`

### Add RDS Access to Security Group

1. Go to VPC console → Security groups → select the security group associated with your cg database
2. Edit inbound rules
3. Add rule:
   - Type: PostgreSQL
   - Source: Security group of Batch compute environment (will create next)

## Step 5: Set Up AWS Batch

### Create Compute Environment

1. Go to Batch Console → Environments → create environment
2. Configuration:
   - Name: `cg-metadata-compute`
   - Service role: Create new or use existing
   - Instance type: `optimal` (or specific like `m5.large`)
   - Min vCPUs: 0
   - Max vCPUs: 4 (adjust based on workload)
   - VPC: Same as RDS
   - Subnets: Same as RDS
   - Security groups: Note the security group ID for RDS access

### Create Job Queue

1. AWS Batch Console → Job queues → Create
2. Configuration:
   - Name: `cg-metadata-queue`
   - Priority: 1
   - Compute environments: Select `cg-metadata-compute`

### Create Job Definition

1. AWS Batch Console → Job definitions → Create
2. Configuration:
   - Name: `cg-metadata-job`
   - Platform: EC2 or Fargate
   - Execution role: `CGMetadataExtractorRole`
   - Image: `<account-id>.dkr.ecr.us-east-1.amazonaws.com/cg-metadata-extractor:latest`
   - vCPUs: 2, Memory: 16 GB — a reasonable **starting point** for a fresh setup.

     > [!NOTE]
     > **Current live config is 8 vCPU / 52 GB** (job definition revision 35, up from 2 vCPU/4GB at revision 1). It was bumped repeatedly over ~34 revisions, most likely to fix out-of-memory failures on large `.blend` files. Fargate bills per vCPU/GB-hour *per job run*, so an oversized job definition costs more every time it runs even though there's no idle cost between runs. Nobody has gone back to check whether recent jobs actually need that much — worth profiling actual peak memory usage (CloudWatch Container Insights, or just watch a run) before the next scan, and stepping the size back down if there's headroom.
   - Add Environment variables:
     ```
     STORAGE_TYPE=s3
     ASSET_BUCKET_NAME=cg-production-files-bucket-name

                      # The S3_PREFIX is the folder path (prefix) within your 
                      # S3 bucket where your production files are stored. 
                      # It tells the scanner which subdirectory to scan.
                      # s3://my-cg-production-files/
                        ├── production-files/          ← This is the prefix
                        │   ├── data/
                        │   │   └── spring/
                        │   │       ├── assets/
                        │   │       ├── concept_art/
                        │   │       └── shot/
                        │   └── other-project-files/
                        ├── backups/
                        └── temp/

                      # if you want to scan everything, use:
                      S3_PREFIX=

                      # if you want to scan a specific folder, use:
                      S3_PREFIX=production-files/
     S3_PREFIX=production-files/
     
                      # Separate bucket for thumbnails (for CDN access)
     THUMBNAIL_BUCKET_NAME=cg-thumbnails-bucket-name
     
     AWS_REGION=us-east-1
     LOG_LEVEL=INFO

                      # Resume support: skip files already in database (useful if job crashes partway through)
                      # Set to 'false' to resume, 'true' to re-process everything (default)
     OVERRIDE_EXISTING=true

                      # Parallel processing: number of workers for non-.blend files (default: 4)
                      # .blend files are always processed sequentially to avoid memory issues
     SCANNER_WORKERS=4
     ```
   - Add `DATABASE_URL` as a **secret**, not a plain environment variable (see below).

> [!IMPORTANT]
> **`DATABASE_URL` must be injected from Secrets Manager, not hardcoded.** The live job definition previously had the full `postgresql://user:password@...` connection string sitting in plaintext in its environment variables — visible to anyone with `batch:DescribeJobDefinitions` permission. This is now fixed:
> 1. The secret is stored in Secrets Manager as `cg-metadata-db/database-url`, as JSON key-value pairs (readable in the console's "Key/value pairs" view, same shape RDS-managed secrets use): `username`, `password`, `host`, `port`, `dbname`, `engine`, plus a `url` field holding the full assembled connection string.
> 2. `CGMetadataExtractorPolicy` grants the job/execution role `secretsmanager:GetSecretValue` scoped to just that one secret ARN. (IAM authorization only cares about the base secret ARN — the JSON-key/version suffix below doesn't need to be, and isn't, part of the policy's resource pattern.)
> 3. The job definition references only the `url` key via the `secrets` field's JSON-key suffix, so the container's `DATABASE_URL` env var receives just the connection string, not the whole JSON blob:
>    ```json
>    "secrets": [
>      { "name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:cg-metadata-db/database-url-XXXXXX:url::" }
>    ]
>    ```
> If the database password ever changes, update the secret's value in Secrets Manager (`aws secretsmanager put-secret-value`, keeping the same JSON shape) — no job definition change needed, since it's resolved at container start.

In the command prompts box, either delete the default "hello world" command, or replace it with the command to run the scanner file (CMD ["python3", "scanner.py"]).

## Step 6: Run the Job

### Submit Job (2 options)

## Option 1: Through the CLI
```bash
aws batch submit-job \
  --job-name cg-metadata-scan-$(date +%Y%m%d-%H%M%S) \
  --job-queue cg-metadata-queue \
  --job-definition cg-metadata-job
```

## Option 2: Through the AWS Console UI
1. Go to the "Jobs" section in the AWS Batch console
2. Submit New Job: Click "Submit new job"
3. Configure the Job:
    - Enter a unique Job name (something like "cg-metadata-job-run-1)
    - Select your Job definition: (should be something like "cg-metadata-job")
    - Choose a Job queue: cg-metadata-queue
    - Optional Overrides: You can override container settings
4. Click "Submit job"


### Monitor Job

Once submitted, your job will progress through these states:

SUBMITTED → PENDING → RUNNABLE → STARTING → RUNNING → SUCCEEDED/FAILED

1. AWS Batch Console → Jobs  (you may have to refresh results)
2. Click on job to see status and logs
3. View CloudWatch Logs for detailed output

### Check Results

Connect to RDS: 

AWS doesn't have a dedicated database viewer, so if you want a GUI, you will need to download a tool. I am using pgAdmin: https://www.pgadmin.org/

To connect to the database, using pgAdmin:
1. Select "Create" → "Server..."
2. General Tab
Name: Give it a name like "AWS cg-metadata-db"
3. Connection Tab
Fill in these details:

    - Host name/address: <your database name> (ex. "cg-metadata-db.cluster-corgeqweywqv.us-east-1.rds.amazonaws.com")
    - Port: 5432
    - Maintenance database: postgres (start with this default)
    - Username: postgres
    - Password: <Your database password you made earlier>

![pgAdmin_connection](images/pgAdmin_connection.png)

Query the database:

```sql
-- Total files processed
SELECT COUNT(*) FROM files;

-- Files by type
SELECT file_type, COUNT(*) FROM files GROUP BY file_type;

-- Recent scans
SELECT file_name, scan_date FROM files ORDER BY scan_date DESC LIMIT 10;
```

![pgAdmin_view_tablen](images/pgAdmin_view_table.png)

## Step 7: Automate with Triggers (Optional)

### Trigger on S3 Upload (Event-Driven)

1. Create Lambda function to submit Batch job
2. Add S3 event trigger on bucket
3. Lambda submits job when new files uploaded

### Scheduled Scans (CloudWatch Events)

1. Create CloudWatch Events rule
2. Schedule: `cron(0 2 * * ? *)` (daily at 2 AM)
3. Target: AWS Batch job queue

## Monitoring and Troubleshooting

### View Logs

**Option 1: AWS Console**
1. Go to AWS Batch Console → Jobs
2. Click on your job
3. Click "View logs" in the job details
4. This opens CloudWatch Logs

**Option 2: AWS CLI**
```bash
# Get job ID from Batch console, then:
aws logs tail /aws/batch/job --follow
```

### Common Issues

**Job fails immediately:**
- Check IAM role permissions (S3 read access required)
- Verify ECR image exists and is accessible
- Check environment variables in job definition (especially DATABASE_URL and ASSET_BUCKET_NAME)
- Review CloudWatch logs for startup errors

**Cannot connect to RDS:**
- Verify security group allows inbound PostgreSQL (port 5432) from Batch compute environment
- Check DATABASE_URL format: `postgresql://username:password@endpoint:5432/dbname`
- Ensure RDS is in same VPC as Batch compute environment
- Test connection string locally first using psql or pgAdmin

**S3 access denied:**
- Verify IAM role has `s3:GetObject` and `s3:ListBucket` permissions
- Check bucket name and prefix are correct (no typos)
- Ensure bucket is in the same region or cross-region access is configured
- Verify bucket policy doesn't block access

**Out of memory errors:**
- Increase memory in job definition (try 8 GB or more)
- Reduce number of concurrent file operations
- Consider processing large .blend files separately

**Blender extraction fails:**
- Check if Blender is properly installed in container (test locally first)
- Increase job timeout in job definition
- Check .blend file compatibility with Blender version in container

**Container runs but processes 0 files:**
- Verify `STORAGE_TYPE=s3` is set (not `local`)
- Check ASSET_BUCKET_NAME is correct
- Verify S3_PREFIX matches your folder structure (use empty string for root)
- Ensure IAM role has ListBucket permission on the bucket

### Debugging Steps

1. **Test container locally first:**
   ```bash
   docker run -e STORAGE_TYPE=s3 \
              -e ASSET_BUCKET_NAME=your-bucket \
              -e S3_PREFIX=production-files/ \
              -e AWS_REGION=us-east-1 \
              -e DATABASE_URL=postgresql://user:pass@localhost:5432/db \
              cg-metadata-extractor
   ```

2. **Check CloudWatch Logs immediately after job fails:**
   - Look for Python exceptions
   - Check if storage adapter initializes
   - Verify database connection succeeds

3. **Test S3 access from container:**
   ```bash
   docker run --entrypoint /bin/bash -it cg-metadata-extractor
   # Inside container:
   python3 -c "import boto3; s3=boto3.client('s3'); print(s3.list_objects_v2(Bucket='your-bucket', MaxKeys=5))"
   ```

4. **Verify environment variables:**
   - Double-check all env vars in job definition
   - Look for typos in DATABASE_URL
   - Ensure no extra spaces or quotes

## Cost Optimization

Batch runs on Fargate, so there's no idle compute cost between job runs — you only pay per job execution. As of this writing, the account-wide cost drivers (verified against the live account) were:

- **RDS (`cg-metadata-db`, db.t4g.micro/gp3)**: the largest fixed cost. Already the cheapest viable burstable instance class; shared with the chatbot Lambda, so it can't be scaled down further without affecting that service too.
- **S3 (`cg-production-data`)**: scales with how much production data is stored. An Intelligent-Tiering lifecycle rule is applied so infrequently-accessed objects automatically move to a cheaper tier with no retrieval fees.
- **ECR image storage**: container image versions accumulate on every push. A lifecycle policy (see `scripts/push_to_ecr.sh`) keeps only the 3 most recent tagged versions and expires untagged/orphaned images after 1 day.
- **RDS public IPv4 address**: AWS charges ~$0.005/hr for any in-use public IPv4 address. The database no longer has `PubliclyAccessible` set, which removes this charge — see the note in Step 1 for how to still connect locally when needed.
- **CloudWatch log retention**: `/aws/batch/job` previously had no expiration (logs kept forever). Retention is now set to 30 days.

Further opportunities, not yet applied: right-sizing the job definition's vCPU/memory (it has grown to 8 vCPU / 52GB over many revisions — worth checking whether recent jobs actually need that much before the next bump), and using Fargate Spot for the compute environment if occasional job interruption/retry is acceptable.

## Security Best Practices

1. **Never hardcode credentials** - Use IAM roles and Secrets Manager. `DATABASE_URL` is injected via Secrets Manager (see Step 5) rather than hardcoded in the job definition.
2. **Enable VPC** - Run Batch and RDS in private subnets
3. **Encrypt data** - Enable encryption at rest for RDS and S3
4. **Least privilege** - Grant only necessary IAM permissions
5. **Audit logs** - Enable CloudTrail for API call logging
