from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

authenticator = IAMAuthenticator('{apikey}')
assistant = AssistantV2(
    version='2024-08-25',
    authenticator=authenticator
)

assistant.set_service_url('https://api.us-east.assistant.watson.cloud.ibm.com')