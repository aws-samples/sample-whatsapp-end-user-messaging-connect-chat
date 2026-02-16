from aws_cdk import aws_connect as connect, Stack
from constructs import Construct


class LambdaAssociation(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        instance_id: str,
        lambda_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stk = Stack.of(self)
        region = stk.region
        account = stk.account
        instance_arn = f"arn:aws:connect:{region}:{account}:instance/{instance_id}"

        self.association = connect.CfnIntegrationAssociation(
            self,
            "LambdaAssociation",
            instance_id=instance_arn,
            integration_arn=lambda_arn,
            integration_type="LAMBDA_FUNCTION",
        )
