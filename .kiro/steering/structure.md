# Project Structure

Monorepo with one CDK project in `whatsapp-eum-connect-chat/`. Root contains shared docs and repo metadata.

## Root

- `readme.md` — repo overview and use case index
- `general_cdk_deploy.md` — shared CDK deployment instructions
- `general_connect_eum.md` — prerequisites for Connect + End User Messaging setup

## `whatsapp-eum-connect-chat/`

Single CDK app. All paths below are relative to this directory.

### Entry Points

- `app.py` — CDK app entry, stack instantiation, cdk-nag aspects
- `config.py` — centralized constants (buffer timing, API version, SSM param names)
- `nag_suppressions.py` — cdk-nag suppression rules

### CDK Stack

`whatsapp_end_user_messaging_connect_chat/whatsapp_end_user_messaging_connect_chat_stack.py`

Stack is organized into four methods:
1. `create_resources()` — instantiate all AWS resources
2. `set_up_env_vars()` — wire Lambda environment variables
3. `create_parameters()` — create SSM parameters
4. `set_up_permissions()` — grant IAM permissions

### Infrastructure Constructs

Each resource type is a separate CDK Construct in its own module:

| Module | Construct | Purpose |
|--------|-----------|---------|
| `lambdas/project_lambdas.py` | `Lambdas` | All Lambda function definitions + shared config |
| `databases/databases.py` | `Tables` | DynamoDB tables (raw_messages, active_connections) |
| `topic/topic.py` | `Topic` | SNS topics with Lambda subscriptions |
| `layers/project_layers.py` | `TranscribeClient`, `RequestsLayer`, `FFMpeg` | Lambda layer definitions |

### Lambda Code

Each Lambda lives in its own directory under `lambdas/code/`:

| Directory | Role |
|-----------|------|
| `on_raw_messages/` | Receives SNS → stores raw WhatsApp messages in DynamoDB |
| `message_aggregator/` | DynamoDB Stream consumer → aggregates buffered messages |
| `whatsapp_event_handler/` | Processes aggregated messages → creates/updates Connect chat |
| `connect_event_handler/` | Receives Connect events → sends replies back to WhatsApp |
| `convert_to_wav/` | Converts OGG audio to WAV for Connect attachments |
| `transcribe_audio/` | Transcribes audio via Amazon Transcribe Streaming |

### Lambda Code Conventions

- Entry point: `lambda_function.py` → `lambda_handler(event, context)`
- Service logic split into separate modules (e.g., `whatsapp.py`, `connections_service.py`, `connect_chat_service.py`)
- Shared code is duplicated per Lambda directory (no shared Lambda code layer for business logic)

### Event Flow

```
Inbound:  WhatsApp → EUM → SNS (whatsapp_in) → on_raw_messages → DynamoDB
          DynamoDB Streams → message_aggregator → whatsapp_event_handler → Amazon Connect

Outbound: Amazon Connect → SNS (whatsapp_out) → connect_event_handler → EUM → WhatsApp
```

### Tests

`tests/unit/` — pytest unit tests for CDK stack synthesis

### Construct ID Conventions

- Top-level constructs use short IDs: `L` (Lambdas), `T` (Tables), `S3`, `WAIn`/`WAOut` (SNS topics)
- Lambda IDs: `RawMessage`, `MessageAggr`, `WhatsappIn`, `ConnectOut`, `convertWav`, `Transcribe`
