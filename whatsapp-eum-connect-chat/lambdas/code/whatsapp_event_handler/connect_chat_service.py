import boto3
import os
import sys
import requests
from urllib.parse import urlparse
from botocore.exceptions import ClientError

participant_client = boto3.client("connectparticipant")
connect_client = boto3.client("connect")


class ChatService:
    def __init__(
        self,
        instance_id=os.environ.get("INSTANCE_ID"),
        contact_flow_id=os.environ.get("CONTACT_FLOW_ID"),
        chat_duration_minutes=60,
        topic_arn = os.environ.get("TOPIC_ARN")
    ) -> None:
        self.participant = boto3.client("connectparticipant")
        self.connect = boto3.client("connect")
        self.contact_flow_id = contact_flow_id
        self.instance_id = instance_id
        self.chat_duration_minutes = chat_duration_minutes
        self.topic_arn = topic_arn

    def start_chat(
        self, message, phone, channel, name="unknown", systemNumber="unknown"
    ):

        start_chat_response = self.connect.start_chat_contact(
            InstanceId=self.instance_id,
            ContactFlowId=self.contact_flow_id,
            Attributes={
                "Channel": channel,
                "customerId": phone,
                "customerName": name,
                "systemNumber": systemNumber,
            },
            ParticipantDetails={"DisplayName": name},
            InitialMessage={"ContentType": "text/plain", "Content": message},
            ChatDurationInMinutes=self.chat_duration_minutes,
            SupportedMessagingContentTypes=[
                "text/plain",
                "text/markdown",
                "application/json",
                "application/vnd.amazonaws.connect.message.interactive",
                "application/vnd.amazonaws.connect.message.interactive.response",
            ],
        )
        print (start_chat_response)
        return start_chat_response

    def send_message_with_retry_connection(self,text, message, connectionToken):
        customer_name = message.message.get("customer_name", "NN")
        result = self.send_message(text, connectionToken)
        if result == "ACCESS_DENIED":
            contactId, participantToken, connectionToken = (
                self.start_chat_and_stream(
                    text or "New conversation with attachment",
                    message.phone_number,
                    "Whatsapp",
                    customer_name,
                    message.phone_number_id,
                )
            )
            return contactId, participantToken, connectionToken
        return None, None, None

    def attach_file_with_retry_connection(self, message, connections, fileContents, fileName, fileType, connectionToken):
        """Attach file with retry logic: if chat expired, start a new one and retry."""
        attachment_id, error_str = self.attach_file(
            fileContents=fileContents, fileName=fileName, fileType=fileType, ConnectionToken=connectionToken
        )

        if error_str == "ACCESS_DENIED":
            # Chat expired — start a new one
            customer_name = message.message.get("customer_name", "NN")
            text = message.get_text() or "New conversation with attachment"

            contactId, participantToken, newConnectionToken = self.start_chat_and_stream(
                text, message.phone_number, "Whatsapp", customer_name, message.phone_number_id
            )

            # Update connection in DynamoDB
            contact = connections.get_contact(message.phone_number)
            if contact:
                connections.remove_contactId(contact["contactId"])
            connections.update_contact(
                message.phone_number, "Whatsapp", contactId,
                participantToken, newConnectionToken, customer_name, message.phone_number_id
            )

            # Retry with new connection
            attachment_id, error_str = self.attach_file(
                fileContents=fileContents, fileName=fileName, fileType=fileType, ConnectionToken=newConnectionToken
            )

        return attachment_id, error_str


        
    def send_message(self, message, connectionToken):
        try:
            self.participant.send_message(ContentType="text/plain", Content=message, ConnectionToken=connectionToken)
            return None
        except self.participant.exceptions.AccessDeniedException as e:
            print(f"Access denied: {e}. Check your IAM permissions or connection token validity.")
            return "ACCESS_DENIED"
        except self.participant.exceptions.InternalServerException as e:
            print(f"Internal server error: {e}. Please try again later.")
            return "SERVER_EXCEPTION"
        except self.participant.exceptions.ThrottlingException as e:
            print(f"Request throttled: {e}. Reduce request frequency or implement backoff strategy.")
            return "THROTTILING"
        except self.participant.exceptions.ValidationException as e:
            print(f"Validation error: {e}. Check your message content and connection token format.")
            return "VALIDATION_ERROR"
        except self.participant.exceptions.ServiceQuotaExceededException as e:
            print(f"Service quota exceeded: {e}. Reduce message frequency or request quota increase.")
            return "QUOTA_ERROR"
        except Exception as e:
            print(f"Unexpected error: {e}")
            return "UNEXEPECTED_ERROR"


    def start_stream(self, ContactId):
        if not self.topic_arn:
            print ("Missing Topic ARN for start streamming")
            return None

        start_stream_response = connect_client.start_contact_streaming(
            InstanceId=self.instance_id,
            ContactId=ContactId,
            ChatStreamingConfiguration={"StreamingEndpointArn": self.topic_arn})
        
        return start_stream_response

    def start_chat_and_stream( self, message, phone, channel, name="unknown", systemNumber="unknown"):
        start_chat_response         = self.start_chat(message, phone, channel, name, systemNumber)

    
        participantToken             = start_chat_response["ParticipantToken"]
        contactId                   = start_chat_response['ContactId']
        
        start_stream_response       = self.start_stream(contactId)
        create_connection_response  = self.create_connection(participantToken)
        connectionToken             = create_connection_response['ConnectionCredentials']['ConnectionToken']

        return contactId, participantToken, connectionToken

    def create_connection(self, ParticipantToken):

        create_connection_response = self.participant.create_participant_connection(
            Type=["CONNECTION_CREDENTIALS"],
            ParticipantToken=ParticipantToken,
            ConnectParticipant=True
        )
        return create_connection_response

    def get_signed_url(self, connectionToken, attachment):
        try:
            response = self.participant.get_attachment(
                AttachmentId=attachment, ConnectionToken=connectionToken
            )
        except ClientError as e:
            print("Get attachment failed")
            print(e.response["Error"]["Code"])
            return None
        else:
            return response["Url"]

    def attach_file(self, fileContents,fileName,fileType,ConnectionToken):
        
        fileSize = sys.getsizeof(fileContents) - 33 ## Removing BYTES overhead
        print("Size downloaded:" + str(fileSize))
        try:
            attachResponse = participant_client.start_attachment_upload(
            ContentType=fileType,
            AttachmentSizeInBytes=fileSize,
            AttachmentName=fileName,
            ConnectionToken=ConnectionToken
            )
        except self.participant.exceptions.AccessDeniedException as e:
            print(f"Access denied: {e}. Check your IAM permissions or connection token validity.")
            return None, "ACCESS_DENIED"
        except self.participant.exceptions.InternalServerException as e:
            print(f"Internal server error: {e}. Please try again later.")
            return  None, "SERVER_EXCEPTION"
        except self.participant.exceptions.ThrottlingException as e:
            print(f"Request throttled: {e}. Reduce request frequency or implement backoff strategy.")
            return  None, "THROTTILING"
        except self.participant.exceptions.ValidationException as e:
            print(f"Validation error: {e}. Check your message content and connection token format.")
            return  None, "VALIDATION_ERROR"
        except self.participant.exceptions.ServiceQuotaExceededException as e:
            print(f"Service quota exceeded: {e}. Reduce message frequency or request quota increase.")
            return  None, "QUOTA_ERROR"
        except Exception as e:
            print(f"Unexpected error: {e}")
            return  None, "UNEXEPECTED_ERROR"
        else:
            try:
                upload_url = attachResponse['UploadMetadata']['Url']
                
                # Validate URL scheme and domain for security (prevents file:// scheme attacks)
                parsed_url = urlparse(upload_url)
                
                # Explicitly block file:// scheme
                if parsed_url.scheme == 'file':
                    print("Rejected file:// URL scheme - local file access not allowed")
                    return None, "file:// URLs are not allowed"
                
                # Only allow HTTPS scheme
                if parsed_url.scheme != 'https':
                    print(f"Rejected non-HTTPS URL scheme: {parsed_url.scheme}")
                    return None, f"Only HTTPS URLs are allowed, got: {parsed_url.scheme}"
                
                # Ensure netloc exists (prevents malformed URLs)
                if not parsed_url.netloc:
                    print("Rejected URL with missing domain")
                    return None, "Invalid URL: missing domain"
                
                # Only allow AWS domains
                if not parsed_url.netloc.endswith('.amazonaws.com'):
                    print(f"Rejected non-AWS domain: {parsed_url.netloc}")
                    return None, f"Only AWS domains are allowed"
                
                # Upload file using requests
                filePostingResponse = requests.put(
                    upload_url,
                    data=fileContents,
                    headers=attachResponse['UploadMetadata']['HeadersToInclude'],
                    timeout=30
                )
                filePostingResponse.raise_for_status()
            except Exception as e:
                print("Error while uploading")
                print(str(e))
                return None, str(e)
            else:
                print(filePostingResponse.status_code) 
                verificationResponse = participant_client.complete_attachment_upload(
                    AttachmentIds=[attachResponse['AttachmentId']],
                    ConnectionToken=ConnectionToken)
                print("Verification Response")
                #print(verificationResponse)
                return attachResponse['AttachmentId'], None
