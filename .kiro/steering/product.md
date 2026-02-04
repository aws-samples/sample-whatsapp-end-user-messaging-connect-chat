# Product Overview

WhatsApp message buffering system for Amazon Connect integration. Aggregates rapid consecutive WhatsApp messages before forwarding to Amazon Connect to improve user experience and reduce costs.

## Core Problem
When users send multiple quick messages ("Hello", "How", "are", "you?"), each triggers a separate webhook, creating multiple Connect chat sessions and poor UX.

## Solution
DynamoDB Streams-based buffering that:
- Stores raw messages in DynamoDB with TTL
- Aggregates consecutive messages by sender
- Forwards combined messages to Amazon Connect
- Reduces downstream processing by ~75%

## Key Components
- **Raw message storage**: DynamoDB table with streams enabled
- **Message aggregator**: Lambda triggered by DynamoDB streams
- **WhatsApp handler**: Processes aggregated messages and manages Connect chats
- **Connect handler**: Sends messages from Connect back to WhatsApp
- **Active connections**: DynamoDB table tracking chat sessions

## Integration Points
- AWS End User Messaging (WhatsApp API)
- Amazon Connect (chat service)
- Amazon Transcribe (voice message transcription)
- SNS topics for message routing
