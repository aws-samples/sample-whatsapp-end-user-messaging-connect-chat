# Technology Stack

## Infrastructure as Code

- **AWS CDK** (Python) — all infrastructure defined as CDK constructs
- **cdk-nag** (`AwsSolutionsChecks`) — security/compliance validation on every synth
- Nag suppressions centralized in `nag_suppressions.py`

## Runtime

- **Python 3.13** — Lambda runtime
- **AWS Lambda** — ARM64 by default, X86_64 only for `convert_to_wav` (FFmpeg layer requirement)
- **boto3** — AWS SDK, available in Lambda runtime (not in `requirements.txt`)

## CDK Dependencies

```
aws-cdk-lib>=2.236.0,<3.0.0
constructs>=10.0.0,<11.0.0
cdk-nag>=2.0.0
```

## Lambda Configuration Defaults

Defined in `lambdas/project_lambdas.py` as `BASE_LAMBDA_CONFIG`:
- Timeout: 900s
- Memory: 512 MB
- Tracing: X-Ray active
- Architecture: ARM64

## Lambda Layers (pre-packaged zips in `/layers/`)

- `requests.zip` — HTTP requests library
- `transcribe-client.zip` — Amazon Transcribe streaming client
- `ffmpeg.zip` — FFmpeg binary for audio conversion

## AWS Services Used

- DynamoDB (with Streams) — message buffering and connection tracking
- SNS — event routing between WhatsApp EUM and Connect
- S3 — media/attachment storage
- SSM Parameter Store — runtime configuration
- Amazon Connect — chat sessions
- Amazon Transcribe — voice note transcription
- AWS End User Messaging (Social) — WhatsApp send/receive

## Common Commands

All commands run from `whatsapp-eum-connect-chat/`.

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# CDK
cdk synth        # synthesize CloudFormation
cdk diff         # compare with deployed
cdk deploy       # deploy stack
cdk destroy      # tear down stack

# Testing
pip install -r requirements-dev.txt
pytest
```

## Conventions

- Lambda handler entry point is always `lambda_function.lambda_handler`
- Environment variables are set in the CDK stack (`set_up_env_vars`), not hardcoded in Lambda code
- Configuration values read from SSM Parameter Store at runtime via `config_service.py`
- `print()` and `logging` are both used for CloudWatch Logs output in Lambda code
