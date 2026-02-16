import aws_cdk as core
import aws_cdk.assertions as assertions

from agent_initiated_whatsapp.agent_initiated_whatsapp_stack import AgentInitiatedWhatsappStack

# example tests. To run these tests, uncomment this file along with the example
# resource in agent_initiated_whatsapp/agent_initiated_whatsapp_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AgentInitiatedWhatsappStack(app, "agent-initiated-whatsapp")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
