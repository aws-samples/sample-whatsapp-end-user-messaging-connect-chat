# Handling Attachments (and voice notes) between Whatsapp and Amazon Connect. 

   _Learn how to handle file attachments in both directions between WhatsApp and Amazon Connect — images, documents, audio, and video. This step-by-step guide covers the full architecture using AWS CDK, AWS Lambda, AWS End User Messaging Social, Amazon S3, and Amazon Connect. From downloading WhatsApp media to uploading it into Connect Chat, forwarding agent files back to WhatsApp, and processing voice notes with format conversion and real-time transcription using Amazon Transcribe._


![Demo](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/demo_attachments.gif)


Text messages are just the beginning. Customers send photos of damaged products, PDFs of invoices, voice notes explaining their issue, and sometimes even videos. If your WhatsApp integration with Amazon Connect only handles text, you're missing a huge part of the conversation.

In this blog, you'll learn how to handle file attachments in both directions — customer to agent and agent to customer — including a pipeline for converting and transcribing voice notes. This enables advanced use cases like insurance claims with photo evidence, voice instructions transcribed for the agent, and document exchange without leaving the chat.

Check out the code at [https://github.com/aws-samples](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)


## What you'll build

A bidirectional attachment handling layer between WhatsApp and Amazon Connect that:

1. Detects and downloads media from incoming WhatsApp messages (images, documents, audio, video)
2. Converts WhatsApp voice notes (OGG/Opus) to WAV for Connect compatibility
3. Transcribes voice notes in real time using Amazon Transcribe Streaming
4. Add those files into the Amazon Connect Chat session so agents can see them
5. Forwards files sent by agents from the Connect Chat widget back to WhatsApp


The end result: agents and customers can exchange files naturally, and voice notes arrive both as playable audio and as readable text.

## Architecture

![Architecture Diagram](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/attach_arqui.png)

Here's how it flows:

1. A customer sends a file or media on WhatsApp. The inbound handler Lambda downloads it to S3 using AWS SDK.
2. If the file is a voice note (OGG), it's converted to WAV using ffmpeg in a separate Lambda
3. The file is uploaded to the Amazon Connect Chat session via the Participant API
4. When an agent sends a file from the Connect Chat widget, the outbound handler detects the `ATTACHMENT` event
5. The handler retrieves a signed URL for the file and sends it to WhatsApp as a media message

## Understanding WhatsApp Message Types

WhatsApp messages aren't just text. The webhook payload from Meta includes a `type` field that tells you what kind of content the customer sent. Each media type carries its content in a dedicated field within the message object:

| Type | Field | Description |
|---|---|---|
| `text` | `text` | Plain text message |
| `image` | `image` | Photos, screenshots, memes |
| `document` | `document` | PDFs, spreadsheets, Word docs |
| `audio` | `audio` | Voice notes (OGG/Opus format) |
| `video` | `video` | Video clips |
| `sticker` | `sticker` | WhatsApp stickers |
| `reaction` | `reaction` | Emoji reactions to messages |



Not all of these are useful in a customer service context. Stickers and reactions typically add noise rather than value, so the solution makes them configurable — you can ignore them via the SSM parameter:

### Supported Attachment Types in this project

| Direction | Images | Documents | Audio | Video | Stickers | Reactions
|---|---|---|---|---|---|---|
| Inbound (WhatsApp → Connect) | ✅ | ✅ | ✅ (converted + transcribed) | N/I | Configurable | N/I
| Outbound (Connect → WhatsApp) | ✅ | ✅ | — | — | — | - 

N/I: Not implemented here, but feasible.

```json
{
  "ignore_reactions": "yes",
  "ignore_stickers": "yes"
}
```

For media types (`image`, `document`, `audio`, `video`), the message payload includes a `media_id` that you use to download the actual file content. The file itself isn't in the webhook — you need to fetch it separately.

## Inbound: WhatsApp → Amazon Connect

When a customer sends a file on WhatsApp, the inbound handler Lambda (`whatsapp_event_handler`) processes it through three stages: detection, download, and upload.

### 1. Detection and Download

The `WhatsappMessage` class inspects each incoming message for media fields. It checks for `audio`, `image`, `document`, `video`, and `sticker` in that order:

```python
def get_attachment(self, download=True):
    attachment = None
    if self.message.get("audio"):
        attachment = self.message.get("audio")
    elif self.message.get("image"):
        attachment = self.message.get("image")
    elif self.message.get("document"):
        attachment = self.message.get("document")
    elif self.message.get("video"):
        attachment = self.message.get("video")
    elif self.message.get("sticker"):
        attachment = self.message.get("sticker")
    # reactions not implemented

    if not attachment:
        return {}

    # Download using the Social Messaging API
    media_content = self.download_media(
        media_id=attachment.get("id"),
        phone_id=self.phone_number_id,
        bucket_name=BUCKET_NAME,
        media_prefix=ATTACHMENT_PREFIX,
    )
    # Read binary content from S3
    binary = self.get_s3_file_content(media_content.get("location"))
    attachment.update({"content": binary})
```

The `download_media()` method calls the End User Messaging Social API (`get_whatsapp_message_media`), which downloads the file from Meta into an S3 bucket. The file lands at `s3://<bucket>/<prefix><media_id>.<extension>` where the extension is derived from the MIME type.

### 2. Upload to Amazon Connect Chat

Once the file is in S3 and its binary content is loaded, the `process_attachment()` function uploads it to the active Connect Chat session using the Participant API. This is a three-step process:

1. `start_attachment_upload` — creates an upload slot, returns a pre-signed URL and attachment ID
2. `PUT` to the pre-signed URL — uploads the binary content
3. `complete_attachment_upload` — finalizes the upload

```python
def attach_file(self, fileContents, fileName, fileType, ConnectionToken):
    # Step 1: Create upload slot
    attachResponse = participant_client.start_attachment_upload(
        ContentType=fileType,
        AttachmentSizeInBytes=fileSize,
        AttachmentName=fileName,
        ConnectionToken=ConnectionToken
    )

    # Step 2: Upload to pre-signed URL
    upload_url = attachResponse['UploadMetadata']['Url']
    requests.put(
        upload_url,
        data=fileContents,
        headers=attachResponse['UploadMetadata']['HeadersToInclude'],
        timeout=30
    )

    # Step 3: Finalize
    participant_client.complete_attachment_upload(
        AttachmentIds=[attachResponse['AttachmentId']],
        ConnectionToken=ConnectionToken
    )
```


## Outbound: Amazon Connect → WhatsApp

When an agent sends a file from the Connect Chat widget, the outbound handler Lambda (`connect_event_handler`) picks it up and forwards it to WhatsApp.

### 1. Attachment Detection

Amazon Connect publishes streaming events to an SNS topic. The handler checks the `Type` field in each event:

- `MESSAGE` — text message
- `ATTACHMENT` — file attachment
- `EVENT` — participant join/leave events


### 2. Signed URL Retrieval

For each attachment with `Status: APPROVED`, the handler looks up the customer's phone number and the system phone number from DynamoDB using the `contactId`, then retrieves a temporary download URL:

```python
def get_signed_url(connectionToken, attachment):
    response = participant_client.get_attachment(
        AttachmentId=attachment,
        ConnectionToken=connectionToken
    )
    return response['Url']
```

### 3. Send to WhatsApp

The handler maps the MIME type to the appropriate WhatsApp message type and sends the file using the signed URL as the media link — no need to re-upload the file:

```python
def send_whatsapp_attachment(attachment_url, mime_type, name, to, phone_number_id):
    message_type = get_file_category(mime_type)  # image, video, audio, or document
    message_object = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": f"+{to}",
        "type": message_type,
    }
    message_object[message_type] = {"link": attachment_url}
    if message_type == "document":
        message_object[message_type]["filename"] = name

    socialessaging.send_whatsapp_message(
        originationPhoneNumberId=phone_number_id,
        metaApiVersion=meta_api_version,
        message=bytes(json.dumps(message_object), "utf-8"),
    )
```

| MIME prefix | WhatsApp type |
|---|---|
| `image/*` | `image` |
| `video/*` | `video` |
| `audio/*` | `audio` |
| everything else | `document` |

For `document` types, the original filename is preserved so the customer sees a meaningful file name in their WhatsApp chat.

## Special Case. Processing Voice Notes

Beyond simple file relay, attachments can be processed to enable advanced use cases. The most compelling example in this solution is voice note handling — converting audio formats and transcribing speech to text.

### The Problem with Voice Notes

WhatsApp voice notes arrive in OGG/Opus format. Amazon Connect Chat [does not support OGG files as attachments](https://docs.aws.amazon.com/connect/latest/adminguide/feature-limits.html). If you try to upload an OGG file, it will be rejected. So you need a conversion step.

### OGG → WAV Conversion

A dedicated Lambda function (`convert_to_wav`) handles the format conversion using ffmpeg. After conversion, the inbound handler reads the WAV content from S3 and uploads it to Connect Chat as `voice.wav`.

### Real-Time Transcription with Amazon Transcribe Streaming

The original OGG file is also sent to a `transcribe_audio` Lambda for speech-to-text conversion. This uses Amazon Transcribe Streaming — not the batch API — for near real-time results.

## Beyond Voice Notes: Advanced Processing Ideas

The same pattern — intercept, process, forward — can be extended to other attachment types for advanced use cases:

- **Image understanding**: Use Amazon Bedrock or Amazon Rekognition to analyze photos. A customer sends a photo of a damaged product? Extract a description and attach it to the chat alongside the image. Useful for insurance claims or warranty requests.
- **Video analysis**: Extract key frames from video attachments and run them through multimodal models for understanding. A customer sends a video of a malfunctioning device? Summarize the issue for the agent.
- **Document extraction**: Use Amazon Textract or multimodal Foundation Models to extract text from scanned documents, invoices, or forms. Pre-fill case details before the agent even opens the chat.
- **Language detection and translation**: Detect the language of voice notes or text in images and translate them before forwarding to the agent.

The inbound handler is designed to be extensible — you can add processing steps between the download and the upload to Connect without changing the overall flow.



## Deployment Prerequisites

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

(see the [WhatsApp / Connect Prerequisites](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_connect_eum.md) for more details)

### Important: Enable Attachments in the Amazon Connect Instance

Follow [this steps](https://docs.aws.amazon.com/connect/latest/adminguide/enable-attachments.html) to enable attachment sharing.


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

### Step 3: Configure Transcription Language (Optional)

The transcription language is set to `es-US` (Spanish) by default. To change it, edit the `language_code` parameter in `lambdas/code/transcribe_audio/transcribe.py`:

```python
stream = await self.transcribe_client.start_stream_transcription(
    language_code="en-US",  # Change to your target language
    media_sample_rate_hz=48000,
    media_encoding="ogg-opus",
)
```

## Testing

Go to your Amazon Connect instance and [open the Contact Control Panel (CCP)](https://docs.aws.amazon.com/connect/latest/adminguide/launch-ccp.html). Send a WhatsApp message to the End User Messaging Social number.

<div align="center">
<video src="https://github.com/user-attachments/assets/652683f2-5a5c-4a35-ad82-c80f0f3fe275" width="540" controls></video>
</div>

Try these scenarios:

- Send a photo — it should appear as an image attachment in the agent's chat
- Send a PDF — it should appear as a document attachment
- Send a voice note — it should arrive as a WAV audio file plus a text transcription
- From the agent side, send an image or document — it should appear in the customer's WhatsApp chat

## Next Steps

This solution handles the core attachment flow. Some ideas to extend it:

- Multimodal Foundation Model for image analysis on inbound photos (e.g., damage assessment for claims)
- Implement support for video inbound attachments
- Support multiple transcription languages with automatic language detection
- Combine with the [Message Buffering](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/whatsapp-eum-connect-chat) solution to aggregate rapid messages and the [Agent-Initiated WhatsApp](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/agent-initiated-whatsapp) solution for full proactive communication

## Resources

- [Project Repository](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)
- [Amazon Connect Administrator Guide](https://docs.aws.amazon.com/connect/latest/adminguide/what-is-amazon-connect.html)
- [Amazon Connect Chat — Supported Attachment Types](https://docs.aws.amazon.com/connect/latest/adminguide/feature-limits.html)
- [Amazon Connect Participant API — StartAttachmentUpload](https://docs.aws.amazon.com/connect-participant/latest/APIReference/API_StartAttachmentUpload.html)
- [AWS End User Messaging Social — SendWhatsAppMessage API](https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_SendWhatsAppMessage.html)
- [AWS End User Messaging Social User Guide](https://docs.aws.amazon.com/social-messaging/latest/userguide/what-is-service.html)
- [Amazon Transcribe Streaming SDK](https://github.com/awslabs/amazon-transcribe-streaming-sdk)
- [WhatsApp Business Platform — Media Messages](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media)
