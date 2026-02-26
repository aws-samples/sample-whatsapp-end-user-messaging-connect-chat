# WhatsApp Message Buffering for Amazon Connect


   _Learn how to optimize WhatsApp-to-Amazon Connect integrations by buffering rapid consecutive messages into a single coherent message. This step-by-step guide covers the full architecture using AWS CDK, DynamoDB Streams, AWS Lambda, AWS End User Messaging Social, and Amazon Connect. Reduce costs and deliver a natural conversation experience for your agents. Ideal for teams handling high-volume WhatsApp customer interactions._


![Demo](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/demo_buffer.gif)


When customers reach out via WhatsApp, they rarely send a single message. They type fast: "Hello", "I need help", "with my order", "P12345". Each of those messages triggers a separate webhook event, and without any optimization, each one creates a separate chat message in Amazon Connect. The result? A fragmented conversation, a confused agent, and unnecessary costs.

In this blog, you'll learn how to solve that with a message buffering layer that aggregates rapid consecutive WhatsApp messages into a single, coherent message before forwarding them to Amazon Connect.

Check out the code at [https://github.com/aws-samples](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)


## What you'll build

A buffering layer between AWS End User Messaging Social and Amazon Connect that:

1. Captures incoming WhatsApp messages in a DynamoDB table
2. Uses DynamoDB Streams with a tumbling window to buffer messages
3. Aggregates consecutive text messages from the same sender into one
4. Forwards the combined message to Amazon Connect as a single chat message

The end result: agents see a clean, natural conversation instead of a flood of fragmented messages.

## Architecture

![Architecture Diagram](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/whatsapp-optimization-connect-DynamoDB.drawio.svg)

Here's how it flows:

1. A WhatsApp message arrives via AWS End User Messaging Social and is published to an SNS topic
2. A Lambda function (`on_raw_messages`) stores each message in a DynamoDB table (`raw_messages`)
3. DynamoDB Streams triggers a Lambda function (`message_aggregator`) using a tumbling window as a buffer
4. The aggregator groups, sorts, and concatenates text messages from the same sender
5. The aggregated message is forwarded to the WhatsApp event handler, which creates or updates the Amazon Connect chat session

## The Problem

When users send multiple messages in quick succession:

```
Message 1: Hello
Message 2: I need help
Message 3: with my order
Message 4: P12345
```

Without buffering, each message creates a separate Amazon Connect chat message. This leads to:
- A fragmented conversation that's hard for agents to follow
- Higher costs (each message is billed individually)
- Multiple Lambda invocations downstream

## The Solution: How Buffering Works

### 1. Raw Message Storage

Incoming WhatsApp messages are stored in a DynamoDB table (`raw_messages`) with:

- Partition key: `from` (sender phone number)
- Sort key: `id` (message ID)
- TTL enabled for automatic cleanup
- DynamoDB Streams enabled with a tumbling window

Using `from` as the partition key and `id` as the sort key guarantees that messages from the same user are stored together and fall into the same shard, so they are processed sequentially by the stream.

The Lambda that handles this is straightforward:

```python
def lambda_handler(event, context):
    records = event.get("Records", [])

    for record in records:
        sns = record.get("Sns", {})
        sns_message = json.loads(sns.get("Message", "{}"), parse_float=decimal.Decimal)
        webhook_entry = json.loads(sns_message.get("whatsAppWebhookEntry", {}))

        for change in webhook_entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            contacts = value.get("contacts", [])

            for message in value.get("messages", []):
                item = message.copy()
                item["metadata"] = metadata
                item["messaging_product"] = value.get("messaging_product")

                # Store in DynamoDB
                table.put_item(Item=item)

    return {'statusCode': 200}
```

### 2. Stream Processing with Tumbling Window

The tumbling window is the key to the buffering strategy. DynamoDB Streams triggers the `message_aggregator` Lambda, but instead of invoking it for every single record, the tumbling window waits a configurable number of seconds (default: 20) before invoking the function with all accumulated records in that window.

Each shard invokes one Lambda, so messages from the same user within that window are processed altogether.

### 3. Aggregation Logic

The aggregator groups messages by sender, sorts them by timestamp, and concatenates consecutive text messages with newlines. Non-text messages (images, audio, documents, etc.) are preserved as separate items.

```
Input:
  Message 1: Hello
  Message 2: I need help
  Message 3: with my order
  Message 4: P12345

Output (single aggregated message):
  Hello
  I need help
  with my order
  P12345
```

The core aggregation logic:

```python
def lambda_handler(event, context):
    raw_records = event.get("Records", [])

    records = []
    for record in raw_records:
        if record.get("eventName") == "INSERT":
            new_image = record.get("dynamodb", {}).get("NewImage", {})
            deserialized = deserialize_dynamodb(new_image)
            records.append(deserialized)

    if len(records) == 0:
        return {"state": event.get('state', {})}

    aggregated = aggregate_all_messages(records)

    # Forward each aggregated message to the WhatsApp event handler
    for agg in aggregated:
        lambda_client.invoke(
            FunctionName=os.environ['WHATSAPP_EVENT_HANDLER'],
            InvocationType='Event',
            Payload=json.dumps(agg)
        )

    return {"state": event.get('state', {})}
```

### 4. Forwarding to Amazon Connect

Once aggregated, the Lambda asynchronously invokes the WhatsApp event handler, which creates or updates the Amazon Connect chat session with the combined message. The agent sees one clean message instead of four separate ones.

### Benefits

- **Natural conversation flow**: Multiple rapid messages appear as one coherent message
- **Cost optimization**: Fewer messages downstream means lower Amazon Connect chat costs
- **Automatic cleanup**: TTL removes old raw messages automatically
- **Scalable**: DynamoDB Streams handles high throughput (up to 10,000 records per stream)
- **Reliable**: Stream processing ensures no messages are lost (at-least-once delivery)

## Cost Estimation

Example scenario: 1,000 raw messages aggregated into 250 messages (4:1 ratio assumption). Messages are answered by a human agent.

| Component | Without Buffering | With Buffering | Savings |
|---|---|---|---|
| DynamoDB + Streams | — | ~$0.0013 | — |
| Lambda (all functions) | — | ~$0.00078 | — |
| Buffering Infrastructure | $0.00 | ~$0.002 | — |
| Inbound API Calls | 1,000 calls | 250 calls | 75% fewer calls |
| Connect Chat (In) Cost | $4.00 | $1.00 | $3.00 |
| **Total** | **$4.00** | **~$1.00** | **~$3.00 (75%)** |


Note the whole cost considers connect in and out as well EUM in and out. Here we are only reducing Amazon Connect Chat in messages.

- *Connect Chat cost: $0.004 × msg (in) + $0.004 × msg (out). [See pricing](https://aws.amazon.com/connect/pricing/)*
- *EUM cost: $0.005 × msg (in) + $0.005 × msg (out). [See pricing](https://aws.amazon.com/end-user-messaging/pricing/)*

## Prerequisites

Before getting started you'll need:

### WhatsApp Business Account

To get started, you need to create a new WhatsApp Business Account (WABA) or migrate an existing one to AWS. The main steps are described [here](https://docs.aws.amazon.com/social-messaging/latest/userguide/getting-started.html). In summary:

1. Have or create a Meta Business Account
2. Access the AWS End User Messaging Social console and link your business account through the embedded Facebook portal
3. Make sure you have a phone number that can receive SMS/voice verification and add it to WhatsApp

⚠️ Important: Do not use your personal WhatsApp number for this.

### An Amazon Connect Instance

You need an Amazon Connect instance. If you don't have one yet, you can [follow this guide](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-instances.html) to create one.

You'll need the **INSTANCE_ID** of your instance. You can find it in the Amazon Connect console or in the instance ARN:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID`

### A Chat Flow to Handle Messages

Create or have ready the contact flow that defines the user experience. [Follow this guide](https://docs.aws.amazon.com/connect/latest/adminguide/create-contact-flow.html) to create an Inbound Contact Flow. The simplest one will work.

Remember to publish the flow.

![Simple Flow](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/flow_simple.png)

Take note of the **INSTANCE_ID** and **CONTACT_FLOW_ID** from the Details tab. The values are in the flow ARN:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID/contact-flow/CONTACT_FLOW_ID`

## Deploying with AWS CDK

⚠️ Deploy in the same region where your AWS End User Messaging WhatsApp numbers are configured.

### 1. Clone the repository and navigate to the project

```bash
git clone https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat.git
cd sample-whatsapp-end-user-messaging-connect-chat/whatsapp-eum-connect-chat
```

### 2. Deploy with CDK

Follow the instructions in the [CDK Deployment Guide](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_cdk_deploy.md).

## Post-deployment Configuration

### Step 1: Update the SSM Parameter

After deployment, update the SSM parameter `/whatsapp_eum_connect_chat/config` with your Amazon Connect details:

```json
{
  "instance_id": "<your-connect-instance-id>",
  "contact_flow_id": "<your-contact-flow-id>",
  "chat_duration_minutes": 60,
  "ignore_reactions": "yes",
  "ignore_stickers": "yes"
}
```

| Parameter | Description |
|---|---|
| `instance_id` | Your Amazon Connect Instance ID |
| `contact_flow_id` | The ID of the Inbound Contact Flow for chat |
| `chat_duration_minutes` | How long the chat session stays active (default: 60) |
| `ignore_reactions` | Whether to ignore WhatsApp reactions (default: yes) |
| `ignore_stickers` | Whether to ignore WhatsApp stickers (default: yes) |

### Step 2: Add the Event Destination

After deploying the stack, use the created SNS topic as your event destination in the AWS End User Messaging Social console.

1. Go to AWS Systems Manager Parameter Store and copy the value of `/whatsapp_eum_connect_chat/topic/in` (it starts with `arn:aws:sns`)

![Topic Parameter](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/topic_parameter.png)

2. In the AWS End User Messaging Social console, select destination **Amazon SNS** and paste the **Topic ARN** from the previous step

![SNS EUM Configuration](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/SNS_EUM.png)

### Step 3: Adjust the Buffer Time (Optional)

The default buffer window is 20 seconds. If you want to change it, edit `BUFFER_IN_SECONDS` in [`config.py`](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/whatsapp-eum-connect-chat/config.py) and redeploy:

```python
BUFFER_IN_SECONDS = 20  # Change this value (in seconds)
```

## Testing

Go to your Amazon Connect instance and [open the Contact Control Panel (CCP)](https://docs.aws.amazon.com/connect/latest/adminguide/launch-ccp.html). Send a WhatsApp message to the End User Messaging Social number.

Try sending a rapid sequence of messages and see how they arrive as a single aggregated message in Amazon Connect.

<div align="center">
<video src="https://github.com/user-attachments/assets/652683f2-5a5c-4a35-ad82-c80f0f3fe275" width="540" controls></video>
</div>

## Next Steps

This solution is a starting point. Some ideas to extend it:

- Adjust the buffer window based on your use case (shorter for real-time, longer for cost savings)
- Add a Dead Letter Queue for failed stream processing
- Implement custom aggregation logic for specific message types (e.g., group images together)
- Combine with the [Agent-Initiated WhatsApp](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/agent-initiated-whatsapp) solution for full bidirectional communication

## Resources

- [Project Repository](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)
- [Amazon Connect Administrator Guide](https://docs.aws.amazon.com/connect/latest/adminguide/what-is-amazon-connect.html)
- [Amazon Connect API Reference](https://docs.aws.amazon.com/connect/latest/APIReference/Welcome.html)
- [AWS End User Messaging Social User Guide](https://docs.aws.amazon.com/social-messaging/latest/userguide/what-is-service.html)
- [DynamoDB Streams Developer Guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html)
- [DynamoDB Streams and Lambda Tumbling Windows](https://docs.aws.amazon.com/lambda/latest/dg/with-ddb.html)
