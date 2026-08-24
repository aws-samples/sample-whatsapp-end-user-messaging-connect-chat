# Supporting WhatsApp Business-Scoped User IDs (BSUID) in your Amazon Connect integration

   _Learn how to make a WhatsApp + Amazon Connect integration work when the customer's phone number is no longer guaranteed to be in the webhook. This step-by-step guide covers Meta's Business-Scoped User IDs (BSUID), how to carry an opaque sender identity through AWS Lambda, Amazon DynamoDB and Amazon Connect Chat, and how to address replies with `recipient` instead of `to`. Built on top of the existing WhatsApp End User Messaging + Amazon Connect solution using AWS CDK._


![Demo](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/demo_blurred.gif)


Every WhatsApp integration ever built has the same assumption baked into it somewhere: the customer *is* their phone number. It's the database key, the CRM lookup, the contact attribute the agent sees, and the destination you reply to.

That assumption is expiring. WhatsApp is rolling out **usernames**, an optional feature that lets a user display a username instead of their phone number. When a user adopts one, [their phone number stops appearing in webhook payloads](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-scoped-user-ids/). To keep you able to identify and reply to those users, Meta introduced a new identifier: the **Business-Scoped User ID (BSUID)**, delivered in a `user_id` / `from_user_id` property. Supporting it is required for all partners and directly-integrated businesses on the WhatsApp Business Platform.

The good news: if your pipeline is built well, this is a smaller change than it sounds. In this blog you'll see the exact changes made to the [WhatsApp End User Messaging + Amazon Connect Chat solution](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat) to support BSUID end to end — a handful of functions, no infrastructure changes, and one design decision that keeps the rest of the code from caring.

