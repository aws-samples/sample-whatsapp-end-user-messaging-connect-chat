import json
from aws_cdk import Stack, aws_ssm as ssm, aws_iam as iam

from constructs import Construct
from lambdas import Lambdas
from connect_constructs import View, LambdaAssociation, ContactFlow

import config


def load_flow_content(file_name):
    with open(file_name) as f:
        return json.dumps(json.load(f))


class AgentInitiatedWhatsappStack(Stack):

    def create_ssm_parameter(self, parameter_name: str, string_value: str):
        return ssm.StringParameter(
            self,
            parameter_name.replace("/", "").replace("_", "").title(),
            parameter_name=parameter_name,
            string_value=string_value,
        )

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.create_resources()
        self.set_up_env_vars()
        self.create_parameters()
        self.set_up_permissions()

    def create_resources(self):
        self.lambda_functions = Lambdas(self, "L")
        self.form_view = View(
            self,
            "V",
            instance_id=config.INSTANCE_ID,
            content=config.FORM_VIEW["Content"],
            name=config.FORM_VIEW["Name"],
        )
        LambdaAssociation(
            self,
            "LA1",
            instance_id=config.INSTANCE_ID,
            lambda_arn=self.lambda_functions.send_whatsapp_message.function_arn,
        )
        LambdaAssociation(
            self,
            "LA2",
            instance_id=config.INSTANCE_ID,
            lambda_arn=self.lambda_functions.get_customer_data.function_arn,
        )

        flow_content = load_flow_content(config.CONTACT_FLOW_CONTENTS_FILE)

        self.contact_flow = ContactFlow(
            self,
            "CF",
            instance_id=config.INSTANCE_ID,
            cf_name=config.CONTACT_FLOW["Name"],
            cf_content=flow_content,
            cf_description=config.CONTACT_FLOW["Description"],
        )

    def set_up_env_vars(self):
        self.lambda_functions.send_whatsapp_message.add_environment(
            key="CONFIG_PARAM_NAME", value=config.CONFIG_PARAM_NAME
        )

    def create_parameters(self):
        self.config_parameters = self.create_ssm_parameter(
            config.CONFIG_PARAM_NAME, json.dumps(config.CONFIG_PARAM_INITIAL_CONTENT)
        )

    def set_up_permissions(self):
        eum_policy = iam.PolicyStatement(
            actions=[
                "social-messaging:SendWhatsAppMessage",
                "social-messaging:GetWhatsAppMessageMedia",
            ],
            resources=[
                f"arn:aws:social-messaging:{self.region}:{self.account}:phone-number-id/*"
            ],
        )

        self.lambda_functions.send_whatsapp_message.add_to_role_policy(eum_policy)
        self.config_parameters.grant_read(self.lambda_functions.send_whatsapp_message)
