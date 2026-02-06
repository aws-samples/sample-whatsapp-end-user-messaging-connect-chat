import json
from aws_cdk import (
    RemovalPolicy,     aws_ssm as ssm,

    aws_s3 as s3, Stack, CfnOutput, 
    aws_iam as iam, Duration, aws_lambda_event_sources as event_sources, aws_lambda
)

from constructs import Construct

from lambdas import Lambdas
from topic import Topic
from databases import Tables
import config


class WhatsappEndUserMessagingConnectChatStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.create_resources()
        self.set_up_env_vars()
        self.create_parameters()
        self.set_up_permissions()

    def create_resources(self):

        buffer_seconds = Duration.seconds(config.BUFFER_IN_SECONDS) 

        self.lambda_functions = Lambdas(self, "L")
        self.tables = Tables(self, "T")

        self.topic_messages_in =  Topic( self, "WAIn", name="whatsapp_in", lambda_function=self.lambda_functions.on_raw_messages)
        self.topic_messages_out = Topic( self, "WAOut", name="whatsapp_out", lambda_function=self.lambda_functions.connect_event_handler)

        
        self.lambda_functions.message_aggregator.add_event_source(
            event_sources.DynamoEventSource(
                self.tables.raw_messages, 
                starting_position=aws_lambda.StartingPosition.TRIM_HORIZON, 
                tumbling_window = buffer_seconds,
                batch_size=1000, 
                max_batching_window = buffer_seconds)
        )
        
        self.s3_bucket = s3.Bucket(self, "S3", removal_policy=RemovalPolicy.DESTROY)

        CfnOutput(self, "TopicArn", value=self.topic_messages_in.topic.topic_arn)


    def set_up_env_vars(self):
        self.lambda_functions.message_aggregator.add_environment(key="WHATSAPP_EVENT_HANDLER", value=self.lambda_functions.whatsapp_event_handler.function_arn)
        self.lambda_functions.on_raw_messages.add_environment(key="RAW_MESSAGES_TABLE", value=self.tables.raw_messages.table_name)
        self.lambda_functions.whatsapp_event_handler.add_environment(key="CONVERT_WAV_HANDLER", value=self.lambda_functions.convert_to_wav.function_arn)
        self.lambda_functions.whatsapp_event_handler.add_environment(key="TRANSCRIBE_HANDLER", value=self.lambda_functions.transcribe_audio.function_arn)

        for l in [self.lambda_functions.whatsapp_event_handler,  self.lambda_functions.connect_event_handler]:
            l.add_environment(key="META_API_VERSION", value=config.META_API_VERSION)
            l.add_environment(key="TABLE_NAME", value=self.tables.active_connections.table_name)
            l.add_environment(key="BUCKET_NAME", value=self.s3_bucket.bucket_name)
            l.add_environment(key="VOICE_PREFIX", value="voice_")
            l.add_environment(key="TOPIC_ARN", value=self.topic_messages_out.topic.topic_arn)
            l.add_environment(key="CONFIG_PARAM_NAME", value=config.CONFIG_PARAM_NAME)


    def set_up_permissions(self):
        self.tables.raw_messages.grant_read_write_data(self.lambda_functions.on_raw_messages)
        self.tables.raw_messages.grant_read_write_data(self.lambda_functions.message_aggregator)

        self.tables.active_connections.grant_read_write_data(self.lambda_functions.whatsapp_event_handler)
        self.tables.active_connections.grant_read_write_data(self.lambda_functions.connect_event_handler)

        self.lambda_functions.whatsapp_event_handler.grant_invoke(self.lambda_functions.message_aggregator)
        self.lambda_functions.convert_to_wav.grant_invoke(self.lambda_functions.whatsapp_event_handler)
        self.lambda_functions.transcribe_audio.grant_invoke(self.lambda_functions.whatsapp_event_handler)

        eum_policy = iam.PolicyStatement(
            actions=["social-messaging:SendWhatsAppMessage","social-messaging:GetWhatsAppMessageMedia"],
            resources=[ f"arn:aws:social-messaging:{self.region}:{self.account}:phone-number-id/*"])

        amazon_connect_policy = iam.PolicyStatement(
            actions=["connect:StartChatContact", "connect:StartContactStreaming"],
            resources=[
                f"arn:aws:connect:*:{self.account}:instance/*",
                f"arn:aws:connect:*:{self.account}:instance/*/contact/*",
                f"arn:aws:connect:*:{self.account}:instance/*/contact-flow/*",
            ],
        )

        transcribe_policy = iam.PolicyStatement(actions=["transcribe:Start*"], resources=["*"])

        self.lambda_functions.connect_event_handler.add_to_role_policy(eum_policy)
        self.lambda_functions.whatsapp_event_handler.add_to_role_policy(eum_policy)
        self.lambda_functions.whatsapp_event_handler.add_to_role_policy(amazon_connect_policy)
        self.lambda_functions.transcribe_audio.add_to_role_policy(transcribe_policy)

        self.s3_bucket.grant_read_write(self.lambda_functions.whatsapp_event_handler)
        self.s3_bucket.grant_read_write(self.lambda_functions.convert_to_wav)
        self.s3_bucket.grant_read(self.lambda_functions.transcribe_audio)

        self.topic_messages_in.allow_principal("social-messaging.amazonaws.com")
        self.topic_messages_out.allow_principal("connect.amazonaws.com")

        self.config_parameters.grant_read(self.lambda_functions.whatsapp_event_handler)


    def create_parameters(self):
        self.config_parameters = self.create_ssm_parameter( config.CONFIG_PARAM_NAME, json.dumps(config.CONFIG_PARAM_INITIAL_CONTENT))
        self.create_ssm_parameter(config.TOPIC_PARAM_NAME, self.topic_messages_in.topic.topic_arn)



    def create_ssm_parameter(self, parameter_name: str, string_value: str):
        return ssm.StringParameter(
            self,
            parameter_name.replace("/", "").replace("_", "").title(),
            parameter_name=parameter_name,
            string_value=string_value,
        )
