suppresion_list = [
    {
        "id": "AwsSolutions-IAM4",
        "reason": "AWSLambdaBasicExecutionRole is appropriate for Lambda CloudWatch Logs access",
        "appliesTo": [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        ]
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "Wildcard permissions required for DynamoDB streams (resource ARN includes stream suffix)",
        "appliesTo": [
            "Resource::*",
            "Resource::<TRawMessages*.Arn>/*"
        ]
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "Transcribe requires wildcard as job names are dynamic and created at runtime",
        "appliesTo": [
            "Resource::*",
            "Action::transcribe:Start*"
        ]
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "Connect resources use wildcards for instance/contact/contact-flow as these are configured via SSM parameters at runtime",
        "appliesTo": [
            "Resource::arn:aws:connect:*:<AWS::AccountId>:instance/*",
            "Resource::arn:aws:connect:*:<AWS::AccountId>:instance/*/contact/*",
            "Resource::arn:aws:connect:*:<AWS::AccountId>:instance/*/contact-flow/*"
        ]
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "End User Messaging phone number IDs are dynamic and configured at runtime",
        "appliesTo": [
            "Resource::arn:aws:social-messaging:<AWS::Region>:<AWS::AccountId>:phone-number-id/*"
        ]
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "S3 bucket requires object-level permissions for read/write operations",
        "appliesTo": [
            "Action::s3:Abort*",
            "Action::s3:DeleteObject*",
            "Action::s3:GetBucket*",
            "Action::s3:GetObject*",
            "Action::s3:List*",
            "Resource::<S3*.Arn>/*",
            "Resource::<S3486F821D.Arn>/*"
        ]
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "DynamoDB GSI requires wildcard for index queries on active_connections table",
        "appliesTo": [
            "Resource::<TWAChats4C84E925.Arn>/index/*"
        ]
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "Lambda invoke permission requires :* suffix to support function versions and aliases",
        "appliesTo": [
            "Resource::<LWhatsappIn3B664A40.Arn>:*"
        ]
    },
    {
        "id": "AwsSolutions-L1",
        "reason": "Using Python 3.13 which is the latest available Lambda runtime"
    },
    {
        "id": "AwsSolutions-SNS3",
        "reason": "SNS topics receive messages from AWS services (End User Messaging, Connect) which use SSL by default. Consider adding aws:SecureTransport condition for production."
    },
    {
        "id": "AwsSolutions-S1",
        "reason": "S3 access logging disabled to reduce costs for temporary voice message storage. Enable for production if audit trail needed."
    },
    {
        "id": "AwsSolutions-S10",
        "reason": "S3 bucket accessed only by Lambda functions within same account. Consider adding SSL requirement for production."
    },
    {
        "id": "AwsSolutions-DDB3",
        "reason": "Point-in-time recovery disabled to reduce costs. raw_messages table has TTL and is temporary buffer. active_connections can be rebuilt from Connect. Enable PITR for production if data recovery is critical."
    }
]