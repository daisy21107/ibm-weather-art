from ibm_watson import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

API_KEY = 'tPXH4Q0IxwmYuO0NwVhOCEeHvxOBhcBRvxKHeyT-7z2v'
URL = 'https://api.eu-gb.speech-to-text.watson.cloud.ibm.com/instances/5e463547-3ba5-4a81-922d-7643a51e08c5'

def transcribe_audio_ibm(filename='output.wav'):
    api_key = API_KEY
    url = URL
    # initialize the IBM Watson Speech to Text service with API key and URL

    authenticator = IAMAuthenticator(api_key)
    speech_to_text = SpeechToTextV1(authenticator=authenticator)
    speech_to_text.set_service_url(url)

    with open(filename, 'rb') as audio_file:
        response = speech_to_text.recognize(
            audio=audio_file,
            content_type='audio/wav',
            model='en-US_BroadbandModel'
        ).get_result()
    
    for result in response['results']:
        print(f"Transcript: {result['alternatives'][0]['transcript']}")

if __name__ == "__main__":
    transcribe_audio_ibm()