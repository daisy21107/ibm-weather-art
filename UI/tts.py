import os
from ibm_watson import TextToSpeechV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

# Read from .env / environment
API_KEY = os.getenv("IBM_TTS_APIKEY")
URL     = os.getenv("IBM_TTS_URL")

def text_to_speech_ibm(text: str, output_filename: str = 'output_speech.wav') -> None:
    """
    Reads IBM_TTS_APIKEY and IBM_TTS_URL from environment,
    synthesizes the given text into WAV via Watson TTS,
    and writes to output_filename.
    """
    if not API_KEY or not URL:
        raise RuntimeError("IBM TTS credentials not set in environment")

    authenticator = IAMAuthenticator(API_KEY)
    tts_service = TextToSpeechV1(authenticator=authenticator)
    tts_service.set_service_url(URL)

    response = tts_service.synthesize(
        text,
        voice='en-US_MichaelV3Voice',
        accept='audio/wav;rate=48000'
    ).get_result()

    with open(output_filename, 'wb') as audio_file:
        audio_file.write(response.content)

if __name__ == "__main__":
    user_text = input("Enter text to synthesize:\n")
    text_to_speech_ibm(user_text)
