import json
import os
import logging

import boto3
from config_service import  get_ssm_parameter


logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CONFIG_PARAM_NAME = os.environ.get("CONFIG_PARAM_NAME", "")

ssm_client = boto3.client("ssm")
social_client = boto3.client("socialmessaging")


def get_attribute(attributes: dict, name: str) -> dict | None:
    """Return a template text parameter dict if the attribute exists."""
    value = attributes.get(name)
    if value is not None:
        return {"type": "text", "text": value}
    return None


def build_template_parameters(attributes: dict, names: list[str]) -> list[dict]:
    """Iterate over attribute names and build the parameters list, skipping missing ones."""
    parameters = []
    for name in names:
        param = get_attribute(attributes, name)
        if param is not None:
            parameters.append(param)
    return parameters


def get_phone_number(attributes: dict) -> str | None:
    """Return phoneNumber if present, otherwise fall back to whatsapp attribute."""
    return attributes.get("phoneNumber") or attributes.get("whatsapp")


def lambda_handler(event, context):
    """
    Send a WhatsApp template message via AWS End User Messaging Social.

    Reads config from SSM Parameter Store (CONFIG_PARAM_NAME env var).
    Extracts contact attributes from an Amazon Connect event to populate
    template parameters (input1, input2, input3, input4) and resolve
    the destination phone number.
    """
    logger.info(json.dumps(event))

    try:
        if not CONFIG_PARAM_NAME:
            return _error_response("CONFIG_PARAM_NAME environment variable is not set")

        # Load config from SSM
        config = get_ssm_parameter(CONFIG_PARAM_NAME)
        message_payload = config["message"]
        meta_api_version = config.get("META_API_VERSION", "v23.0")
        
        # a chance to overwrite ORIGINATION_PHONE_NUMBER_ID
        origination_phone_number_id = config.get("ORIGINATION_PHONE_NUMBER_ID", os.environ.get("ORIGINATION_PHONE_NUMBER_ID", ""))

        if not origination_phone_number_id:
            return _error_response("ORIGINATION_PHONE_NUMBER_ID is not set")

        # Extract attributes from Amazon Connect event
        attributes = event.get("Details", {}).get("ContactData", {}).get("Attributes", {})

        # Resolve phone number: phoneNumber first, then whatsapp
        phone_number = get_phone_number(attributes)
        if not phone_number:
            return _error_response("No phone number found in contact attributes (phoneNumber or whatsapp)")

        # Build template body parameters from input attributes
        input_names = ["input1", "input2", "input3", "input4"]
        template_params = build_template_parameters(attributes, input_names)

        # Inject phone number and parameters into the message payload
        message_payload["to"] = phone_number

        # Find or create the body component and set parameters
        components = message_payload.get("template", {}).get("components", [])
        body_component = next((c for c in components if c.get("type") == "body"), None)
        if body_component is not None:
            body_component["parameters"] = template_params
        elif template_params:
            components.append({"type": "body", "parameters": template_params})

        template_name = message_payload.get("template", {}).get("name", "")
        logger.info(f"Sending template '{template_name}'")

        response = social_client.send_whatsapp_message(
            originationPhoneNumberId=origination_phone_number_id,
            message=bytes(json.dumps(message_payload), "utf-8"),
            metaApiVersion=meta_api_version,
        )

        message_id = response.get("messageId", "")
        logger.info(f"Message sent successfully. messageId: {message_id}")

        return {
            "result": "OK",
            "messageId": message_id,
        }

    except ssm_client.exceptions.ParameterNotFound:
        logger.error(f"SSM parameter not found: {CONFIG_PARAM_NAME}")
        return _error_response(f"Config parameter not found: {CONFIG_PARAM_NAME}")
    except social_client.exceptions.ValidationException as e:
        logger.error(f"Validation error: {e}")
        return _error_response(str(e))
    except social_client.exceptions.InvalidParametersException as e:
        logger.error(f"Invalid parameters: {e}")
        return _error_response(str(e))
    except social_client.exceptions.ResourceNotFoundException as e:
        logger.error(f"Resource not found: {e}")
        return _error_response(str(e))
    except social_client.exceptions.ThrottledRequestException as e:
        logger.error(f"Throttled: {e}")
        return _error_response(str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return _error_response(str(e))


def _error_response(message: str) -> dict:
    return {
        "result": "ERROR",
        "message": message,
    }
