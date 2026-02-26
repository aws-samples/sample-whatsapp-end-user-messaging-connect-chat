# Agent-Initiated WhatsApp Messages from Amazon Connect


   _Learn how to build a proactive WhatsApp messaging experience from Amazon Connect, enabling customer service agents to send WhatsApp template messages with a single click from the Agent Workspace. This step-by-step guide covers the full architecture using AWS CDK, AWS Lambda, AWS End User Messaging Social, and Amazon Connect, including the configuration of Contact Flows, custom forms (Views), and Lambda functions to retrieve customer data and send messages. Ideal for teams looking to automate and simplify outbound WhatsApp communication without leaving the Amazon Connect console._


![Demo](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/agent-initiated-whatsapp/demo_whatsapp_saliente.gif)


Does your customer service team need to send proactive WhatsApp messages? Imagine an agent being able to send a WhatsApp template message to a customer with a single click, right from their Amazon Connect desktop. No switching apps, no copy-pasting phone numbers, no mistakes.

In this blog I'll show you how to build that experience using AWS CDK, AWS Lambda, AWS End User Messaging Social, and Amazon Connect.

Check out the code at [https://github.com/aws-samples](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)


## What are we building?

A guided experience inside the Amazon Connect Agent Workspace that allows agents to:

1. See customer data pre-loaded in a form
2. Review and edit WhatsApp template parameters
3. Send the message with a single click

All orchestrated by a Contact Flow, Lambda functions, and a custom form (Connect view).

## Architecture


![Architecture Diagram](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/agent-initiated-whatsapp/agent-initiated-whatsapp.png)

Here's how it flows:

1. A Contact Flow invokes a Lambda function (`get_customer_data`) to retrieve customer information (name, phone number, etc.). You can also use the [`Customer Profile`](https://docs.aws.amazon.com/connect/latest/adminguide/customer-profiles-block.html) block to look up customer information in Connect Customer Profiles.
2. The flow presents a form (View) in the Agent Workspace with pre-filled data
3. The agent reviews, edits if needed, and submits
4. A second Lambda function (`send_whatsapp_message`) sends the WhatsApp template message via the AWS End User Messaging Social API

## Prerequisites

Before getting started you'll need:

### WhatsApp Business Account

To get started, you need to create a new WhatsApp Business Account (WABA) or migrate an existing one to AWS. The main steps are described [here](https://docs.aws.amazon.com/social-messaging/latest/userguide/getting-started.html). In summary:

1. Have or create a Meta Business account
2. Access the AWS End User Messaging Social console and link your business account through the embedded Facebook portal
3. Make sure you have a phone number that can receive SMS/voice verification and add it to WhatsApp

⚠️ Important: Do not use your personal WhatsApp number for this.

### An Amazon Connect Instance

You need an Amazon Connect instance. If you don't have one yet, you can [follow this guide](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-instances.html) to create one.

You'll need the **INSTANCE_ID** of your instance. You can find it in the Amazon Connect console or in the instance ARN:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID`

(see the [WhatsApp / Connect Prerequisites](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_connect_eum.md) for more details)


### WhatsApp Message Template Creation

A WhatsApp message template created in End User Messaging (see the [Template Creation Guide](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_template_creation.md))


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

Follow the instructions in the [CDK Deployment Guide](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_cdk_deploy.md).

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

| Parameter | Description |
|---|---|
| `template.name` | Name of your WhatsApp template created in End User Messaging |
| `template.language.code` | Template language code (e.g.: `en_US`) |
| `ORIGINATION_PHONE_NUMBER_ID` | The phone number ID in AWS End User Messaging Social |
| `META_API_VERSION` | Meta API version (default: `v23.0`) |

### Step 2: Explore the deployed form

Navigate to the views in your Amazon Connect instance:

```
https://<your-instance>.my.connect.aws/views
```

Look for the view named `enviarWhatsAppForm007`. This is the form that agents will use to review customer data and send the message.

![Deployed Form](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/agent-initiated-whatsapp/form.png)

_Note: the WhatsApp field is of type password to hide the number. It could even be removed from the form entirely and accessed using [Contact Attributes](https://docs.aws.amazon.com/connect/latest/adminguide/connect-contact-attributes.html)._

### Step 3: Configure the deployed Contact Flow

Navigate to the contact flow `SendWhatsAppGuideFlow007` in your Amazon Connect console.

![Contact Flow](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/agent-initiated-whatsapp/flow.png)

#### 3.1 Configure the first Lambda (Get customer data)

Edit the first **Invoke AWS Lambda function** block and select the pre-deployed Lambda function. Look for the one containing `GetCustomerData` in the name.

This is a mock function that returns sample data:

```python
def lambda_handler(event, context):
    return {
        "fullName": "John Doe",
        "phoneNumber": "+XXXXXXXX",
        "input4": "Delivered",
        "input3": "Puzzle 1000 pieces",
        "input2": "P12345",
        "input1": "John",
    }
```

Replace this with your own data source. For example, you could do a data dip to Amazon Connect Customer Profiles using a `profileId`, query a DynamoDB table, or call an external API.

Click **Confirm** to save.

#### 3.2 Configure the Show View block

Edit the **Show view** block and select `enviarWhatsAppForm007` as the view resource.

The form default values are mapped from the values returned by the Lambda:

- `fullName` → `$.External.fullName`
- `whatsappNumber` → `$.External.phoneNumber`
- `input1` to `input4` → `$.External.input1` to `$.External.input4`

These values pre-fill the form so the agent can review them before sending. Click **Confirm** to save.

#### 3.3 Configure the second Lambda (Send WhatsApp message)

Edit the second **Invoke AWS Lambda function** block and select the Lambda containing `SendWhatsappMessage` in the ARN.

This Lambda reads the template configuration from SSM, extracts the form values from the contact attributes, and sends the message:

```python
def lambda_handler(event, context):
    # Load the template configuration from SSM Parameter Store
    config = get_ssm_parameter(CONFIG_PARAM_NAME)
    message_payload = config["message"]

    # Extract form values from contact attributes
    attributes = event["Details"]["ContactData"]["Attributes"]
    phone_number = attributes.get("phoneNumber")

    # Build template parameters from input1..input4
    template_params = build_template_parameters(
        attributes, ["input1", "input2", "input3", "input4"]
    )

    # Send using AWS End User Messaging Social
    response = social_client.send_whatsapp_message(
        originationPhoneNumberId=origination_phone_number_id,
        message=bytes(json.dumps(message_payload), "utf-8"),
        metaApiVersion=meta_api_version,
    )
    return {"result": "OK", "messageId": response.get("messageId", "")}
```

Click **Confirm** to save. Then **Save** and **Publish** the contact flow.

### Step 4: Create a new View (Guide)

Navigate to the Amazon Connect views:

```
https://<your-instance>.my.connect.aws/views
```

Create a new view of type **Guide**.

![Create View](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/agent-initiated-whatsapp/create_view.png)

#### 4.1 Add a Connect Application component

Drag a **Connect Application** component onto the canvas.

#### 4.2 Configure the component

Set the `contactFlowId` to the deployed contact flow `SendWhatsAppGuideFlow007`.

![Create Guide](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/agent-initiated-whatsapp/create_guide.png)

#### 4.3 Name and publish

Give the view a name and click **Publish**.

### Step 5: Create a custom Workspace

#### 5.1 Create the workspace

Navigate to the Amazon Connect workspaces:

```
https://<your-instance>.my.connect.aws/workspaces
```

Click **Add new workspace** and fill in the name, description, and title.

![Create Workspace](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/agent-initiated-whatsapp/create_workspace.png)

Assign this workspace to the users or routing profiles you need.

#### 5.2 Add a page with the guide

Add a new page using **Set page with custom page slug** and select the view you created in the previous step (the one with the Connect Application component).

Use a custom slug like:

```
/page/send_whatsapp
```

![Add Page](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/agent-initiated-whatsapp/add_page.png)

Save the page.

#### 5.3 Navigate to the custom workspace

Select your custom workspace from the top navigation bar in the Agent Workspace.

![Select Workspace](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/agent-initiated-whatsapp/select_workspace.png)

The agent can now navigate to the custom page and use the guide to send WhatsApp template messages to customers.

## Demo

When the agent navigates to the custom page, they are presented with a Connect Application that runs the contact flow. The flow displays the form with pre-loaded values from the customer data Lambda, giving the agent the opportunity to review, modify, and submit. Once the agent submits, the WhatsApp sending Lambda is invoked with all the form parameters to deliver the final message.

<div align="center">
<video src="https://github.com/user-attachments/assets/251a757c-2fe8-4875-966f-32d2bb7c3aa7" width="540" controls></video>
</div>


## Next steps

This solution is a starting point. Some ideas to extend it:

- Connect the customer data Lambda to Amazon Connect Customer Profiles or DynamoDB
- Add additional validations to the form
- Support multiple WhatsApp templates selectable by the agent
- Dynamically incorporate the number of inputs, depending on the number of variables in the template

## Resources

- [Project Repository](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)
- [Amazon Connect Administrator Guide](https://docs.aws.amazon.com/connect/latest/adminguide/what-is-amazon-connect.html)
- [Amazon Connect API Reference](https://docs.aws.amazon.com/connect/latest/APIReference/Welcome.html)
- [AWS End User Messaging Social - SendWhatsAppMessage API](https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_SendWhatsAppMessage.html)
- [AWS End User Messaging Social User Guide](https://docs.aws.amazon.com/social-messaging/latest/userguide/what-is-service.html)
- [WhatsApp Business Platform - Template Message Structure](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates)
- [WhatsApp Business Platform - Template Components Reference](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#template-object)
