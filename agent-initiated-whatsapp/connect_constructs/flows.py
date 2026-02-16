from aws_cdk import aws_connect as connect, Stack
from constructs import Construct, Node


class ContactFlow(Construct):

    def add_dependancy(self, node: Node):
        self.resource.add_dependency(node)

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        instance_id: str,
        cf_name,
        cf_content,
        cf_description: str = "Simple CDK Created Contact Flow",
        cf_type: str = "CONTACT_FLOW",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stk = Stack.of(self)
        region = stk.region
        account = stk.account
        instance_arn = f"arn:aws:connect:{region}:{account}:instance/{instance_id}"

        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_connect/CfnContactFlow.html
        self.resource = connect.CfnContactFlow(
            self,
            "CF",
            content=cf_content,
            instance_arn=instance_arn,
            name=cf_name,
            type=cf_type,
            # the properties below are optional
            description=cf_description,
            state="ACTIVE",
        )
