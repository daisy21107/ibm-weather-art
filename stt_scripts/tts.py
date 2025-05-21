from ibm_watson import TextToSpeechV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

API_KEY = "81uEaSJz4IcVNQX6CyZFU5YPjCcjnWH_1iQcmFkUiV_T"
URL = "https://api.eu-gb.text-to-speech.watson.cloud.ibm.com/instances/a5f2f9b1-296c-4f01-b904-3b7384f91933"

def text_to_speech_ibm(text, output_filename='output_speech.wav'):
    api_key = API_KEY
    url = URL

    authenticator = IAMAuthenticator(api_key)
    text_to_speech = TextToSpeechV1(authenticator=authenticator)
    text_to_speech.set_service_url(url)

    # Synthesize speech
    response = text_to_speech.synthesize(
        text,
        voice='en-US_MichaelV3Voice',  # You can change voice
        accept='audio/wav'
    ).get_result()

    with open(output_filename, 'wb') as audio_file:
        audio_file.write(response.content)

    print(f"Speech audio saved to '{output_filename}'")

if __name__ == "__main__":
    text = input("Enter the text you want to synthesize to speech:\n")
    text_to_speech_ibm(text)