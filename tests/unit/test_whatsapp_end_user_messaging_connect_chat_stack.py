import aws_cdk as core
import aws_cdk.assertions as assertions

from whatsapp_end_user_messaging_connect_chat.whatsapp_end_user_messaging_connect_chat_stack import WhatsappEndUserMessagingConnectChatStack

# example tests. To run these tests, uncomment this file along with the example
# resource in whatsapp_end_user_messaging_connect_chat/whatsapp_end_user_messaging_connect_chat_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = WhatsappEndUserMessagingConnectChatStack(app, "whatsapp-end-user-messaging-connect-chat")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
