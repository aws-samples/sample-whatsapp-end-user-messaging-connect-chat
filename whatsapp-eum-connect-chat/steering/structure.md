# Project Structure

## Root Files

- `app.py` - CDK app entry point, stack instantiation, and cdk-nag security checks
- `config.py` - Centralized configuration (buffer timing, API versions, parameter names)
- `cdk.json` - CDK configuration and feature flags
- `nag_suppressions.py` - Security check suppressions for cdk-nag

## Core Modules

### `/whatsapp_end_user_messaging_connect_chat/`

Main CDK stack definition:
- `whatsapp_end_user_messaging_connect_chat_stack.py` - Primary stack with resource creation, environment variables, permissions, and SSM parameters

### `/lambdas/`

Lambda function definitions and code:
- `project_lambdas.py` - Lambda construct with all function definitions and shared configuration
- `/code/` - Lambda function implementations:
  - `on_raw_messages/` - Stores incoming WhatsApp messages in DynamoDB
  - `message_aggregator/` - DynamoDB Stream processor that aggregates messages
  - `whatsapp_event_handler/` - Processes aggregated messages and creates Connect chats
  - `connect_event_handler/` - Handles outbound messages from Connect to WhatsApp
  - `convert_to_wav/` - Audio format conversion for Connect attachments

### `/databases/`

DynamoDB table constructs:
- `databases.py` - Table definitions (raw_messages with streams, active_connections)

### `/topic/`

SNS topic constructs:
- `topic.py` - SNS topic creation with Lambda subscriptions

### `/layers/`

Lambda layers:
- `project_layers.py` - Layer construct definitions
- `.zip` files - Pre-packaged layer dependencies (ffmpeg, requests, transcribe-client)

### `/tests/`

Test suite:
- `/unit/` - Unit tests for stack and components

## Architecture Patterns

### Resource Organization

Stack follows a modular pattern:
1. `create_resources()` - Create all AWS resources
2. `set_up_env_vars()` - Configure Lambda environment variables
3. `create_parameters()` - Create SSM parameters
4. `set_up_permissions()` - Grant IAM permissions

### Lambda Naming Convention

Lambda IDs use short prefixes:
- `RawMessage` - Raw message handler
- `MessageAggr` - Message aggregator
- `WhatsappIn` - Inbound WhatsApp handler
- `ConnectOut` - Outbound Connect handler
- `convertWav` - Audio converter

### Construct IDs

Top-level constructs use single-letter IDs:
- `L` - Lambdas
- `T` - Tables
- `S3` - S3 bucket
- `WAIn` / `WAOut` - SNS topics

### Configuration Management

Centralized in `config.py`:
- Buffer timing settings
- API versions
- SSM parameter names and initial values

### Event Flow

1. WhatsApp → SNS (`whatsapp_in`) → `on_raw_messages` → DynamoDB
2. DynamoDB Streams → `message_aggregator` → `whatsapp_event_handler` → Amazon Connect
3. Amazon Connect → SNS (`whatsapp_out`) → `connect_event_handler` → WhatsApp
