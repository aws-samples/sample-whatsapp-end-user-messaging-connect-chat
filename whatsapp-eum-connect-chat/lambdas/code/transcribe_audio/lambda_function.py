import json, decimal
import os
import logging


from transcribe import TranscribeService

logger = logging.getLogger()
logger.setLevel(logging.INFO)

transcribe_service = TranscribeService()


def lambda_handler(event, context):
    print(event)
    location = event.get("location")
    if location:
        logger.info(f"Direct audio processing request for: {location}")
        transcription = transcribe_service.transcribe(location)
        logger.info(f"Transcription result: {transcription}")
        return { "statusCode": 200,"transcription": transcription }

    
