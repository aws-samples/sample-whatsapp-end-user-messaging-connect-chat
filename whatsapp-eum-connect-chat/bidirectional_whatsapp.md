# Bidirectional WhatsApp – Amazon Connect Chat

Complete two-way messaging between WhatsApp and Amazon Connect chat. Handles inbound customer messages and outbound agent responses with proper session management, attachment and voice notes handling.

## Prerequisites

Besides this deployment, to be able to test bidirectional communication with a user in Whatsapp, you will need:

- A WhatsApp Business Account in AWS End User Messaging
- An Amazon Connect Instance (INSTANCE_ID)
- A Chat Inbound Flow (CONTACT_FLOW_ID)

For the detailed instructions follow the [prerequisites guide](../general_connect_eum.md)

## Architecture

![Architecture Diagram](./whatsapp-connect-bidirectional-chat.drawio.svg)

## How It Works

The solution bridges WhatsApp End User Messaging and Amazon Connect Chat through two event-driven paths — one for each direction — connected by a shared DynamoDB connections table and SNS topics.

### Inbound: WhatsApp → Amazon Connect

When a customer sends a message on WhatsApp:

1. **WhatsApp End User Messaging** publishes the event to an SNS topic.
2. The message is buffered through DynamoDB (see [README](./README.md) for buffering details) and after pre-processing forwarded to the `Inbound Handler` Lambda.
3. The handler checks the connections table for an existing chat session:
   - **Existing session** — sends the message to Amazon Connect using the stored `connectionToken`.
   - **No session** — calls `StartChatContact` to create a new chat, starts contact streaming, creates a participant connection, and stores the session in DynamoDB.
4. Attachments (images, documents, audio) are uploaded to the Connect chat via the Participant API. Audio files, originally ogg, are converted to .wav ([supported as attachment in amazon connect chat](https://docs.aws.amazon.com/connect/latest/adminguide/feature-limits.html)) and transcribed using Amazon Transcribe.

### Outbound: Amazon Connect → WhatsApp

When an amazon connect (Human agent or AI agent) replies in Amazon Connect:

1. **Contact streaming** publishes the oubound message to SNS topic.
2. The `Connect Responses` Lambda receives the SNS record.
3. It looks up the customer's phone number and system number from the connections table using the `contactId`.
4. It sends the reply back to WhatsApp through the Social Messaging API (`SendWhatsAppMessage`).
5. Attachments from the agent are fetched via a signed URL and forwarded as WhatsApp media messages (image, video, audio, or document).
6. In event of disconnection from Amazon Connect (end chat), that record from connections table is deleted.

### Session Management

A DynamoDB table (`active_connections`) tracks every open conversation:

| Field | Purpose |
|---|---|
| `contactId` (PK) | Amazon Connect contact identifier |
| `customerId` (GSI) | Customer phone number, used for lookups on inbound messages |
| `connectionToken` | Participant connection token for sending messages and attachments |
| `participantToken` | Token used to create the participant connection |
| `systemNumber` | WhatsApp phone number ID used to send outbound replies |
| `channel` | Originating channel (e.g., `Whatsapp`) |
| `name` | Customer display name |

When a chat session expires or the participant leaves, the connection can be cleaned up so the next inbound message starts a fresh session.



### Message Types Supported

| Direction | Text | Images | Documents | Audio | Reactions |
|---|---|---|---|---|---|
| Inbound (customer → agent) | ✅ | ✅ | ✅ | ✅ (transcribed) | Configurable |
| Outbound (agent → customer) | ✅ | ✅ | ✅ | - | — |

Inbound Handler can be extended to include LLM preprocessing, other media analysis (videos, images multimodal understanding) before arriving to Amazon Connect.
## Deployment

⚠️ Important: Deploy in the same region as your AWS End User Messaging Whatsapp Numbers.

1. Clone the repository and navigate to the project folder

```bash
git clone https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat.git
cd sample-whatsapp-end-user-messaging-connect-chat/whatsapp-eum-connect-chat
```

2. Deployment instructions, follow [CDK Deployment Guide](../general_cdk_deploy.md).


## After deployment Configuration

After deployment, update the SSM parameter `/whatsapp_eum_connect_chat/config` with your Amazon Connect details:

```json
{
  "instance_id": "<your-connect-instance-id>",
  "contact_flow_id": "<your-contact-flow-id>",
  "chat_duration_minutes": 60,
  "ignore_reactions": "yes",
  "ignore_stickers": "yes",
}
```

### Add the event destination 

After deploying the stack, use the created SNS topic as your event destination in AWS End user messaging social console. The specific arn will SSM parameter `/whatsapp_eum_connect_chat/topic/in`. Copy the value of the parameter (it start with `arn:aws:sns`)
![](./topic_parameter.png)

AWS End user messaging social console, select destination **Amazon SNS** and paste the **Topic ARN** from previous step:
![](SNS_EUM.png)


If you want to change the buffer time, edit `BUFFER_IN_SECONDS` in [`config.py`](./config.py) and redeploy. 


## Test whatsapp communication

In order to test, go to your Amazon Connect Instance and [Open Contact control Panel (CCP)](https://docs.aws.amazon.com/connect/latest/adminguide/launch-ccp.html) and send a Whatsapp Message to the EUM Social number.

Try with voice notes, photos, files and see how they arrives to Amazon connect. Also try sending a file from the Agent to the user.

_(personal phone number blurred)_

![](demo_blurred.gif)

