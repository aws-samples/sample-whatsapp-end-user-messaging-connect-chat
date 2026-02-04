import json, decimal
import os
import logging

from whatsapp import WhatsappService, WhatsappMessage
from transcribe import TranscribeService
from connections_service import ConnectionsService
from connect_chat_service import ChatService
from config_service import get_secret_value, get_ssm_parameter


logger = logging.getLogger()
logger.setLevel(logging.INFO)

transcribe_service = TranscribeService()

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

    if not file_name:
        file_name = f"file.{get_extension_by_file_type(attach.get('mimeType'))}"

    if attach.get("content"):
        contact = connections.get_contact(message.phone_number)

        if contact and contact.get("connectionToken"):
            # Upload attachment to Connect chat
            kwargs = dict(
                fileContents=file_content,
                fileName=file_name,
                fileType=file_type,
            )
            logger.info(f"Uploading attachment: {file_name} {file_type}")
            attachment_id, error_str = chat.attach_file(**kwargs, ConnectionToken=contact["connectionToken"]) # type: ignore

            if attachment_id:
                logger.info(f"Successfully uploaded attachment: {attachment_id}")
                message.reaction("📎")
            else:
                logger.error(f"Failed to upload attachment: {error_str}")
                message.reaction("❌")
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
        transcription = transcribe_service.transcribe(
            message.attachment.get("location")
        )
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
        logger.info(f"Found existing connection for {message.phone_number}")
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


def process_record(chat, connections, event):
    whatsapp = WhatsappService(event)
    for message in whatsapp.messages:
        process_message(chat, connections, message)


def lambda_handler(event, context):
    print(event)
    connections = ConnectionsService(os.environ.get("TABLE_NAME"))
    config = get_ssm_parameter(os.environ["CONFIG_PARAM_NAME"])


    chat = ChatService(
        instance_id=config.get("instance_id"),
        contact_flow_id=config.get("contact_flow_id"),
        chat_duration_minutes=int(config.get("chat_duration_minutes", 60)),
        topic_arn=os.environ.get("TOPIC_ARN"),
    )

    process_record(chat, connections, event)

    
