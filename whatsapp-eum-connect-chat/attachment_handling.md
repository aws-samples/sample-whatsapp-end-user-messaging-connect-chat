# Attachment Handling

This document explains how the project handles file attachments in both directions — customer to agent and agent to customer. For the full architecture and prerequisites, see the [Bidirectional WhatsApp guide](./bidirectional_whatsapp.md).

## Architecture

Zooming in, the flow is depicted in the following image:

1. If user send a file or media, that file is stored in s3 bucket
2. if is .ogg (voice notes) optionally is converted to wav for connect attachment support (see [File types supported for attachments to emails, cases, or chats](https://docs.aws.amazon.com/connect/latest/adminguide/feature-limits.html))
3. File is attached to Amazon Connect chat.
4. Later on, If Connect sends an attachment is detected with `Type: ATTACHMENT` event.
5. AWS lambda que media url and send to user a corresponding attachment (file, audio, video, etc)

![Architecture Diagram](./handlin_attachments.svg)


## Supported Attachment Types in this sample
(not limited to)

| Direction | Images | Documents | Audio | Video | Stickers |
|---|---|---|---|---|---|
| Inbound (WhatsApp → Connect) | ✅ | ✅ | ✅ (converted + transcribed) | - | Configurable |
| Outbound (Connect → WhatsApp) | ✅ | ✅ | - | - | — |

## Inbound: WhatsApp → Amazon Connect

When a customer sends a file on WhatsApp, the inbound handler Lambda (`whatsapp_event_handler`) processes it through these steps:

### 1. Detection and Download

On initialization, `WhatsappMessage` calls `get_attachment()` which inspects the incoming message for any media field (`audio`, `image`, `document`, `video`, `sticker`). If found, it:

- Calls `download_media()` using the Social Messaging API (`get_whatsapp_message_media`)
- The API downloads the file from Meta's servers into an S3 bucket configured via environment variables
- The file lands at `s3://<bucket>/<prefix><media_id>.<extension>` where the extension is derived from the MIME type
- The binary content is then read from S3 and stored in the attachment object for upload

### 2. Upload to Amazon Connect Chat

The `process_attachment()` function in the inbound handler uploads the file to the active Connect Chat session using the Participant API:

1. `start_attachment_upload` — creates an upload slot, returns a signed URL and attachment ID
2. `PUT` to the signed URL — uploads the binary content (validated to be HTTPS on an `.amazonaws.com` domain)
3. `complete_attachment_upload` — finalizes the upload

The agent then sees the file as an attachment in the Connect Chat widget. A 📎 reaction is sent to the customer on success, or ❌ on failure.

### 3. Audio Special Handling (OGG → WAV Conversion)

Amazon Connect Chat does not support OGG/Opus files as attachments. Since WhatsApp voice notes arrive in OGG format, they must be converted before upload.

The `convert_to_wav` Lambda (`lambdas/code/convert_to_wav/`) handles this:

1. Receives the S3 URI of the OGG file
2. Downloads it to `/tmp`
3. Runs **`ffmpeg`** (provided as a Lambda Layer) with these settings:
   - Codec: `pcm_s16le` (16-bit PCM)
   - Sample rate: `16000` Hz
   - Channels: `1` (mono)
4. Uploads the resulting WAV file back to S3 in the same prefix
5. Returns the new S3 URI to the caller

This Lambda runs on x86_64 architecture (unlike the other ARM64 Lambdas) because the ffmpeg layer is compiled for x86.

After conversion, the inbound handler reads the WAV content from S3 and uploads it to Connect Chat as `voice.wav`. The original OGG is also sent to the `transcribe_audio` Lambda for transcription — see [voice_notes.md](./voice_notes.md) for details on that pipeline.


## Outbound: Amazon Connect → WhatsApp

When an agent sends a file from the Connect Chat widget, the outbound handler Lambda (`connect_event_handler`) forwards it to WhatsApp.

### 1. Attachment Detection

Amazon Connect publishes streaming events to an SNS topic. The `process_record()` function checks the message `Type` field:

- `MESSAGE` — text message
- `ATTACHMENT` — file attachment
- `EVENT` — participant join/leave events

Messages from the `CUSTOMER` participant role are ignored to avoid echo loops.

### 2. Signed URL Retrieval

For each attachment with `Status: APPROVED`, the handler:

1. Looks up the customer's phone number and system number from DynamoDB using the `contactId`
2. Calls `get_signed_url()` which uses the Participant API (`get_attachment`) with the stored `connectionToken` to get a temporary download URL for the file

### 3. Send to WhatsApp

The `send_whatsapp_attachment()` function determines the WhatsApp message type from the MIME type:

| MIME prefix | WhatsApp type |
|---|---|
| `image/*` | `image` |
| `video/*` | `video` |
| `audio/*` | `audio` |
| everything else | `document` |

For `document` types, the original filename is included. The file is sent via the Social Messaging API (`send_whatsapp_message`) using the signed URL as the media `link` — no re-upload needed.

