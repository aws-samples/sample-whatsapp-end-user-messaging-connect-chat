import json
import os
import re
import shutil
import subprocess  # nosec B404 - subprocess required for ffmpeg invocation; inputs validated via _validate_path
import tempfile
import boto3
import logging
from urllib.parse import urlparse

logger = logging.getLogger()
logger.setLevel(logging.INFO)




ALLOWED_FILENAME_PATTERN = re.compile(r'^[\w\-. ]+$')


def _validate_path(path: str) -> str:
    """Validate that a file path is safe for use in subprocess commands."""
    filename = os.path.basename(path)
    if not ALLOWED_FILENAME_PATTERN.match(filename):
        raise ValueError(f"Invalid characters in filename: {filename}")
    # Resolve to absolute and ensure it stays under /tmp
    resolved = os.path.realpath(path)
    if not resolved.startswith("/tmp/"):  # nosec B108 - Lambda only provides /tmp as writable space; this is an intentional jail check
        raise ValueError(f"Path escapes temp directory: {resolved}")
    return resolved


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
    safe_input = _validate_path(input_file)
    safe_output = _validate_path(output_file)

    # Using list form (not shell=True) so each element is passed as a discrete
    # argv entry — no shell expansion or injection is possible.  Paths are
    # already validated by _validate_path (allowlist regex + /tmp jail).
    command = [
        'ffmpeg', '-i', safe_input,
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        safe_output,
    ]
    logger.info("Running ffmpeg command: %s", command)

    result = subprocess.run(  # nosemgrep: dangerous-subprocess-use-audit  # nosec B603
        command,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print(f"code: {result.returncode}, stdout: {result.stdout}, stderr: { result.stderr}")
    
    return result.returncode == 0


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
    tmp_dir = tempfile.mkdtemp()

    try:
        local_ogg = os.path.join(tmp_dir, file)
        print(f"Downloading {file} from s3://{bucket}/{location} to {local_ogg}")
        download_file(bucket, location, local_ogg)

        # Convert to WAV
        wav_file = f"{fileName}.wav"
        local_wav = os.path.join(tmp_dir, wav_file)

        success = convert_ogg_to_wav(local_ogg, local_wav)

        if not success:
            return {
                'statusCode': 500,
                'error': 'ffmpeg conversion failed'
            }

        # Upload WAV to S3
        wav_location = f"{prefix}/{wav_file}" if prefix else wav_file
        upload_file(local_wav, bucket, wav_location)

        # Return both locations
        converted_location = f"s3://{bucket}/{wav_location}"

        return {
            'statusCode': 200,
            'location': s3_uri,
            'converted_location': converted_location
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
