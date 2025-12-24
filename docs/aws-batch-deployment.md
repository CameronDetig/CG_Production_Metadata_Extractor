# AWS Batch Deployment Guide

This guide covers deploying the CG Production Data Assistant to AWS Batch with S3 storage and RDS PostgreSQL database.

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
3. Choose PostgreSQL engine
4. Select appropriate instance size (e.g., db.t3.micro for testing)
5. Configure:
   - DB instance identifier: `cg-metadata-db`
   - Master username: `postgres`
   - Master password: (create a password and save for use later)
   - VPC: Default or custom
   - Public access: No (for security)
   - RDS Data API: enable
6. Create database


This should look something like:
- ch-metadata-db &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  # Regional cluster
  - cg-metadata-db-instance-1 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; #  Writer instance
  - g-metadata-db-instance-1-us-east-1b &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; # Reader instance


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
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-cg-production-files",
        "arn:aws:s3:::my-cg-production-files/*"
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
     S3_BUCKET_NAME=cg-production-files-bucket-name

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
     AWS_REGION=us-east-1

                      # use the password you made earlier for the database
     DATABASE_URL=postgresql://postgres:password@rds-endpoint:5432/postgres
     LOG_LEVEL=INFO
     ```

> [!WARNING]
> **Security Best Practice**: Store the `DATABASE_URL` in AWS Secrets Manager and reference it in the job definition instead of hardcoding credentials.

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

Go to AWS Aurora and RDS - Query Editor

![connect to rds](images/connect_to_db.png)


AWS doesn't have a dedicated database viewer, so if you want a GUI, you will need to download a tool. I am using pgAdmin: https://www.pgadmin.org/


Query the database:

```sql
-- Total files processed
SELECT COUNT(*) FROM files;

-- Files by type
SELECT file_type, COUNT(*) FROM files GROUP BY file_type;

-- Recent scans
SELECT file_name, scan_date FROM files ORDER BY scan_date DESC LIMIT 10;
```

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

```bash
# Get job ID from Batch console, then:
aws logs tail /aws/batch/job --follow
```

### Common Issues

**Job fails immediately:**
- Check IAM role permissions
- Verify ECR image exists and is accessible
- Check environment variables in job definition

**Cannot connect to RDS:**
- Verify security group allows inbound from Batch compute environment
- Check DATABASE_URL is correct
- Ensure RDS is in same VPC as Batch

**S3 access denied:**
- Verify IAM role has s3:GetObject and s3:ListBucket permissions
- Check bucket name and prefix are correct

**Out of memory errors:**
- Increase memory in job definition
- Process files in smaller batches

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
