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
- [ ] `ASSET_BUCKET_NAME=your-actual-bucket-name`
- [ ] `S3_PREFIX=production-files/` (or empty for root)
- [ ] `THUMBNAIL_BUCKET_NAME=your-thumbnail-bucket-name`
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
   - Public access: No (for security)
   - RDS Data API: enable
7. Create database


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
        }
    ]
}
```

> [!NOTE]
> **Bucket Configuration:**
> - The first statement allows **read access** to your production files bucket
> - The second statement allows **write access** to upload thumbnails to a separate bucket with public-read ACL for CDN access


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
   - vCPUs: 2
   - Memory: 4 GB
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

                      # use the password you made earlier for the database
     DATABASE_URL=postgresql://postgres:<your-db-password>@<your-database-write-endpoint>:5432/postgres
     LOG_LEVEL=INFO
     ```

> [!WARNING]
> **Security Best Practice**: Store the `DATABASE_URL` in AWS Secrets Manager and reference it in the job definition instead of hardcoding credentials.

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

- Use Spot instances in compute environment (up to 90% savings)
- Set Min vCPUs to 0 (scales down when idle)
- Use appropriate instance types (don't over-provision)
- Monitor CloudWatch metrics for optimization opportunities

## Security Best Practices

1. **Never hardcode credentials** - Use IAM roles and Secrets Manager
2. **Enable VPC** - Run Batch and RDS in private subnets
3. **Encrypt data** - Enable encryption at rest for RDS and S3
4. **Least privilege** - Grant only necessary IAM permissions
5. **Audit logs** - Enable CloudTrail for API call logging
