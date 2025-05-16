# s3_utils.py

import os
import boto3
import logging
from botocore.exceptions import NoCredentialsError, ClientError

# Only download config remains
EKG_DATA_BUCKET    = os.getenv('EKG_DATA_BUCKET',   'physionet-open')
EKG_DATA_PREFIX    = os.getenv('EKG_DATA_PREFIX',   'mimic3wdb-matched/1.0')
DOWNLOAD_DIRECTORY = os.getenv('DOWNLOAD_DIRECTORY','/tmp')

# Init S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_DEFAULT_REGION')
)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def download_patient_data(patient_id):
    """
    Fetch .dat/.hea files for patient_id from S3 into /tmp/{patient_id}.
    Returns the local path or None if no data / on error.
    """
    # Build a clean prefix string
    s3_prefix = f"{EKG_DATA_PREFIX.rstrip('/')}/{patient_id[:3]}/{patient_id}/"
    local_dir = os.path.join(DOWNLOAD_DIRECTORY, patient_id)
    os.makedirs(local_dir, exist_ok=True)

    try:
        resp = s3_client.list_objects_v2(Bucket=EKG_DATA_BUCKET, Prefix=s3_prefix)
        if 'Contents' not in resp:
            logger.warning(f"No files found under S3 prefix {s3_prefix}")
            return None

        for obj in resp['Contents']:
            key = obj['Key']
            filename = os.path.basename(key)
            path = os.path.join(local_dir, filename)
            s3_client.download_file(EKG_DATA_BUCKET, key, path)
            logger.info(f"Downloaded {key} → {path}")

        return local_dir

    except (NoCredentialsError, ClientError) as e:
        logger.error(f"S3 download failed for {patient_id}: {e}")
        return None
