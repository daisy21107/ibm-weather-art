from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

# Replace with your IBM credentials
api_key = 'vdRE2zXQ76xvUNWLb48L08719XHJStyhwIim-zdJbl0L'
service_url = 'https://api.eu-gb.assistant.watson.cloud.ibm.com'
assistant_id = '48bceb2d-d598-4677-866a-a62a3946e656'

# Set up authenticator and assistant
authenticator = IAMAuthenticator(api_key)
assistant = AssistantV2(
    version='2021-06-14',
    authenticator=authenticator
)
assistant.set_service_url(service_url)

# Create a session
session = assistant.create_session(assistant_id=assistant_id).get_result()
session_id = session['session_id']

# Prompt to send
user_input = "Hi nice to meet you"

# Send user input
response = assistant.message(
    assistant_id=assistant_id,
    session_id=session_id,
    environment_id='48bceb2d-d598-4677-866a-a62a3946e656',
    input={
        'message_type': 'text',
        'text': user_input
    }
).get_result()

# Extract and print response
output_texts = response['output']['generic']
for message in output_texts:
    print("Assistant:", message.get('text'))

# Clean up session (optional but recommended)
assistant.delete_session(
    assistant_id=assistant_id,
    session_id=session_id
)
