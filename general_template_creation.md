# Creating WhatsApp Message Templates in AWS End User Messaging

WhatsApp requires businesses to use pre-approved message templates when initiating conversations with customers. This guide walks through creating templates in the AWS End User Messaging Social console.

## What Are WhatsApp Templates?

WhatsApp message templates are structured messages that must be approved by Meta before they can be used. They support dynamic parameters (e.g., `{{1}}`, `{{2}}`) that are replaced with actual values at send time.

Templates are required for:
- Sending the first message to a customer (opening a conversation)
- Re-engaging a customer after the 24-hour conversation window has closed

## Creating a Template

### 1. Access the End User Messaging Social Console

Navigate to the [AWS End User Messaging Social console](https://console.aws.amazon.com/social-messaging/) and select your WhatsApp Business Account.

### 2. Navigate to Templates

In the left navigation, select **Templates** and click **Create template**.

### 3. Configure the Template

- **Template name**: Use lowercase letters, numbers, and underscores only (e.g., `order_update`, `appointment_reminder`)
- **Category**: Select the appropriate category:
  - **Marketing**: Promotions, offers, product recommendations
  - **Utility**: Order updates, account alerts, appointment reminders
  - **Authentication**: One-time passwords, verification codes
- **Language**: Select the language for the template (e.g., English, Spanish). You can create the same template in multiple languages

### 4. Define the Template Body

Write the message body using `{{1}}`, `{{2}}`, etc. as placeholders for dynamic content.

Example:
```
Hello {{1}}, your order {{2}} for {{3}} is now {{4}}.
```

At send time, these placeholders are replaced with actual values:
```
Hello Enrique, your order P12345 for Puzzle 1000 piezas is now Entregado.
```

### 5. Add Sample Content

Meta requires sample values for each parameter to review the template. Provide realistic examples that represent how the template will be used.

### 6. Submit for Approval

Click **Submit** to send the template for Meta's review. Approval typically takes a few minutes to a few hours, but can take up to 24 hours.

## Template Status

| Status | Description |
|---|---|
| **Pending** | Template is under review by Meta |
| **Approved** | Template is ready to use |
| **Rejected** | Template was not approved. Review Meta's feedback and resubmit |

## Using Templates with This Project

Once your template is approved, update the SSM parameter `/whatsapp_template/config` with:

- `template.name`: The exact template name you created
- `template.language.code`: The language code (e.g., `en_US`, `es`)
- Template parameters (`input1` through `input4`) map to `{{1}}` through `{{4}}` in the template body

## Tips

- Keep templates concise and clear
- Avoid promotional language in Utility templates to prevent rejection
- Test with the sample values before deploying to production
- You can manage templates both from the AWS console and the Meta Business Manager
- Template names cannot be changed after creation. Create a new template if you need a different name