Check out the code at [https://github.com/aws-samples](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)


## What you'll build

A WhatsApp ↔ Amazon Connect integration that no longer assumes the customer's identity is a phone number. Specifically, it:

1. Detects whether an inbound message carries a BSUID (`from_user_id`) or only a phone number (`from`)
2. Uses whichever one is available as the conversation identity, and keeps the phone number as a separate attribute when it's present
3. Carries that identity through the buffering layer, the DynamoDB tables, and into the Amazon Connect Chat contact attributes
4. Addresses outbound messages with `recipient` (BSUID) or `to` (phone number), whichever matches the stored identity
5. Stays backward compatible with conversations that were started before the change

The end result: customers who adopt a username keep talking to your agents, and nothing in the flow breaks when the phone number disappears from the payload.

## Understanding BSUID

A BSUID is an opaque identifier for a WhatsApp user, scoped to a single Meta business portfolio. Two things matter for the implementation:

- **It's always there.** BSUIDs appear in messages webhooks whether or not the user adopted a username. The phone number is the field that may go missing.
- **It's not a phone number.** BSUIDs are prefixed with the user's ISO 3166 alpha-2 country code and a period, followed by up to 128 alphanumeric characters — for example `US.XXXXXXXXXXXXXXX`. When you send to a BSUID you must use the entire value, country code and period included.

### Which identifier arrives, and when

| Field | User has a username | User has no username |
|---|---|---|
| `messages[].from` (phone number) | Included only if the phone number is available per Meta's conditions | Always included |
| `messages[].from_user_id` (BSUID) | Always included | Always included |
| `contacts[].wa_id` (phone number) | Included only if available | Always included |
| `contacts[].user_id` (BSUID) | Always included | Always included |
| `contacts[].profile.username` | Always included | Not included |

Meta still shares the phone number in some cases — if you messaged or received a message/call from that number in the last 30 days, or the user is in your contact book. Practically, that means **you cannot rely on the phone number being there, and you cannot rely on it being absent either.** Your code has to handle both, on a per-message basis.

Here's an inbound webhook from a user who has a BSUID and whose phone number is still available (this is the fixture committed as `lambdas/code/on_raw_messages/entry.json`):

```json
{
  "changes": [
    {
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "XXXXXXXXXX",
          "phone_number_id": "XXXXXXXXXXXXXX"
        },
        "contacts": [
          {
            "profile": { "name": "Kike" },
            "wa_id": "XXXXXXXXX",
            "user_id": "US.XXXXXXXXXXXXXXX"
          }
        ],
        "messages": [
          {
            "from": "XXXXXXXXX",
            "from_user_id": "US.XXXXXXXXXXXXXXX",
            "id": "wamid.XXXXXXXXXXXXXXXXXXXXXXXXXXXXX=",
            "timestamp": "1787204895",
            "text": { "body": "Hola" },
            "type": "text"
          }
        ]
      },
      "field": "messages"
    }
  ]
}
```

When the same user adopts a username and the 30-day window lapses, `from` and `wa_id` simply disappear. Everything else stays.

### Sending: `to` vs `recipient`

On the send side, Meta added a `recipient` property alongside the existing `to`:

```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "<USER_PHONE_NUMBER>",
  "recipient": "<BSUID>",
  "type": "text",
  "text": { "body": "<BODY_TEXT>" }
}
```

You can include both, in which case `to` wins. This solution sends exactly one of them — cleaner, and it makes the identity mode explicit in the payload.

An important detail for AWS: **AWS End User Messaging Social passes the message body through verbatim.** The `send_whatsapp_message` API takes the Meta payload as raw bytes:

```python
socialmessaging.send_whatsapp_message(
    originationPhoneNumberId=phone_number_id,
    metaApiVersion=meta_api_version,
    message=bytes(json.dumps(message_object), "utf-8"),
)
```

So there is no AWS-side API change to adopt. `recipient` is a field inside `message`, and support for it comes from the `metaApiVersion` you send. Keep `META_API_VERSION` in [`config.py`](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/whatsapp-eum-connect-chat/config.py) current.

## Architecture

![Architecture Diagram](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/whatsapp-optimization-connect-DynamoDB.drawio.svg)

The architecture is unchanged. That's the point — no new resources, no new tables, no schema migration. The flow is still:

1. AWS End User Messaging Social publishes the WhatsApp webhook to an Amazon SNS topic
2. `on_raw_messages` writes each message into the `raw_messages` DynamoDB table
3. DynamoDB Streams with a tumbling window triggers `message_aggregator`, which buffers and concatenates consecutive messages
4. `whatsapp_event_handler` starts or continues the Amazon Connect Chat session
5. Amazon Connect streams agent messages to SNS, and `connect_event_handler` sends them back to WhatsApp

What changed is **the value that flows through it as the customer's identity**, and the two places that turn that value into a destination.

## The core design decision: one identity, decided once

The temptation with BSUID is to add `user_id` handling in every Lambda. Don't. Instead, pick the identity once at ingestion and let everything downstream treat it as an opaque string.

The pipeline already had a natural place for this: `item["from"]`, which is the partition key of the `raw_messages` table and the value that eventually becomes `customerId` in Amazon Connect. Rather than adding a parallel field, the change **redefines what `from` means**: it's no longer "the phone number", it's "whatever identifies this sender".

That single decision is why the diff is small.

### 1. Ingestion: choose the identity mode

`lambdas/code/on_raw_messages/lambda_function.py` is the only place that branches on identity mode:

```python
for message in value.get("messages", []):
    item = message.copy()
    item["context"] = message_context
    item["metadata"] = metadata
    item["messaging_product"] = messaging_product
    item["field"] = field

    from_phone_number = message.get("from")
    from_user_id = message.get("from_user_id")

    # Identity mode: user_id when available, phone number otherwise.
    if from_user_id:
        item["from"] = from_user_id
        contact_key, contact_value = "user_id", from_user_id
    else:
        item["from"] = from_phone_number
        contact_key, contact_value = "wa_id", from_phone_number

    item["from_phone_number"] = from_phone_number
    if from_user_id:
        item["from_user_id"] = from_user_id

    contact = next((c for c in contacts if c.get(contact_key) == contact_value), {})
    item["contact"] = contact

    table.put_item(Item=item)
```

Before the change, that block was two lines, and the contact was always matched on `wa_id`:

```python
wa_id = message.get("from")
contact = next((c for c in contacts if c.get("wa_id") == wa_id), {})
```

Three things happen now:

- `item["from"]` holds the BSUID when one is present, the phone number otherwise. This becomes the conversation key.
- `item["from_phone_number"]` preserves Meta's raw `from`, so the real phone number is still available when you have it — for CRM enrichment, callbacks, or analytics.
- `item["from_user_id"]` is written **only when non-empty**, because downstream code branches on its presence rather than its value. An empty string would be indistinguishable from a real one at a glance and would make the branch conditions noisier.

Note that the contact lookup key moves with the identity mode: `user_id` for BSUID senders, `wa_id` for phone-number senders. The contacts array is keyed differently depending on which one you got.

### 2. Buffering: forward the new fields explicitly

This is the step that's easy to miss. The `message_aggregator` Lambda rebuilds a synthetic webhook payload from the DynamoDB stream images, and it does so with an **explicit field allowlist**. Any field not named there is silently dropped between the buffer table and the handler.

Two builders were added in `lambdas/code/message_aggregator/process_stream.py`:

```python
def build_contact(contact: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild a webhook contact, keeping user_id when the sender has one."""
    payload: Dict[str, Any] = {
        'profile': contact.get('profile', {}),
        'wa_id': contact.get('wa_id', '')
    }
    if contact.get('user_id'):
        payload['user_id'] = contact['user_id']
    return payload


def build_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild a webhook message, keeping the sender identity fields."""
    payload: Dict[str, Any] = {
        'from': message.get('from'),
        'id': message.get('id'),
        'timestamp': message.get('timestamp'),
        'text': message.get('text'),
        'type': message.get('type'),
        'audio': message.get('audio'),
        'image': message.get('image'),
        'video': message.get('video'),
        'document': message.get('document'),
        'sticker': message.get('sticker'),
        'location': message.get('location'),
        'contacts': message.get('contacts'),
        'interactive': message.get('interactive')
    }

    # from_user_id only exists for senders identified by user_id, and downstream
    # code branches on its presence, so it is omitted when empty.
    if message.get('from_user_id'):
        payload['from_user_id'] = message['from_user_id']
    if message.get('from_phone_number'):
        payload['from_phone_number'] = message['from_phone_number']

    return payload
```

The aggregation logic itself needed no changes at all. It groups by `record.get('from')`, which now transparently groups by BSUID:

```python
sender = record.get('from')
key = (json.dumps(metadata, sort_keys=True), json.dumps(context, sort_keys=True), sender)
```

If you have your own transformation layer between the webhook and your handlers, audit it for this same pattern. Allowlists are good practice, and they are exactly what breaks when a new identifier shows up.

### 3. Inbound handler: address replies with `recipient` or `to`

The `WhatsappMessage` class now derives three identity attributes instead of one, in `lambdas/code/whatsapp_event_handler/whatsapp.py`:

```python
self.phone_number = message.get("from", "")
self.from_user_id = message.get("from_user_id", "")
# Older payloads only carry "from", which is the phone number in that case.
self.from_phone_number = message.get("from_phone_number") or (
    "" if self.from_user_id else self.phone_number
)
```

That fallback on `from_phone_number` is the backward-compatibility hinge. Items written by the previous version of the stack have no `from_phone_number` attribute at all, and their `from` *is* a phone number — so treating `from` as the phone number when `from_user_id` is absent keeps in-flight conversations replying correctly.

The destination is then resolved in one place:

```python
def get_recipient(self):
    """Destination field for a send_whatsapp_message payload.

    Senders identified by user_id are addressed with "recipient";
    senders identified by phone number are addressed with "to".
    """
    if self.from_user_id:
        return {"recipient": self.from_user_id}
    if self.from_phone_number:
        return {"to": f"+{self.from_phone_number}"}
    return {}
```

And every outbound payload builds the message body *without* a destination, then merges one in:

```python
def text_reply(self, text_message):
    message_object = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "context": {"message_id": self.message_id},
        "type": "text",
        "text": {"preview_url": False, "body": text_message},
    }
    message_object.update(self.get_recipient())

    kwargs = dict(
        originationPhoneNumberId=self.phone_number_id,
        metaApiVersion=self.meta_api_version,
        message=bytes(json.dumps(message_object), "utf-8"),
    )
    response = self.client.send_whatsapp_message(**kwargs)
```

Before, these dicts contained a hardcoded `"to": f"+{self.phone_number}"`. The `.update()` pattern is worth copying: it keeps the destination decision in exactly one function, so adding support for parent BSUIDs later is a one-line change. The same treatment was applied to `reaction()`. `mark_as_read()` needs no destination and was left untouched.

### 4. Contact name: match on the right key

Resolving the customer's display name has the same two-mode problem — the contacts array is keyed by `user_id` or `wa_id` depending on the sender. The method signature changed from `(from_number, contacts)` to `(message, contacts)` so it can inspect the identity itself:

```python
def get_customer_name(self, message, contacts):
    """Match the contact by user_id when present, by wa_id otherwise."""
    from_user_id = message.get("from_user_id")
    if from_user_id:
        key, value = "user_id", from_user_id
    else:
        key, value = "wa_id", message.get("from_phone_number") or message.get("from", "")

    for contact in contacts:
        if contact.get(key) == value:
            return contact.get("profile", {}).get("name", "NN")
    return ""
```

### 5. Outbound from Amazon Connect: infer the mode from the stored value

The agent side is the interesting one. `connect_event_handler` never sees the original webhook — it only has the `customerId` it looked up in DynamoDB from the `contactId`. So it has to infer whether that string is a BSUID or a phone number.

In `lambdas/code/connect_event_handler/whatsapp.py`:

```python
# A phone number destination is only digits, optionally prefixed with "+".
PHONE_NUMBER_PATTERN = re.compile(r"^\+?\d+$")


def get_recipient(destination):
    """Destination field for a send_whatsapp_message payload.

    active_connections stores whatever identified the customer: a WhatsApp
    user_id (e.g. "US.XXXXXXXXXXXXXXX") or a phone number. user_id
    destinations are addressed with "recipient", phone numbers with "to".
    """
    destination = str(destination or "").strip()
    if not destination:
        return {}
    if PHONE_NUMBER_PATTERN.match(destination):
        return {"to": f"+{destination.lstrip('+')}"}
    return {"recipient": destination}
```

Both send functions use it the same way as the inbound handler:

```python
def send_whatsapp_text(text_message, to, phone_number_id, meta_api_version=META_API_VERSION):
    message_object = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": "text",
        "text": {"preview_url": False, "body": text_message},
    }
    message_object.update(get_recipient(to))

    kwargs = dict(
        originationPhoneNumberId=phone_number_id,
        metaApiVersion=meta_api_version,
        message=bytes(json.dumps(message_object), "utf-8"),
    )
    response = socialessaging.send_whatsapp_message(**kwargs)
```

Shape-based inference works here because BSUIDs always carry a country-code prefix and a period, so they can never match `^\+?\d+$`. It's a pragmatic choice that avoids adding a column to the connections table. If you'd rather be explicit, store an `identityType` attribute alongside `customerId` when the contact is created and branch on that instead — worth it if your `customerId` space might ever include all-digit identifiers from another channel.

### 6. What Amazon Connect sees

`start_chat_contact` was not modified, but it's where the identity reaches the agent. Because the caller passes `message.phone_number` (which is `from`, i.e. the BSUID when one exists), the `customerId` contact attribute now carries the BSUID:

```python
start_chat_response = self.connect.start_chat_contact(
    InstanceId=self.instance_id,
    ContactFlowId=self.contact_flow_id,
    Attributes={
        "Channel": channel,
        "customerId": phone,
        "customerName": name,
        "systemNumber": systemNumber,
    },
    ParticipantDetails={"DisplayName": name},
    InitialMessage={"ContentType": "text/plain", "Content": message},
    ChatDurationInMinutes=self.chat_duration_minutes,
    ...
)
```

**Check your contact flows.** If a flow, Lambda invocation, or agent screen-pop uses `customerId` as a phone number — a CRM lookup, a callback, an outbound dial — it will now receive `US.XXXXXXXXXXXXXXX` for some customers. Two options: pass the phone number as a second attribute (it's available as `message.from_phone_number` when present), or make the consumer handle both shapes. This is the change most likely to surprise you in production, and it lives outside the code in this repo.

## Differences from the previous version, at a glance

| Concern | Before | After |
|---|---|---|
| Conversation identity | `messages[].from` (always a phone number) | BSUID when present, phone number otherwise |
| Phone number | Was the identity | Separate `from_phone_number` attribute, may be absent |
| Contact lookup key | Always `wa_id` | `user_id` or `wa_id`, per message |
| Outbound destination | Hardcoded `"to": f"+{phone}"` | `get_recipient()` returns `{"recipient": ...}` or `{"to": ...}` |
| Aggregator payload | Fixed field allowlist | Same allowlist plus `from_user_id`, `from_phone_number`, contact `user_id` |
| `raw_messages` partition key `from` | `XXXXXXXXX` | `US.XXXXXXXXXXXXXXX` or `XXXXXXXXX` |
| `active_connections` GSI `customerId` | Phone number | BSUID or phone number |
| DynamoDB schema / GSIs | — | **Unchanged** |
| CDK stack, IAM, SNS, tables | — | **Unchanged** |
| AWS API calls | `send_whatsapp_message` | **Unchanged** — only the serialized Meta body differs |

Worth restating: **no infrastructure change and no schema migration.** Both affected keys are already `STRING` typed and opaque to DynamoDB. The `raw_messages` partition key is still `from`, the `active_connections` GSI is still `customerId-index`. Only the value space widened.

## Planning your rollout

**Naming.** `WhatsappMessage.phone_number`, the `phone` variable in `connect_event_handler.process_message`, and the log line `"Found existing connection for Phone Number..."` all carry the identity value, which may now be a BSUID. Only `from_phone_number` is always a phone number. Renaming these as you touch them keeps the intent clear for the next reader.

**Conversation continuity across the cutover.** A conversation that started before BSUIDs appeared is keyed by phone number, so once Meta starts sending `from_user_id` for that user, the `customerId` GSI lookup misses and a new Amazon Connect contact begins. To carry those threads over, add a fallback lookup: try the BSUID first, then `from_phone_number` when it's present, and rewrite the stored `customerId` on a hit.

**BSUIDs are regenerated when a user changes their phone number.** Meta reports this on the `messages` field as a system message, with `system.type` set to `user_changed_number` or `user_changed_user_id` and `system.previous_user_id` carrying the old value — your join key for stitching the new identity onto the record you already have. A branch for `type: "system"` messages is the natural place to handle it.

**Outbound payloads include the recipient identifier.** BSUIDs and phone numbers both identify a customer, so if you keep the debug logging in the send paths, factor Amazon CloudWatch log retention and access into your pre-production review.

**Proactive outreach.** The companion [agent-initiated WhatsApp](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/agent-initiated-whatsapp) solution addresses customers by phone number, which suits its use case of an agent typing a number into a form. To let agents reach a customer you only have a BSUID for, apply the same `get_recipient()` helper on that path.

**If you still need phone numbers, ask for them.** Meta added a `REQUEST_CONTACT_INFO` button for utility and marketing templates, and as an interactive message. When the user taps it, their number is shared in-thread and arrives in a contacts webhook. If your business process genuinely requires a phone number (identity verification, shipping, a callback), build that into the conversation instead of relying on the webhook.

## Deployment Prerequisites

Before getting started you'll need:

### WhatsApp Business Account

To get started, you need to create a new WhatsApp Business Account (WABA) or migrate an existing one to AWS. The main steps are described [here](https://docs.aws.amazon.com/social-messaging/latest/userguide/getting-started.html). In summary:

1. Have or create a Meta Business Account
2. Access the AWS End User Messaging Social console and link your business account through the embedded Facebook portal
3. Make sure you have a phone number that can receive SMS/voice verification and add it to WhatsApp

⚠️ Important: Do not use your personal WhatsApp number for this.

### An Amazon Connect Instance

You need an Amazon Connect instance. If you don't have one yet, you can [follow this guide](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-instances.html) to create one.

You'll need the **INSTANCE_ID** of your instance. You can find it in the Amazon Connect console or in the instance ARN:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID`

### A Chat Flow to Handle Messages

Create or have ready the contact flow that defines the user experience. [Follow this guide](https://docs.aws.amazon.com/connect/latest/adminguide/create-contact-flow.html) to create an Inbound Contact Flow. The simplest one will work.

Remember to publish the flow.

![Simple Flow](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/flow_simple.png)

Take note of the **INSTANCE_ID** and **CONTACT_FLOW_ID** from the Details tab. The values are in the flow ARN:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID/contact-flow/CONTACT_FLOW_ID`

(see the [WhatsApp / Connect Prerequisites](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_connect_eum.md) for more details)

### Optional: Enable Attachments

If you want images, documents and voice notes to flow in both directions, follow [these steps](https://docs.aws.amazon.com/connect/latest/adminguide/enable-attachments.html) to enable attachment sharing in your instance. The BSUID changes cover attachment sending too — `send_whatsapp_attachment` uses the same `get_recipient()` helper.

## Deploying with AWS CDK

⚠️ Deploy in the same region where your AWS End User Messaging WhatsApp numbers are configured.

### 1. Clone the repository and navigate to the project

```bash
git clone https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat.git
cd sample-whatsapp-end-user-messaging-connect-chat/whatsapp-eum-connect-chat
```

### 2. Deploy with CDK

Follow the instructions in the [CDK Deployment Guide](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_cdk_deploy.md).

Because the BSUID support is entirely in the Lambda code, an existing deployment just needs a redeploy — no table replacement, no data migration:

```bash
cdk deploy
```

## Post-deployment Configuration

### Step 1: Update the SSM Parameter

After deployment, update the SSM parameter `/whatsapp_eum_connect_chat/config` with your Amazon Connect details:

```json
{
  "instance_id": "<your-connect-instance-id>",
  "contact_flow_id": "<your-contact-flow-id>",
  "chat_duration_minutes": 60,
  "ignore_reactions": "yes",
  "ignore_stickers": "yes"
}
```

| Parameter | Description |
|---|---|
| `instance_id` | Your Amazon Connect Instance ID |
| `contact_flow_id` | The ID of the Inbound Contact Flow for chat |
| `chat_duration_minutes` | How long the chat session stays active (default: 60) |
| `ignore_reactions` | Whether to ignore WhatsApp reactions (default: yes) |
| `ignore_stickers` | Whether to ignore WhatsApp stickers (default: yes) |

### Step 2: Add the Event Destination

After deploying the stack, use the created SNS topic as your event destination in the AWS End User Messaging Social console.

1. Go to AWS Systems Manager Parameter Store and copy the value of `/whatsapp_eum_connect_chat/topic/in` (it starts with `arn:aws:sns`)

![Topic Parameter](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/topic_parameter.png)

2. In the AWS End User Messaging Social console, select destination **Amazon SNS** and paste the **Topic ARN** from the previous step

![SNS EUM Configuration](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/SNS_EUM.png)

### Step 3: Review the Meta API version

`recipient` is a Meta payload field, so support depends on the API version you send. It's set in [`config.py`](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/whatsapp-eum-connect-chat/config.py):

```python
BUFFER_IN_SECONDS = 5
META_API_VERSION = "v23.0"
```

Confirm the version you're on supports sending to BSUIDs, and bump it if needed before relying on `recipient` in production.

### Step 4: Audit your contact flows

Search your contact flows, flow-invoked Lambdas, and agent workspace views for `customerId`. Anywhere it's treated as a phone number needs to either handle the BSUID shape or be given the phone number as a separate attribute. Do this before you have BSUID-only customers, not after.

## Testing

You don't have to wait for a real username adopter. Meta's App Dashboard has a webhook test tool that sends realistic payloads to your endpoint: **App Dashboard > Use cases (pencil icon) > Connect with customers through WhatsApp > Customize > Configuration**, then click **Test** next to the messages webhook. It covers the scenarios that matter:

- User has not adopted a username — BSUID and phone number both present
- User has adopted a username, phone number unavailable — BSUID only
- User has adopted a username, phone number available — everything present

For a faster loop, invoke the Lambdas directly with the committed fixtures. `lambdas/code/on_raw_messages/entry.json` is a BSUID payload, and `lambdas/code/message_aggregator/event.json` is the corresponding DynamoDB stream event.

Then go to your Amazon Connect instance, [open the Contact Control Panel (CCP)](https://docs.aws.amazon.com/connect/latest/adminguide/launch-ccp.html), and check:

- A real WhatsApp message still creates a chat and the agent still sees the customer's name
- The agent's reply arrives back in WhatsApp (this proves the `recipient`/`to` selection round-trips)
- The `raw_messages` table item has `from` = BSUID, `from_user_id` = BSUID, `from_phone_number` = the number
- The `customerId` attribute on the contact matches whatever is in `raw_messages`
- Send several messages fast — buffering should still group them, now keyed by BSUID

## Next Steps

BSUID support is the floor, not the ceiling. Some ideas to build on it:

- Handle `type: "system"` messages so you can follow `user_changed_number` / `user_changed_user_id` and keep identity continuity when a BSUID is regenerated
- Add a phone-number fallback lookup on the `customerId` GSI so conversations survive the cutover
- Pass the phone number to Amazon Connect as its own contact attribute, so flows can use it without parsing `customerId`
- Add a `REQUEST_CONTACT_INFO` button to your journey for cases where you genuinely need a phone number
- Extend the [agent-initiated WhatsApp](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/agent-initiated-whatsapp) solution to address BSUIDs
- If you operate multiple business portfolios, look at parent BSUIDs (`from_parent_user_id`) so one identifier works across all of them

## Resources

- [Project Repository](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)
- [WhatsApp Business Platform — Business-scoped user IDs](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-scoped-user-ids/)
- [AWS End User Messaging Social — SendWhatsAppMessage API](https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_SendWhatsAppMessage.html)
- [AWS End User Messaging Social User Guide](https://docs.aws.amazon.com/social-messaging/latest/userguide/what-is-service.html)
- [Amazon Connect Administrator Guide](https://docs.aws.amazon.com/connect/latest/adminguide/what-is-amazon-connect.html)
- [Amazon Connect API — StartChatContact](https://docs.aws.amazon.com/connect/latest/APIReference/API_StartChatContact.html)
- [DynamoDB Streams Developer Guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html)

_Content from the Meta developer documentation was rephrased for compliance with licensing restrictions._
