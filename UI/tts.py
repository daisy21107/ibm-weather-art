# tts.py  – Watson Text-to-Speech helper  (persistent client version)
# ────────────────────────────────────────────────────────────────────
import os
from pathlib import Path
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson import TextToSpeechV1

# ─── credentials from environment / UI/.env ─────────────────────────
API_KEY = os.getenv("IBM_TTS_APIKEY")
URL     = os.getenv("IBM_TTS_URL")

if not API_KEY or not URL:
    raise RuntimeError("IBM TTS credentials (IBM_TTS_APIKEY / IBM_TTS_URL) "
                       "are missing – set them in UI/.env")

# ─── build ONE authenticator + client at import-time ─────────────────
_authenticator = IAMAuthenticator(API_KEY)
_TTS_CLIENT    = TextToSpeechV1(authenticator=_authenticator)
_TTS_CLIENT.set_service_url(URL)

# the Watson SDK already keeps an internal `requests.Session`,
# so just re-using the same TextToSpeechV1 instance is enough
# to benefit from connection-pooling / HTTP keep-alive.

# ─── public API  -----------------------------------------------------
def text_to_speech_ibm(text: str,
                       output_filename: str | os.PathLike = "output_speech.wav",
                       *,
                       voice: str = "en-US_MichaelV3Voice",
                       sample_rate: int = 48_000) -> None:
    """
    Convert *text* to speech using IBM Watson and write a WAV file.

    Parameters
    ----------
    text : str
        The text you want to synthesize.
    output_filename : str | PathLike
        Where to save the generated audio.
    voice : str
        Watson voice model (default: en-US_MichaelV3Voice).
    sample_rate : int
        WAV sample-rate in Hz (default: 48000).

    Notes
    -----
    •  The global `_TTS_CLIENT` is thread-safe for concurrent `.synthesize`
       calls, so the UI can fire TTS jobs from a thread pool.
    """
    accept = f"audio/wav;rate={sample_rate}"

    # Watson call (network I/O -- may take a few seconds)
    resp = _TTS_CLIENT.synthesize(
        text, voice=voice, accept=accept
    ).get_result()

    # write the audio stream to disk
    out_path = Path(output_filename).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("wb") as fh:
        fh.write(resp.content)

# ─── quick CLI test ─────────────────────────────────────────────────
if __name__ == "__main__":
    sentence = input("Type something to synthesize → ").strip() or "Hello!"
    print("Synthesising…")
    text_to_speech_ibm(sentence, "tts_test.wav")
    print("✓ Saved to tts_test.wav")
