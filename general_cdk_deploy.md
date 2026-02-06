# CDK Deployment Guide

General instructions for deploying AWS CDK projects.

## Prerequisites

- Node.js and npm installed (required for CDK CLI)
- Python 3.x installed (for Python CDK projects)
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- AWS Account with appropriate permissions
- AWS CLI configured with credentials (recommended for authentication)

## Initial Setup

### 1. Create Virtual Environment

In the same cdk project folder 

```bash
python3 -m venv .venv
```

### 2. Activate Virtual Environment

macOS/Linux:
```bash
source .venv/bin/activate
```

Windows:
```bash
.venv\Scripts\activate.bat
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Deployment Workflow

### Synthesize CloudFormation Template

Preview the CloudFormation template that will be generated:

```bash
cdk synth
```

This validates your CDK code and outputs the CloudFormation template to the `cdk.out` directory.

### Compare Changes (Recommended)

Before deploying, check what changes will be made:

```bash
cdk diff
```

This shows differences between your current stack definition and the deployed version, including:
- IAM policy and security group changes
- Resource additions, modifications, and deletions
- Parameter changes

### Deploy to AWS

Deploy the stack to your AWS account:

```bash
cdk deploy
```

## Common Commands

- `cdk ls` (or `cdk list`) - List all stacks in the app
- `cdk synth` (or `cdk synthesize`) - Synthesize CloudFormation template
- `cdk deploy` - Deploy stack(s) to AWS
- `cdk diff` - Compare deployed stack with current state
- `cdk destroy` - Remove deployed stack from AWS
- `cdk bootstrap` - Prepare AWS environment for CDK deployments (first-time only)
- `cdk watch` - Continuously monitor and deploy changes (useful for development)
- `cdk doctor` - Check your CDK project for potential issues
- `cdk --version` - Display CDK CLI version

## First-Time Deployment

If this is your first CDK deployment in an AWS account/region, bootstrap the environment. Bootstrapping provisions resources that the CDK needs for deployments, including:
- An S3 bucket for storing assets (Lambda code, Docker images, etc.)
- An ECR repository for container images
- IAM roles for deployment operations

### Bootstrap Commands

From within a CDK project directory:
```bash
cdk bootstrap
```

Or specify the environment explicitly:
```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

Example:
```bash
cdk bootstrap aws://123456789012/us-east-1
```

With a specific AWS profile:
```bash
cdk bootstrap --profile prod aws://123456789012/us-east-1
```

**Note:** You only need to bootstrap each AWS environment (account/region combination) once. The bootstrap stack is named `CDKToolkit` by default.

## Troubleshooting

### Permission Issues

Ensure your AWS credentials have sufficient permissions:
- CloudFormation full access
- IAM role creation
- Service-specific permissions (Lambda, DynamoDB, S3, etc.)
- Access to bootstrap resources (S3 bucket, ECR repository)

### Environment Not Bootstrapped

If you see errors about missing bootstrap resources or templates over 51,200 bytes failing to deploy:

```bash
cdk bootstrap
```

## Best Practices

1. Always run `cdk diff` before deploying to production
2. Use `cdk synth` to validate changes locally
3. Review IAM permissions and security groups carefully
4. Tag resources appropriately for cost tracking
5. Use separate AWS accounts/regions for dev/staging/prod
