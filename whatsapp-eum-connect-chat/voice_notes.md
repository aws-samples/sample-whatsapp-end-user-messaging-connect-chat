# Transcribing Whatsapp Voice Notes

This document explains how the project processes WhatsApp voice. For the full architecture and deployment instructions, see the [Bidirectional WhatsApp guide](./bidirectional_whatsapp.md).

## Overview

![Architecture Diagram](./voice_notes.svg)

When a customer sends a voice note on WhatsApp :

1. Downloads the OGG/Opus audio from WhatsApp via End User Messaging. Saves in Whatsapp Media Bucket
2. Transcribes the audio using Amazon Transcribe Streaming
3. Sends the transcription as a text message back to the customer and forwards it to the agent

## Step by Step

### 1. Download from WhatsApp

The `WhatsappMessage.get_attachment()` method detects the `audio` type in the incoming message and calls `download_media()`, which uses the Social Messaging API (`get_whatsapp_message_media`) to download the file into S3. The resulting S3 URI looks like `s3://<bucket>/<prefix><media_id>.ogg`.


### 4. Audio Transcription

The `transcribe_audio` Lambda (`lambdas/code/transcribe_audio/`) transcribes the original OGG audio:

- Uses the `amazon-transcribe-streaming` SDK (provided as a Lambda Layer)
- Streams the audio from S3 to Amazon Transcribe Streaming in chunks of 8 KB
- Configured for `ogg-opus` encoding at 48 kHz sample rate
- Language is set to `es-US` (Spanish) — edit `transcribe.py` to change this
- Collects partial results and joins them into a final transcription string

The `TranscribeService` class handles the async streaming protocol: it reads the S3 object, sends audio chunks with pacing delays to respect real-time constraints, and a custom `MyEventHandler` accumulates non-partial transcript results.

### 5. Transcription Delivery

Back in the inbound handler, once the transcription is returned:

- The transcription is sent back to the customer on WhatsApp as a quoted reply: `🔊 _transcribed text_`
- The transcription text replaces the original message content, so the agent receives the text version in the Connect Chat window

## Configuration

The transcription language and sample rate can be changed in `lambdas/code/transcribe_audio/transcribe.py`:

```python
SAMPLE_RATE = 48000          # Match your audio source
language_code = "es-US"      # Change to your target language
media_encoding = "ogg-opus"  # Encoding of the source audio
```

