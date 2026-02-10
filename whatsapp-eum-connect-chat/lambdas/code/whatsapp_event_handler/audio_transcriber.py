import json
import os
import logging
import boto3
from botocore.config import Config


logger = logging.getLogger()
lambda_client = boto3.client('lambda', config=Config(
    read_timeout=300,
    connect_timeout=10
))

def transcribe_audio(location: str) -> str:
    """
    Invoke the transcribe lambda to transcribe an audio file.
    
    Args:
        location: S3 URI of the audio file to transcribe (e.g., 's3://bucket/path/file.wav')
    
    Returns:
        Transcription text, or None if transcription failed
    """
    transcribe_lambda = os.environ.get('TRANSCRIBE_HANDLER')
    if not transcribe_lambda:
        logger.warning("TRANSCRIBE_HANDLER environment variable not set")
        return None
    try:
        payload = {'location': location}
        logger.info(f"Invoking transcribe lambda with location: {location}")
        
        response = lambda_client.invoke(
            FunctionName=transcribe_lambda,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        logger.info(f"Transcribe lambda response: {result}")
        
        if result.get('statusCode') == 200:
            transcription = result.get('transcription')
            if transcription:
                logger.info(f"Successfully transcribed audio: {transcription}")
                return transcription
            else:
                logger.info("No transcription returned")
                return None
        else:
            logger.error(f"Transcribe lambda failed: {result.get('error')}")
            return None

    except Exception as e:
        logger.error(f"Error invoking transcribe lambda: {str(e)}")
        return None
