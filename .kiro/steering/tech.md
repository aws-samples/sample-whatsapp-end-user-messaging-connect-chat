# Technology Stack

## Infrastructure as Code
- **AWS CDK** (Python) - Infrastructure definition and deployment
- **CloudFormation** - Generated from CDK for AWS resource provisioning

## Runtime
- **Python 3.13** - Lambda runtime
- **ARM64 architecture** - Lambda architecture for cost optimization

## AWS Services
- **Lambda** - Serverless compute (4 functions)
- **DynamoDB** - NoSQL database with streams
- **SNS** - Message routing between services
- **S3** - File storage for attachments
- **SSM Parameter Store** - Configuration management
- **AWS End User Messaging** - WhatsApp Business API integration
- **Amazon Connect** - Contact center chat service
- **Amazon Transcribe** - Audio transcription

## Key Libraries
- `aws-cdk-lib>=2.236.0` - CDK framework
- `constructs>=10.0.0` - CDK constructs
- `pytest==8.4.2` - Testing framework

## Lambda Configuration
All Lambda functions use:
- Timeout: 30 seconds
- Memory: 512 MB
- Runtime: Python 3.13
- Architecture: ARM64
- Tracing: X-Ray enabled

## Common Commands

### Setup
```bash
# Create virtual environment
python3 -m venv .venv

# Activate (macOS/Linux)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### CDK Operations
```bash
# Synthesize CloudFormation template
cdk synth

# Deploy to AWS
cdk deploy

# Compare deployed vs current state
cdk diff

# List all stacks
cdk ls

# Destroy stack
cdk destroy
```

### Testing
```bash
# Run tests
pytest

# Run specific test file
pytest tests/unit/test_whatsapp_end_user_messaging_connect_chat_stack.py
```

## Configuration
- `config.py` - Central configuration file with parameter names and defaults
- SSM Parameter Store - Runtime configuration (instance IDs, contact flow IDs, buffer settings)
- Environment variables - Lambda-specific configuration injected by CDK
