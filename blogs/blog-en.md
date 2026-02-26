# Agent-Initiated WhatsApp Messages from Amazon Connect

Does your customer service team need to send proactive WhatsApp messages? Imagine an agent being able to send a WhatsApp template message to a customer with a single click, right from their Amazon Connect desktop. No switching apps, no copy-pasting phone numbers, no mistakes.

In this blog I'll show you how to build that experience using AWS CDK, AWS Lambda, AWS End User Messaging Social, and Amazon Connect.

Also available on [github.com/ensamblador](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)

## What are we building?

A guided experience inside the Amazon Connect Agent Workspace that allows agents to:

1. See customer data pre-loaded in a form
2. Review and edit WhatsApp template parameters
3. Send the message with a single click

All orchestrated by a Contact Flow, two Lambda functions, and a custom form (View).

## Architecture

![Architecture Diagram](../agent-initiated-whatsapp/agent-initiated-whatsapp.svg)

Here's how it flows:

1. A Contact Flow invokes a Lambda function (`get_customer_data`) to retrieve customer information (name, phone number, etc.)
2. The flow presents a form (View) in the Agent Workspace with pre-filled data
3. The agent reviews, edits if needed, and submits
4. A second Lambda function (`send_whatsapp_message`) sends the WhatsApp template message via the AWS End User Messaging Social API

## Prerequisites

Before getting started you'll need:

- A WhatsApp Business Account configured in AWS End User Messaging
- An Amazon Connect instance (you'll need the `INSTANCE_ID`)
- A WhatsApp message template created in End User Messaging (see the [Template Creation Guide](../general_template_creation.md))

For detailed instructions follow the [prerequisites guide](../general_connect_eum.md).

## Deploying with AWS CDK

⚠️ Deploy in the same region where your AWS End User Messaging WhatsApp numbers are configured.

### 1. Set the Instance ID

Edit `config.py` and set your Amazon Connect Instance ID:

```python
INSTANCE_ID = "<your-connect-instance-id>"
```

### 2. Clone the repository and navigate to the project

```bash
git clone https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat.git
cd sample-whatsapp-end-user-messaging-connect-chat/agent-initiated-whatsapp
```

### 3. Deploy with CDK

Follow the instructions in the [CDK Deployment Guide](../general_cdk_deploy.md).

## Post-deployment configuration

Once deployed, there are a few manual steps to wire everything together.

### Step 1: Update the SSM Parameter

Go to AWS Systems Manager Parameter Store and update `/whatsapp_template/config` with your template configuration:

```json
{
  "message": {
    "messaging_product": "whatsapp",
    "to": "PHONE_NUMBER",
    "recipient_type": "individual",
    "type": "template",
    "template": {
      "name": "your_template_name",
      "language": { "code": "en_US" },
      "components": [
        {
          "type": "body",
          "parameters": []
        }
      ]
    }
  },
  "META_API_VERSION": "v23.0",
  "ORIGINATION_PHONE_NUMBER_ID": "<your-origination-phone-number-id>"
}
```
