from aws_cdk import (
    custom_resources as cr,
    aws_iam as iam,
)
from constructs import Construct


class View(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        instance_id: str,
        content: dict,
        name: str,
        description: str = "",
        status: str = "PUBLISHED",
        tags: dict = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        create_params = {
            "InstanceId": instance_id,
            "Content": content,
            "Name": name,
            "Status": status,
        }
        if description:
            create_params["Description"] = description
        if tags:
            create_params["Tags"] = tags

        update_params = {
            "InstanceId": instance_id,
            "ViewId": cr.PhysicalResourceIdReference(),
            "Content": content,
            "Status": status,
        }

        self.custom_resource = cr.AwsCustomResource(
            self,
            "ViewCustomResource",
            on_create=cr.AwsSdkCall(
                service="Connect",
                action="createView",
                parameters=create_params,
                physical_resource_id=cr.PhysicalResourceId.from_response("View.Id"),
                output_paths=["View.Id", "View.Arn"],
            ),
            on_update=cr.AwsSdkCall(
                service="Connect",
                action="updateViewContent",
                parameters=update_params,
                physical_resource_id=cr.PhysicalResourceId.from_response("View.Id"),
                output_paths=["View.Id", "View.Arn"],
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=[
                        "connect:CreateView",
                        "connect:UpdateViewContent",
                    ],
                    resources=["*"],
                )
            ]),
        )

    @property
    def view_id(self) -> str:
        return self.custom_resource.get_response_field("View.Id")

    @property
    def view_arn(self) -> str:
        return self.custom_resource.get_response_field("View.Arn")
