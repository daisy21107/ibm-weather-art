import os
from ibm_watson import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

# Read from .env / environment
API_KEY = os.getenv("IBM_STT_APIKEY")
URL     = os.getenv("IBM_STT_URL")

def transcribe_audio_ibm(filename: str = 'output.wav') -> str:
    """
    Reads IBM_STT_APIKEY and IBM_STT_URL from environment,
    sends the WAV file to Watson STT, and returns the full transcript.
    """
    if not API_KEY or not URL:
        raise RuntimeError("IBM STT credentials not set in environment")

    print(f"[STT] Using file: {filename}")
    print(f"[STT] Using API key: {'****' + API_KEY[-4:]}")
    print(f"[STT] Using URL: {URL}")

    try:
        authenticator = IAMAuthenticator(API_KEY)
        stt_service = SpeechToTextV1(authenticator=authenticator)
        stt_service.set_service_url(URL)

        with open(filename, 'rb') as audio_file:
            response = stt_service.recognize(
                audio=audio_file,
                content_type='audio/wav',
                model='en-US_BroadbandModel'
            ).get_result()

        transcripts = [
            alt["transcript"]
            for result in response.get("results", [])
            for alt in result.get("alternatives", [])
        ]

        if not transcripts:
            print("[STT] No transcript returned.")
        else:
            print(f"[STT] Transcript: {' '.join(transcripts)}")

        return " ".join(transcripts).strip()

    except Exception as e:
        print(f"[STT ERROR] {e}")
        return ""

if __name__ == "__main__":
    print(transcribe_audio_ibm())
