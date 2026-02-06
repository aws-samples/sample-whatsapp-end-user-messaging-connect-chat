import json, decimal, logging, os, boto3
from process_stream import deserialize_dynamodb, aggregate_all_messages

logger = logging.getLogger()
logger.setLevel(logging.INFO)
lambda_client = boto3.client('lambda')


def lambda_handler(event, context):
    raw_records = event.get("Records", [])
    state = event.get('state', {})

    logger.info("raw_records: %s", raw_records)
    
    records = []
    for record in raw_records:
        if record.get("eventName") == "INSERT":
            dynamodb_data = record.get("dynamodb", {})
            new_image = dynamodb_data.get("NewImage", {})
            deserialized = deserialize_dynamodb(new_image)
            records.append(deserialized)
    
    if len(records) == 0:
        return {"state": state}
    logger.info("records: %s", records)
    
    aggregated = aggregate_all_messages(records)
    logger.info("aggregated: %s", aggregated)
    
    handler_name = os.environ['WHATSAPP_EVENT_HANDLER']
    for agg in aggregated:
        lambda_client.invoke(
            FunctionName=handler_name,
            InvocationType='Event',
            Payload=json.dumps(agg)
        )
    
    return {"state": state}