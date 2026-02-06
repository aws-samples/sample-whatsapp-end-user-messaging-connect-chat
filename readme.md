# WhatsApp Integration with Amazon Connect - Use Cases & Code Samples

This repository provides code samples and patterns for integrating WhatsApp Business with Amazon Connect using AWS End User Messaging. Each use case demonstrates common integration patterns with complete implementations using AWS CDK.

## Use Cases

| Use Case | Description | Type |
|----------|-------------|------|
| **[Bidirectional Chat Integration ](./whatsapp-eum-connect-chat/README.md)** | Complete two-way messaging between WhatsApp and Amazon Connect chat. Handles inbound customer messages and outbound responses with proper session management. | CDK Python |
| **[Message Buffering & Aggregation](./whatsapp-eum-connect-chat/README.md)** | Buffers rapid consecutive WhatsApp messages using DynamoDB Streams and aggregates them before forwarding to Amazon Connect. Prevents multiple chat messages from message bursts reducing downfall associated costs per invocation / per chat. | CDK Python |
| **[Whatsapp voice notes handling](./whatsapp-eum-connect-chat/README.md)** | Automatically transcribes WhatsApp voice messages using Amazon Transcribe Streamning and converts audio formats (OGG to WAV) for Amazon Connect attachments compatibility. Enables voice-to-text workflows. | Media Processing |
| **[Attachments Handling](./whatsapp-eum-connect-chat/README.md)** | Processes WhatsApp media attachments (images, documents, audio) with S3 storage, format conversion, and secure delivery to Amazon Connect agents. Connect attachments delivered to Whatsapp Users | Media Processing |
| **Outbound Messaging** *(Coming Soon)* | WhatsApp messages to customers from Amazon Connect agent Workspace | Sample Code


## General deployment Instructions

If you want to deploy any of this use cases, unless stated otherwise, follow this [General Guide](general_cdk_deploy.md) to deploy using CDK

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.

## Contributing

Please refer to the [CONTRIBUTING](CONTRIBUTING.md) document for further details on contributing to this repository. 