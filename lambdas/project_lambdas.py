from aws_cdk import ( Duration, aws_lambda)
from constructs import Construct


LAMBDA_TIMEOUT = 30

BASE_LAMBDA_CONFIG = dict(
    timeout=Duration.seconds(LAMBDA_TIMEOUT),
    memory_size=512,
    runtime=aws_lambda.Runtime.PYTHON_3_13,
    architecture=aws_lambda.Architecture.ARM_64,
    tracing=aws_lambda.Tracing.ACTIVE,
)


from layers import TranscribeClient, RequestsLayer

class Lambdas(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        TranscribeLayer = TranscribeClient(self, "TranscribeLayer")
        RequestsLib = RequestsLayer(self, "RequestsLayer")

        # ======================================================================
        # Message RAW
        # ======================================================================
        self.on_raw_messages = aws_lambda.Function(
            self,
            "RawMessage",
            code=aws_lambda.Code.from_asset("./lambdas/code/on_raw_messages/"),
            handler="lambda_function.lambda_handler",
            **BASE_LAMBDA_CONFIG, # type: ignore
        )

        # ======================================================================
        # Message Aggregator
        # ======================================================================
        self.message_aggregator = aws_lambda.Function(
            self,
            "MessageAggr",
            code=aws_lambda.Code.from_asset("./lambdas/code/message_aggregator/"),
            handler="lambda_function.lambda_handler",
            **BASE_LAMBDA_CONFIG, # type: ignore
        )


        # ======================================================================
        # Inbound Messages (Buffered)
        # ======================================================================
        self.whatsapp_event_handler = aws_lambda.Function(
            self,
            "WhatsappIn",
            code=aws_lambda.Code.from_asset("./lambdas/code/whatsapp_event_handler/"),
            handler="lambda_function.lambda_handler",
            layers=[TranscribeLayer.layer, RequestsLib.layer],
            **BASE_LAMBDA_CONFIG, # type: ignore
        )


        # ======================================================================
        # Connect OUT
        # ======================================================================
        self.connect_event_handler = aws_lambda.Function(
            self,
            "ConnectOut",
            code=aws_lambda.Code.from_asset("./lambdas/code/connect_event_handler/"),
            handler="lambda_function.lambda_handler",
            **BASE_LAMBDA_CONFIG, # type: ignore
        )




    def get_all_functions(self):
        return [
            self.whatsapp_event_handler,
            self.connect_event_handler,
            self.on_raw_messages,
            self.message_aggregator
        ]