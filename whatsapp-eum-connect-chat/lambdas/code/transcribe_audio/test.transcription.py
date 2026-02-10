from lambda_function import lambda_handler

event = {'location': 's3://waba-eum-connect-chat-s3486f821d-mrwmp7rdz9bd/attachment_1552757449350769.ogg'}


print(lambda_handler(event, None))
