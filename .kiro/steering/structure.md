# Project Structure

## Root Files
- `app.py` - CDK app entry point, instantiates main stack
- `cdk.json` - CDK configuration and feature flags
- `config.py` - Centralized configuration constants (SSM param names, buffer settings, API versions)
- `requirements.txt` - Production dependencies
- `requirements-dev.txt` - Development dependencies

## Core Modules

### `/whatsapp_end_user_messaging_connect_chat/`
Main CDK stack definition
- `whatsapp_end_user_messaging_connect_chat_stack.py` - Primary stack orchestrating all resources

### `/lambdas/`
Lambda function definitions and code
- `project_lambdas.py` - CDK construct defining all Lambda functions with shared config
- `/code/on_raw_messages/` - Stores incoming WhatsApp messages in DynamoDB
- `/code/message_aggregator/` - Processes DynamoDB streams, aggregates messages
- `/code/whatsapp_event_handler/` - Handles aggregated messages, manages Connect chats
- `/code/connect_event_handler/` - Sends messages from Connect back to WhatsApp

### `/databases/`
DynamoDB table definitions
- `databases.py` - CDK construct for DynamoDB tables
  - `active_connections` - Tracks active chat sessions (PK: contactId, GSI: customerId+channel)
  - `raw_messages` - Temporary message storage with streams (PK: from, SK: id, TTL enabled)

### `/topic/`
SNS topic definitions
- `topic.py` - CDK construct for SNS topics with Lambda subscriptions

### `/layers/`
Lambda layers
- `project_layers.py` - CDK construct for Lambda layers
- `transcribe-client.zip` - Transcribe client library

### `/tests/`
Test files
- `/unit/` - Unit tests for CDK stack

## Lambda Function Structure
Each Lambda directory contains:
- `lambda_function.py` - Main handler entry point
- Service modules (e.g., `whatsapp.py`, `connections_service.py`, `connect_chat_service.py`)
- Test event JSON files for local testing

## Architecture Patterns

### CDK Constructs
- Modular constructs for Lambdas, Tables, Topics
- Centralized configuration in `BASE_LAMBDA_CONFIG` and `TABLE_CONFIG`
- Stack orchestrates resource creation, environment variables, and permissions

### Lambda Organization
- Service-oriented modules (e.g., `WhatsappService`, `ConnectionsService`, `ChatService`)
- Separation of concerns: message processing, connection management, API interactions
- Shared configuration via environment variables

### Resource Naming
- CDK construct IDs use short prefixes (e.g., "L" for Lambdas, "T" for Tables)
- Logical names in code (e.g., `whatsapp_event_handler`, `active_connections`)
- Stack name: `WABA-EUM-CONNECT-CHAT`

## Configuration Flow
1. `config.py` - Static defaults and parameter names
2. SSM Parameter Store - Runtime configuration (deployed via CDK)
3. Environment variables - Lambda-specific values (set by stack)
4. Lambda code - Reads from environment and SSM at runtime
