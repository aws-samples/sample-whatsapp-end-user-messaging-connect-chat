import json
from constructs import Construct
from aws_cdk import aws_lambda as _lambda


class TranscribeClient(Construct):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.layer = _lambda.LayerVersion(
            self,
            "Transcribe Streaming",
            code=_lambda.Code.from_asset("./layers/transcribe-client-new.zip"),
            compatible_runtimes=[
                _lambda.Runtime.PYTHON_3_12,
                _lambda.Runtime.PYTHON_3_13,
            ],
            description="aws-sdk-transcribe-streaming",
        )


class RequestsLayer(Construct):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.layer = _lambda.LayerVersion(
            self,
            "Requests Library",
            code=_lambda.Code.from_asset("./layers/requests.zip"),
            compatible_runtimes=[
                _lambda.Runtime.PYTHON_3_10,
                _lambda.Runtime.PYTHON_3_11,
                _lambda.Runtime.PYTHON_3_12,
                _lambda.Runtime.PYTHON_3_13,
            ],
            description="Requests HTTP Library",
        )


class FFMpeg(Construct):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.layer = _lambda.LayerVersion(
            self,
            "FFMpeg",
            code=_lambda.Code.from_asset("./layers/ffmpeg.zip"),
            compatible_runtimes=[
                _lambda.Runtime.PYTHON_3_10,
                _lambda.Runtime.PYTHON_3_11,
                _lambda.Runtime.PYTHON_3_12,
                _lambda.Runtime.PYTHON_3_13,
            ],
        )
