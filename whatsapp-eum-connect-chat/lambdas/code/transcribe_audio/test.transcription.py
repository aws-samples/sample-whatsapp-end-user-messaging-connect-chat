from lambda_function import lambda_handler

event = {'location': 'xxx.ogg'}


print(lambda_handler(event, None))
