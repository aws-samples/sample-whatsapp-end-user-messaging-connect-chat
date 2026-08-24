import json
import os
import logging


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    return {
        "fullName": "Enrique Rodriguez",
        "phoneNumber": "+XXXXXXXXX",
        "input4": "Entregado",
        "input3": "Puzzle 1000 piezas",
        "input2": "P12345",
        "input1": "Enrique",
    }
