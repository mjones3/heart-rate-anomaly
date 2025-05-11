import os
import boto3
import logging
from botocore.exceptions import NoCredentialsError, ClientError

# Load environment variables from Docker
OUTPUT_S3_BUCKET = os.getenv('OUTPUT_S3_BUCKET', 'mjones3-patient-data')  # Default if not set
OUTPUT_S3_PREFIX = os.getenv('OUTPUT_S3_PREFIX', 'processed_data/')  # Default if not set
EKG_DATA_BUCKET = os.getenv('EKG_DATA_BUCKET', 'physionet-open')
EKG_DATA_PREFIX = os.getenv('EKG_DATA_PREFIX', 'mimic3wdb-matched/1.0/')
DOWNLOAD_DIRECTORY = os.getenv('DOWNLOAD_DIRECTORY', '/tmp')

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_DEFAULT_REGION')
)

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def download_patient_data(patient_id):
    # Extract the prefix from the patient_id (e.g., "p00", "p01", etc.)
    prefix = patient_id[:3]  # e.g., "p00", "p01", etc.
    # base_ekg_path = s.path.join(download_dir, patient_id)
    download_dir = f"{EKG_DATA_PREFIX}/{prefix}/{patient_id}/"
    patient_data_dir = os.path.join(DOWNLOAD_DIRECTORY, patient_id)  # or any custom directory logic


    # Ensure the directory for the patient data exists
    os.makedirs(patient_data_dir, exist_ok=True)

    try:
        # List objects in the specific S3 folder that matches the patient ID
        response = s3_client.list_objects_v2(Bucket=EKG_DATA_BUCKET, Prefix=download_dir)

        # If no files are found for the patient ID, log a warning
        if 'Contents' not in response:
            print(f"No contents found for {patient_id}")
            return None

        # Iterate over each object in the S3 folder
        for obj in response['Contents']:
            file_key = obj['Key']
            file_name = os.path.basename(file_key)
            local_file_path = os.path.join(patient_data_dir, file_name)

            # Download the file from S3 to the local directory
            s3_client.download_file(EKG_DATA_BUCKET, file_key, local_file_path)

            # Log the download process
            print(f"Downloaded {file_name} to {local_file_path}")

        # Return the path to the patient data directory
        return patient_data_dir

    except (NoCredentialsError, ClientError) as e:
        # Handle errors such as missing credentials or client issues
        print(f"Error downloading from S3: {e}")
        return None


def upload_json_to_s3(json_buffer, patient_id, timestamp):
    # Generate unique filename using patient_id and timestamp
    file_name = f"{patient_id}_{timestamp}.json"
    s3_key = f"{OUTPUT_S3_PREFIX}{patient_id}/{file_name}"

    try:
        # Upload the JSON to S3
        s3_client.put_object(Bucket=OUTPUT_S3_BUCKET, Key=s3_key, Body=json_buffer)
        logger.info(f"Uploaded {file_name} to S3: {s3_key}")
    except (NoCredentialsError, ClientError) as e:
        logger.error(f"Error uploading to S3: {e}")