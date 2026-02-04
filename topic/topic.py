from aws_cdk import aws_sns as sns, aws_sns_subscriptions as subs, aws_iam as iam

from constructs import Construct


class Topic(Construct):

    def __init__(
        self, scope: Construct, construct_id: str, name:str, lambda_function=None, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.topic = sns.Topic(self,name, display_name=name)

        if lambda_function:
            self.topic.add_subscription(subs.LambdaSubscription(lambda_function))

    def trigger(self, lambda_function):
        self.topic.add_subscription(subs.LambdaSubscription(lambda_function))


    def allow_principal(self, service_principal):
        self.topic.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal(service_principal)], # type: ignore
                actions=["sns:Publish"],
                resources=[self.topic.topic_arn],
            )
        )