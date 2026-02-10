import json, decimal
import os
import logging
import boto3

from whatsapp import WhatsappService, WhatsappMessage
from connections_service import ConnectionsService
from connect_chat_service import ChatService
from config_service import get_secret_value, get_ssm_parameter
from audio_converter import convert_to_wav
from audio_transcriber import transcribe_audio

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_extension_by_file_type(file_type):
    if "jpeg" in file_type: return "jpeg"
    if "png" in file_type: return "png"
    return "unknown"


def process_attachment(chat:ChatService, connections, message):
    contact = connections.get_contact(message.phone_number)

    attach = message.attachment
    logger.info(f"Processing attachment: location={attach.get('location')}, mime_type={attach.get('mime_type')}, mimeType={attach.get('mimeType')}, filename={attach.get('filename')}")
    file_type = attach.get("mime_type")
    file_content = attach.get("content")
    file_name = attach.get("filename")
    audio = message.message.get("audio")

    if audio:
        file_name = "voice.ogg"
        converted_location = convert_to_wav(attach.get("location"))
        if converted_location:
            print(f"converted location: {converted_location}")
            file_content = message.get_s3_file_content(converted_location)
            file_name = "voice.wav"
            file_type = "audio/wav"



    if not file_name:
        file_name = f"file.{get_extension_by_file_type(attach.get('mimeType'))}"

    if attach.get("content"):
        contact = connections.get_contact(message.phone_number)

        if contact and contact.get("connectionToken"):
            logger.info(f"Uploading attachment: {file_name} {file_type}")
            attachment_id, error_str = chat.attach_file_with_retry_connection(
                message=message,
                connections=connections,
                fileContents=file_content,
                fileName=file_name,
                fileType=file_type,
                connectionToken=contact["connectionToken"],
            )

            if attachment_id:
                logger.info(f"Successfully uploaded attachment: {attachment_id}")
                message.reaction("📎")
            else:
                logger.error(f"Failed to upload attachment: {error_str}")
                message.reaction("❌")
                # Refresh contact in case connection was renewed
                contact = connections.get_contact(message.phone_number)
                if contact and contact.get("connectionToken"):
                    chat.send_message(f"[{error_str}]", contact["connectionToken"])
    else:
        logger.error("Failed to retrieve attachment content")
        message.reaction("❌")
        chat.send_message(
            "Failed to retrieve attachment content", contact["connectionToken"]
        )

    if audio and message.attachment.get("location"):  # it's been downloaded
        logger.info("Transcribing audio")


        # transcribe using Amazon Transcribe
        transcription = transcribe_audio( message.attachment.get("location"))
        message.add_transcription(transcription)


def process_message(chat: ChatService, connections:ConnectionsService, message:WhatsappMessage):
    message.mark_as_read()
    message.reaction("👀")
    if message.attachment and message.attachment.get("location"):
        process_attachment(chat, connections, message)

    # An existing conversation with Amazon Connect Chat
    contact = connections.get_contact(message.phone_number)

    # Get message text content
    text = message.get_text()

    if message.transcription:
        # Reply the transcription to the user
        message.text_reply(f"🔊_{message.transcription}_")
        text = message.transcription

    customer_name = message.message.get("customer_name", "NN")
    newContactId = None

    if contact:
        logger.info(f"Found existing connection for Phone Number...")
        if text:
            newContactId, newParticipantToken, newConnectionToken = (
                chat.send_message_with_retry_connection(
                    text, message, contact["connectionToken"]
                )
            )
            if newContactId: connections.remove_contactId(contact["contactId"])

    else:
        logger.info("Creating new contact")
        newContactId, newParticipantToken, newConnectionToken = chat.start_chat_and_stream(
            text or "New conversation with attachment",
            message.phone_number,
            "Whatsapp",
            customer_name,
            message.phone_number_id,
        )
    
    if newContactId:
        connections.update_contact(
            message.phone_number,
            "Whatsapp",
            newContactId,
            newParticipantToken,
            newConnectionToken,
            customer_name,
            message.phone_number_id,
        )

    message.reaction("✅")


def process_record(chat, connections, event, ignore_stickers=True, ignore_reactions=True):
    whatsapp = WhatsappService(event, ignore_reactions, ignore_stickers)
    for message in whatsapp.messages:
        process_message(chat, connections, message)


def lambda_handler(event, context):
    print(event)
    connections = ConnectionsService(os.environ.get("TABLE_NAME"))
    config = get_ssm_parameter(os.environ["CONFIG_PARAM_NAME"])

    INSTANCE_ID = config.get("instance_id")
    CONTACT_FLOW_ID = config.get("contact_flow_id")
    IGNORE_REACTIONS = True if config.get("ignore_reactions") == "yes" else False
    IGNORE_STICKERS = True if config.get("ignore_stickers") == "yes" else False
    CHAT_DURATION_MINUTES = int(config.get("chat_duration_minutes", 60))

    if not INSTANCE_ID or not CONTACT_FLOW_ID:
        logger.error("INSTANCE_ID and CONTACT_FLOW_ID must be set in environment variables")
        return {"statusCode": 200, "body": "Missing required configuration"}


    chat = ChatService( instance_id=INSTANCE_ID, contact_flow_id=CONTACT_FLOW_ID, chat_duration_minutes=CHAT_DURATION_MINUTES, topic_arn=os.environ.get("TOPIC_ARN"))

    process_record(chat, connections, event,ignore_stickers=IGNORE_STICKERS, ignore_reactions=IGNORE_REACTIONS)

    
