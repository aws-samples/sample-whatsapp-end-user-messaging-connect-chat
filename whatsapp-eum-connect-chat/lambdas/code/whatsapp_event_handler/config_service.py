import json
import logging
import boto3
from typing import Dict, Any

logger = logging.getLogger()


def get_ssm_parameter(parameter_name: str) -> Dict[str, Any]:
    """
    Retrieve and parse SSM parameter value.
    
    Args:
        parameter_name: Name of the SSM parameter
        
    Returns:
        Dict containing the parsed JSON configuration
        
    Raises:
        ValueError: If parameter name is empty or parameter value is invalid JSON
        Exception: If SSM parameter retrieval fails
    """
    if not parameter_name:
        raise ValueError("Parameter name cannot be empty")
    
    try:
        ssm_client = boto3.client('ssm')
        logger.info(f"Retrieving SSM parameter: {parameter_name}")
        
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        
        parameter_value = response['Parameter']['Value']
        
        # Parse JSON
        try:
            config = json.loads(parameter_value)
            logger.info(f"Successfully parsed SSM parameter: {parameter_name}")
            return config
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in SSM parameter {parameter_name}: {str(e)}")
            raise ValueError(f"SSM parameter contains invalid JSON: {str(e)}")
            
    except ssm_client.exceptions.ParameterNotFound:
        logger.warning(f"SSM parameter not found: {parameter_name}")
        raise Exception(f"SSM parameter not found: {parameter_name}")
        
    except Exception as e:
        logger.warning(f"Failed to retrieve SSM parameter {parameter_name}: {str(e)}")
        raise Exception(f"Failed to retrieve SSM parameter: {str(e)}")


def get_secret_value(secret_arn: str) -> str:
    """
    Retrieve secret value from AWS Secrets Manager.
    
    Args:
        secret_arn: ARN of the secret
        
    Returns:
        String containing the secret value (access token)
        
    Raises:
        ValueError: If secret ARN is empty
        Exception: If secret retrieval fails
    """
    if not secret_arn:
        raise ValueError("Secret ARN cannot be empty")
    
    try:
        secrets_client = boto3.client('secretsmanager')
        logger.info(f"Retrieving secret: {secret_arn}")
        
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        
        # Secret can be in SecretString or SecretBinary
        if 'SecretString' in response:
            secret = response['SecretString']
            # Try to parse as JSON if it's a JSON secret
            try:
                secret_dict = json.loads(secret)
                # If it's a dict, look for common key names
                if isinstance(secret_dict, dict):
                    # Try common key names for access tokens
                    for key in ['access_token', 'token', 'api_key', 'apiKey']:
                        if key in secret_dict:
                            logger.info("Successfully retrieved secret value")
                            return secret_dict[key]
                    # If no common key found, return the first value
                    if secret_dict:
                        logger.info("Successfully retrieved secret value (first dict value)")
                        return list(secret_dict.values())[0]
            except json.JSONDecodeError:
                # Not JSON, return as-is
                pass
            
            logger.info("Successfully retrieved secret value")
            return secret
        else:
            # Binary secret
            logger.info("Successfully retrieved binary secret value")
            return response['SecretBinary'].decode('utf-8')
            
    except secrets_client.exceptions.ResourceNotFoundException:
        logger.warning(f"Secret not found: {secret_arn}")
        raise Exception(f"Secret not found: {secret_arn}")
        
    except Exception as e:
        logger.warning(f"Failed to retrieve secret {secret_arn}: {str(e)}")
        raise Exception(f"Failed to retrieve secret: {str(e)}")
