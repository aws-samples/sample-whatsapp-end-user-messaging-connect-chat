from aws_cdk import ( Duration, aws_lambda)
from constructs import Construct


LAMBDA_TIMEOUT = 900

BASE_LAMBDA_CONFIG = dict(
    timeout=Duration.seconds(LAMBDA_TIMEOUT),
    memory_size=128,
    runtime=aws_lambda.Runtime.PYTHON_3_13,
    architecture=aws_lambda.Architecture.ARM_64,
    tracing=aws_lambda.Tracing.ACTIVE,
)

class Lambdas(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        # ======================================================================
        # Get a customer number from Company Systems (dummy)
        # ======================================================================
        self.get_customer_data = aws_lambda.Function(
            self,
            "GetCustomerData",
            code=aws_lambda.Code.from_asset("./lambdas/code/get_customer_data/"),
            handler="lambda_function.lambda_handler",
            **BASE_LAMBDA_CONFIG, # type: ignore
        )

        # ======================================================================
        # Send a Whatsapp Using Template
        # ======================================================================
        self.send_whatsapp_message = aws_lambda.Function(
            self,
            "SendWhatsappMessage",
            code=aws_lambda.Code.from_asset("./lambdas/code/send_whatsapp_message/"),
            handler="lambda_function.lambda_handler",
            **BASE_LAMBDA_CONFIG, # type: ignore
        )

    def get_all_functions(self):
        return [self.send_whatsapp_message, self.get_customer]