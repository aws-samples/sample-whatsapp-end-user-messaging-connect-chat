import boto3
import json
import os
import re
socialessaging = boto3.client("socialmessaging")

META_API_VERSION = os.environ.get("META_API_VERSION","v24.0" )

# A phone number destination is only digits, optionally prefixed with "+".
PHONE_NUMBER_PATTERN = re.compile(r"^\+?\d+$")


def get_recipient(destination):
    """Destination field for a send_whatsapp_message payload.

    active_connections stores whatever identified the customer: a WhatsApp
    user_id (e.g. "US.XXXXXXXXXXXXXXX") or a phone number. user_id
    destinations are addressed with "recipient", phone numbers with "to".

    NOTE: the identity mode is inferred from the *shape* of the stored value,
    because active_connections keeps a single customerId and not the mode it
    came from. The inference holds today — a BSUID always starts with an ISO
    3166 alpha-2 country code plus a period, which a phone number never does —
    but it is still an inference. The inbound side does not need it: see
    WhatsappMessage.get_recipient in whatsapp_event_handler/whatsapp.py, which
    branches on the presence of from_user_id in the webhook itself.

    A more robust option: persist the identity mode alongside the session.
    Store from_user_id as its own attribute in active_connections (next to the
    customerId used as the lookup key) and read that attribute here instead of
    pattern-matching the string. That also frees from_phone_number to enrich
    the customer profile when Meta does share the number.
    """
    destination = str(destination or "").strip()
    if not destination:
        return {}
    if PHONE_NUMBER_PATTERN.match(destination):
        return {"to": f"+{destination.lstrip('+')}"}
    return {"recipient": destination}


def get_file_category(mime_type):
    # Map MIME types to WhatsApp file categories
    if mime_type.startswith("image/"):
        return "image"
    elif mime_type.startswith("video/"):
        return "video"
    elif mime_type.startswith("audio/"):
        return "audio"
    else:
        # Default to document for all other types (PDF, Office docs, etc.)
        return "document"


def send_whatsapp_text(text_message, to, phone_number_id, meta_api_version=META_API_VERSION):
    print("sending message...")
    message_object = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": "text",
        "text": {"preview_url": False, "body": text_message},
    }
    message_object.update(get_recipient(to))

    kwargs = dict(
        originationPhoneNumberId=phone_number_id,
        metaApiVersion=meta_api_version,
        message=bytes(json.dumps(message_object), "utf-8"),
    )
    print(kwargs)
    response = socialessaging.send_whatsapp_message(**kwargs)
    print("replied to message:", response)


def send_whatsapp_attachment(
    attachment_url,
    mime_type,
    name,
    to,
    phone_number_id,
    meta_api_version=META_API_VERSION,
):
    print("sending attachment...")
    message_type = get_file_category(mime_type)
    message_object = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": message_type,
    }
    message_object.update(get_recipient(to))
    message_object[message_type] = {"link": attachment_url}
    if message_type == "document":
        message_object[message_type]["filename"] = name

    kwargs = dict(
        originationPhoneNumberId=phone_number_id,
        metaApiVersion=meta_api_version,
        message=bytes(json.dumps(message_object), "utf-8"),
    )
    # print(kwargs)
    response = socialessaging.send_whatsapp_message(**kwargs)
    print("attachment response:", response)
