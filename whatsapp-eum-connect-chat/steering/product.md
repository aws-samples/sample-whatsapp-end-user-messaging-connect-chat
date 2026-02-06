# Product Overview

WhatsApp message buffering system for Amazon Connect integration. Aggregates rapid consecutive WhatsApp messages before forwarding to Amazon Connect to improve user experience and reduce costs.

## Core Functionality

- Buffers incoming WhatsApp messages using DynamoDB Streams
- Aggregates consecutive messages from the same sender
- Forwards aggregated messages to Amazon Connect chat sessions
- Handles text, audio, and media messages
- Automatic message cleanup via TTL

## Key Benefits

- Prevents multiple chat sessions from rapid message bursts
- 75% cost reduction in downstream processing
- Natural conversation flow for end users
- Scalable and reliable stream processing
