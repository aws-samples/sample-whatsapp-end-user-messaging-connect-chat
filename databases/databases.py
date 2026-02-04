from aws_cdk import (
    RemovalPolicy,
    aws_dynamodb as ddb
)
from constructs import Construct


TABLE_CONFIG = dict (removal_policy=RemovalPolicy.DESTROY, billing_mode= ddb.BillingMode.PAY_PER_REQUEST)

class Tables(Construct):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        self.active_connections = ddb.Table(
            self, "WAChats", 
            partition_key=ddb.Attribute(name="contactId", type=ddb.AttributeType.STRING),
            time_to_live_attribute='date',
            **TABLE_CONFIG) # type: ignore

        self.active_connections.add_global_secondary_index(
            index_name='customerId-index',
            partition_key=ddb.Attribute(name="customerId", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="channel", type=ddb.AttributeType.STRING),
        )

        #Table uses as temporal containment of raw messages in order to buffer, pre-process or do nothing with them.
        self.raw_messages = ddb.Table(
            self, "RawWAMsg",
            partition_key=ddb.Attribute(name="from", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="id", type=ddb.AttributeType.STRING),
            stream=ddb.StreamViewType.NEW_IMAGE,
            time_to_live_attribute='timestamp',
            **TABLE_CONFIG) # type: ignore
