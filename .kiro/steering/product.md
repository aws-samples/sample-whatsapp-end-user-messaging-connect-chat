# Product Overview

Code samples and patterns for integrating WhatsApp Business with Amazon Connect using AWS End User Messaging. Each use case is a complete CDK deployment.

## Use Cases

- **Bidirectional Chat** — Two-way messaging between WhatsApp and Amazon Connect with session management
- **Message Buffering** — Aggregates rapid consecutive WhatsApp messages via DynamoDB Streams before forwarding to Connect, reducing costs ~75%
- **Voice Notes** — Transcribes WhatsApp voice messages using Amazon Transcribe Streaming, converts OGG→WAV for Connect attachments
- **Attachments** — Processes WhatsApp media (images, documents, audio) with S3 storage and format conversion for Connect agents

## Key Concepts

- Incoming WhatsApp messages arrive via AWS End User Messaging → SNS
- Messages are buffered in DynamoDB with a configurable tumbling window (default 20s)
- Active chat sessions are tracked in a DynamoDB connections table
- Outbound agent messages flow from Amazon Connect → SNS → WhatsApp
- Configuration (Connect instance ID, flow ID, etc.) lives in SSM Parameter Store
