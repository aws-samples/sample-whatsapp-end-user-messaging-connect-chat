# WhatsApp Buffering Messages

AWS CDK project for managing WhatsApp message buffering with Amazon Connect integration.

## Architecture

![Architecture Diagram](./whatsapp-optimization-connect-DynamoDB.drawio.svg)

## How Message Buffering Works

This solution uses DynamoDB Streams to buffer and aggregate rapid consecutive WhatsApp messages before forwarding them to Amazon Connect.

### The Problem

When users send multiple messages in quick succession (e.g., "Hello", "How", "are", "you?"), each message triggers a separate webhook event. Without buffering, this creates:
- Multiple Amazon Connect chat sessions
- Poor user experience
- Increased costs

### The Solution: DynamoDB-Based Buffering

**1. Raw Message Storage**

Incoming WhatsApp messages are stored in a DynamoDB table (`raw_messages`) with:
- Partition key: `from` (sender phone number)
- Sort key: `id` (message ID)
- TTL enabled for automatic cleanup
- DynamoDB Streams enabled with `NEW_IMAGE` view type

**2. Stream Processing**

DynamoDB Streams triggers a Lambda function (`message_aggregator`) that:
- Receives batches of new messages from the stream
- Groups messages by sender, metadata, and context
- Sorts messages by timestamp
- Concatenates consecutive text messages with newlines
- Preserves non-text messages (images, audio, etc.) as separate items

**3. Aggregation Logic**

The aggregator combines messages like:
```
Message 1: "Hello"
Message 2: "How"
Message 3: "are"
Message 4: "you?"
```

Into a single aggregated message:
```
"Hello\nHow\nare\nyou?"
```

**4. Forwarding**

Once aggregated, the Lambda invokes the WhatsApp event handler asynchronously, which then creates or updates the Amazon Connect chat session with the combined message.

### Key Benefits

- **Natural conversation flow**: Multiple rapid messages appear as one coherent message
- **Cost optimization**: Fewer Lambda invocations and Connect API calls
- **Automatic cleanup**: TTL removes old messages automatically
- **Scalable**: DynamoDB Streams handles high throughput automatically
- **Reliable**: Stream processing ensures no messages are lost

## Cost Estimation

Example scenario: 1,000 raw messages aggregated into 250 messages (4:1 ratio)

### DynamoDB Costs (us-east-1)

**Total DynamoDB: ~$0.0013 per 1,000 messages**

### Lambda Costs (us-east-1)

**Total Lambda: ~$0.00078 per 1,000 messages**

### Total Cost Summary

For 1,000 raw messages → 250 aggregated messages:
- **DynamoDB + Streams: $0.0013**
- **Lambda (all functions): $0.00078**
- **Total: ~$0.002 per 1,000 messages**


**Savings vs. no buffering:**
- Without buffering: 1,000 Connect API calls => 0.004 x 1000 (in) + 0.004 x 1000 (out) = 8 USD
- With buffering: 250 Connect API calls => 0.004 x 250 (in) + 0.004 x 250 (out) = 2 USD
- **75% reduction in downstream processing (0,002 USD cost vs 6 USD savins)**

*Note: Costs exclude Amazon Connect charges. Use [AWS Pricing Calculator](https://calculator.aws) for complete estimates.*

## Prerequisites

- Python 3.x
- AWS CDK CLI
- AWS Account with appropriate permissions

## Setup

Create and activate virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate.bat
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Deployment

Synthesize CloudFormation template:

```bash
cdk synth
```

Deploy to AWS:

```bash
cdk deploy
```

## Useful Commands

- `cdk ls` - List all stacks
- `cdk synth` - Synthesize CloudFormation template
- `cdk deploy` - Deploy stack
- `cdk diff` - Compare deployed stack with current state
- `cdk destroy` - Remove deployed stack
