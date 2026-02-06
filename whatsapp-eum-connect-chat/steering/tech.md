# Technology Stack

## Infrastructure as Code

- **AWS CDK** (Python) - Infrastructure definition and deployment
- **cdk-nag** - Security and compliance checks

## Runtime

- **Python 3.13** - Lambda runtime
- **AWS Lambda** - Serverless compute (ARM64 architecture, except convert_to_wav uses X86_64)
- **DynamoDB** - Message storage with Streams for event processing
- **DynamoDB Streams** - Event-driven message aggregation
- **SNS** - Message routing between services
- **S3** - Media file storage
- **SSM Parameter Store** - Configuration management

## Key Libraries

- `aws-cdk-lib>=2.236.0` - CDK framework
- `constructs>=10.0.0` - CDK constructs
- `boto3` - AWS SDK for Python (Lambda runtime)

## Lambda Configuration

- Timeout: 30 seconds
- Memory: 512 MB
- Tracing: X-Ray enabled
- Architecture: ARM64 (default), X86_64 (for FFmpeg layer)

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

### Development

```bash
# Synthesize CloudFormation template
cdk synth

# Compare deployed stack with current state
cdk diff

# Deploy to AWS
cdk deploy

# List all stacks
cdk ls

# Remove deployed stack
cdk destroy
```

### Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest
```

## AWS Services Integration

- **Amazon Connect** - Chat contact creation and streaming
- **WhatsApp Business API** (via AWS End User Messaging) - Message send/receive
- **Amazon Transcribe** - Audio transcription
