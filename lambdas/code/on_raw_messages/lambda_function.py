import json, decimal, os, boto3, logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['RAW_MESSAGES_TABLE']) # type: ignore

def lambda_handler(event, context):
    records = event.get("Records", [])
    logger.info(event)

    for record in records:
        sns = record.get("Sns", {})
        sns_message_str = sns.get("Message", "{}")
        sns_message = json.loads(sns_message_str, parse_float=decimal.Decimal)
        webhook_entry = json.loads(sns_message.get("whatsAppWebhookEntry", {}))
        message_context = sns_message.get("context", {})
        
        for change in webhook_entry.get("changes", []):
            value = change.get("value", {})
            field = change.get("field")
            metadata = value.get("metadata", {})
            messaging_product = value.get("messaging_product")
            contacts = value.get("contacts", [])
            
            for message in value.get("messages", []):
                item = message.copy()
                item["context"] = message_context
                item["metadata"] = metadata
                item["messaging_product"] = messaging_product
                item["field"] = field
                
                wa_id = message.get("from")
                contact = next((c for c in contacts if c.get("wa_id") == wa_id), {})
                item["contact"] = contact
                
                table.put_item(Item=item)

    return {'statusCode': 200}