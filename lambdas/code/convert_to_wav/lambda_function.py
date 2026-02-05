import json
import os
import subprocess
import boto3
import logging
from urllib.parse import urlparse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

tmp_path = "/tmp"


def run_ffmpeg_command(command: list) -> tuple:
    try:
        print(command)
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def parse_location(s3_uri):
    """Parse S3 URI and return bucket, prefix, fileName, extension, file"""
    parsed = urlparse(s3_uri)
    bucket = parsed.netloc
    full_path = parsed.path.lstrip('/')
    
    # Split path into prefix and file
    parts = full_path.rsplit('/', 1)
    if len(parts) == 2:
        prefix, file = parts
    else:
        prefix = ''
        file = parts[0]
    
    # Split filename and extension
    fileName, extension = os.path.splitext(file)
    extension = extension.lstrip('.')
    
    return bucket, prefix, fileName, extension, file


def download_file(bucket, key, local_path):
    """Download file from S3 to local path"""
    s3_client = boto3.client('s3')
    s3_client.download_file(bucket, key, local_path)
    print(f"Downloaded s3://{bucket}/{key} to {local_path}")


def upload_file(local_path, bucket, key):
    """Upload file from local path to S3"""
    s3_client = boto3.client('s3')
    s3_client.upload_file(local_path, bucket, key)
    print(f"Uploaded {local_path} to s3://{bucket}/{key}")


def convert_ogg_to_wav(input_file, output_file):
    """Convert OGG to WAV using ffmpeg"""
    ffmpeg_path = 'ffmpeg'
    
    command = [
        ffmpeg_path, '-i', input_file,
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        output_file
    ]
    
    return_code, stdout, stderr = run_ffmpeg_command(command)
    print(f"code: {return_code}, stdout: {stdout}, stderr: {stderr}")
    
    return return_code == 0


def lambda_handler(event, context):
    print(event)
    
    s3_uri = event.get('location', '')
    if not s3_uri:
        return {'statusCode': 400, 'error': 'No location provided'}
    
    bucket, prefix, fileName, extension, file = parse_location(s3_uri)
    
    # Check if file is OGG
    if extension.lower() != 'ogg':
        print(f"File is not OGG (extension: {extension}), skipping conversion")
        return {
            'statusCode': 200,
            'location': s3_uri,
            'converted_location': None
        }
    
    # Download OGG file
    location = f"{prefix}/{file}" if prefix else file
    local_ogg = f"{tmp_path}/{file}"
    print(f"Downloading {file} from s3://{bucket}/{location} to {local_ogg}")
    download_file(bucket, location, local_ogg)
    
    # Convert to WAV
    wav_file = f"{fileName}.wav"
    local_wav = f"{tmp_path}/{wav_file}"
    
    success = convert_ogg_to_wav(local_ogg, local_wav)
    
    if not success:
        return {
            'statusCode': 500,
            'error': 'ffmpeg conversion failed'
        }
    
    # Upload WAV to S3
    wav_location = f"{prefix}/{wav_file}" if prefix else wav_file
    upload_file(local_wav, bucket, wav_location)
    
    # Clean up temp files
    os.remove(local_ogg)
    os.remove(local_wav)
    
    # Return both locations
    converted_location = f"s3://{bucket}/{wav_location}"
    
    return {
        'statusCode': 200,
        'location': s3_uri,
        'converted_location': converted_location
    }
