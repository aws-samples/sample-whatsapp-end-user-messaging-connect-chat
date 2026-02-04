TOPIC_PARAM_NAME = "/whatsapp_eum_connect_chat/topic/in"

CONFIG_PARAM_NAME = "/whatsapp_eum_connect_chat/config"

#update this after deployment in aws parameter store /whatsapp/config
CONFIG_PARAM_INITIAL_CONTENT = {
    "instance_id": "INSTANCE_ID",
    "contact_flow_id": "CONTACT_FLOW_ID",
    "chat_duration_minutes": 60,
    "ignore_reactions": "yes",
    "ignore_stickers": "yes",
    "buffer_in_seconds": 20,
}

BUFFER_IN_SECONDS = 20
META_API_VERSION = "v23.0"
