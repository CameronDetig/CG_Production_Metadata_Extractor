"""Explicit Batch submission; never called by ordinary deployments."""
import json
import os
import re
from release import aws


def main():
    prefix = os.environ['SCAN_PREFIX']
    definition = os.environ['JOB_DEFINITION']
    if (not prefix.strip('/') or prefix.startswith('/') or '..' in prefix.split('/')
            or any(ord(char) < 32 for char in prefix)):
        raise ValueError('Choose a non-empty relative S3 prefix')
    if not re.fullmatch(r'cg-metadata-job:[1-9][0-9]*', definition):
        raise ValueError('Choose an exact cg-metadata-job revision')
    result = aws('batch', 'submit-job', '--job-name', 'manual-scan-' + os.environ['GITHUB_RUN_ID'],
                 '--job-queue', 'cg-metadata-queue', '--job-definition', definition,
                 '--container-overrides', json.dumps({'environment': [
                     {'name': 'S3_PREFIX', 'value': prefix},
                     {'name': 'OVERRIDE_EXISTING', 'value': 'false'}]}))
    print('Submitted Batch job ' + result['jobId'])


if __name__ == '__main__':
    main()
