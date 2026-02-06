import json
import os
import logging
import boto3

logger = logging.getLogger()
lambda_client = boto3.client('lambda')


def convert_to_wav(location: str) -> str:
    """
    Invoke the converter lambda to convert audio file to WAV format.
    
    Args:
        location: S3 URI of the file to convert (e.g., 's3://bucket/path/file.ogg')
    
    Returns:
        S3 URI of the converted WAV file, or original location if conversion not needed/failed
    """
    converter_lambda = os.environ.get('CONVERT_WAV_HANDLER')
    if not converter_lambda:
        logger.warning("CONVERT_WAV_HANDLER environment variable not set")
        return None
    try:
        payload = {'location': location}
        logger.info(f"Invoking converter lambda with location: {location}")
        
        response = lambda_client.invoke(
            FunctionName=converter_lambda,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        logger.info(f"Converter lambda response: {result}")
        
        if result.get('statusCode') == 200:
            converted_location = result.get('converted_location')
            if converted_location:
                logger.info(f"Successfully converted to: {converted_location}")
                return converted_location
            else:
                logger.info("File did not require conversion")

        else:
            logger.error(f"Converter lambda failed: {result.get('error')}")
            return None

    except Exception as e:
        logger.error(f"Error invoking converter lambda: {str(e)}")
        return None
