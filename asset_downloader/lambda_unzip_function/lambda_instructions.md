# S3 Integration (Upload & Cloud Unzip)

## Auto-Unzipping with AWS Lambda

This is a tool to automatically unzip .zip files when they are uploaded to an S3 bucket.
The production files from Blender Studio are often zipped, and to cut down on the amount of data that needs to be transferred to s3, we can keep them zipped for the upload and then unzip them once they get to the bucket.

### Setup

1. Create a role for the lamda function:

- Go to IAM > Roles > Create Role
- Under use case, select AWS Service > Lambda
- Skip attaching a managed policy for now (don't use S3FullAccess. It grants access to every bucket in the account, so a bug in the function could read/write/delete objects anywhere)
- Name: LambdaUnzipS3FilesRole
- Create Role
- After creating the role, add an inline policy scoped to just this bucket instead:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
            "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
        },
        {
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME"
        }
    ]
}
```

Replace `YOUR-BUCKET-NAME` with the actual bucket, and also attach the AWS-managed `AWSLambdaBasicExecutionRole` policy so the function can write CloudWatch logs.

2. Create a Lambda Function:

- Runtime: Python 3.9+
- Permissions: assign the `LambdaUnzipS3FilesRole` role.
- **Timeout**: Increase to 10-15 minutes 
- **Memory**: Set to **10240 MB (10GB)** since we are holding the zip in RAM, we need the maximum memory available.
- Code: Copy content from `unzip_lambda.py`.
- Be sure to click the **Deploy** button on the left side of the VS Code window.

3. Add Trigger:

- Go to Configuration > Triggers > Add Trigger.
- Select S3.
- Bucket: Your bucket.
- Event type: PUT / All object create events.
- Suffix: .zip.

## Upload files to S3

Use the provided script to upload your assets to an S3 bucket.

```python upload_to_s3.py <your-bucket-name> --dir "spring/concept_art"```

- Arguments:
    - bucket: The name of your S3 bucket.
    - --dir: Local directory to upload (default: spring_assets).

### Upload a zip file. It should disappear and be replaced by a folder filename/ containing the contents.