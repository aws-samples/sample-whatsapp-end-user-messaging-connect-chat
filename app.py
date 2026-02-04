#!/usr/bin/env python3
import os

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from nag_suppressions import suppresion_list
from whatsapp_end_user_messaging_connect_chat.whatsapp_end_user_messaging_connect_chat_stack import WhatsappEndUserMessagingConnectChatStack


app = cdk.App()
stack = WhatsappEndUserMessagingConnectChatStack(app, "WABA-EUM-CONNECT-CHAT",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

# Suppress AWS managed policy warnings for Lambda basic execution role
# This policy provides minimal CloudWatch Logs permissions needed by all Lambda functions
NagSuppressions.add_stack_suppressions(stack, suppresion_list)

# Add security checks
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
