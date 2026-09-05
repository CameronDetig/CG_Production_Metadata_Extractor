import json
import urllib.parse
import boto3
import zipfile
import io
import os

s3 = boto3.client('s3')

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    # Get the object from the event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    try:
        # Only process .zip files
        if not key.lower().endswith('.zip'):
            print(f"Skipping non-zip file: {key}")
            return {'statusCode': 200, 'body': 'Skipped non-zip file'}

        print(f"Processing zip file: s3://{bucket}/{key}")
        
        # 1. Download to RAM 
        print(f"Downloading {key} into memory...")
        response = s3.get_object(Bucket=bucket, Key=key)
        zip_content = response['Body'].read()
        print("Download complete. Loaded into RAM.")

        # 2. Extract and Stream Upload
        extract_count = 0
        # Wrap bytes in BytesIO to make it seekable for ZipFile
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            for filename in z.namelist():
                if filename.endswith('/'):
                    continue

                # Reject entries that could escape the target prefix (zip slip):
                # an absolute path or a ".." segment makes os.path.join below
                # discard parent_dir entirely and write outside the intended prefix.
                normalized = filename.replace("\\", "/")
                if normalized.startswith("/") or ".." in normalized.split("/"):
                    print(f"Skipping unsafe zip entry: {filename}")
                    continue

                # Construct target key
                zip_name_no_ext = os.path.splitext(os.path.basename(key))[0]
                parent_dir = os.path.dirname(key)
                target_key = os.path.join(parent_dir, f"{zip_name_no_ext}", filename).replace("\\", "/")

                print(f"Streaming {filename} to s3://{bucket}/{target_key}")
                
                # Open the file from the zip (this is a stream)
                with z.open(filename) as source_stream:
                    # Upload using upload_fileobj (streams data, minimal extraction RAM usage)
                    s3.upload_fileobj(source_stream, bucket, target_key)
                
                extract_count += 1

        print(f"Extraction complete. {extract_count} files extracted.")

        # 3. Delete the original zip file from S3
        print(f"Deleting original zip file: {key}...")
        s3.delete_object(Bucket=bucket, Key=key)
        print("Zip file deleted successfully.")

        return {'statusCode': 200, 'body': f'Extraction successful. Extracted {extract_count} files.'}

    except Exception as e:
        print(f"Error processing {key}: {e}")
        raise e
