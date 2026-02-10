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

The `transcribe_audio` Lambda (`lambdas/code/transcribe_audio/`) transcribes the audio:

- Uses the [`amazon-transcribe-streaming`](https://github.com/awslabs/aws-sdk-python/tree/develop/clients/aws-sdk-transcribe-streaming) SDK (provided as a Lambda Layer)
- Auto-detects audio format from the S3 key extension via `_get_format_config()` (defaults to `ogg-opus` at 48 kHz)
- Streams the audio from S3 to Amazon Transcribe Streaming in 8 KB chunks with pacing delays calculated from sample rate, bytes per sample, and channels
- Language is set to `es-US` (Spanish) — edit the `LANGUAGE_CODE` constant in `transcribe.py` to change this
- Collects only non-partial transcript results and joins them into a final transcription string

The `TranscribeService` class handles the full async streaming protocol: it downloads the S3 object, sends audio chunks via `write_chunks()`, and the `handle_events()` method accumulates final (non-partial) transcript results from the output stream. Both run concurrently using `asyncio.gather`.

### 5. Transcription Delivery

Back in the inbound handler, once the transcription is returned:

- The transcription is sent back to the customer on WhatsApp as a quoted reply: `🔊 _transcribed text_`
- The transcription text replaces the original message content, so the agent receives the text version in the Connect Chat window

## Configuration

The transcription language can be changed in `lambdas/code/transcribe_audio/transcribe.py`:

```python
LANGUAGE_CODE = "es-US"      # Change to your target language
```

The sample rate and media encoding are auto-detected from the S3 key extension by `_get_format_config()`. Currently supported formats:

| Extension | Encoding | Sample Rate |
|-----------|----------|-------------|
| `.ogg`, `.opus` | `ogg-opus` | 48 kHz |

To add new formats, extend the `_get_format_config()` function in `transcribe.py`.

