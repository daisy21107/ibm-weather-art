from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

import argparse
import base64
import configparser
import json
import threading
import time

import pyaudio
import websocket
from websocket._abnf import ABNF
import certifi

# Audio configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100  # Will override dynamically
FINALS = []
LAST = None

#chatbot handler function
def send_to_assistant(message_text):
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    assistant_apikey = config.get('assistant', 'apikey')
    assistant_id = config.get('assistant', 'assistant_id')
    assistant_url = config.get('assistant', 'url')

    authenticator = IAMAuthenticator(assistant_apikey)
    assistant = AssistantV2(
        version='2021-06-14',
        authenticator=authenticator
    )
    assistant.set_service_url(assistant_url)

    session = assistant.create_session(assistant_id=assistant_id).get_result()
    session_id = session['session_id']

    try:
        response = assistant.message(
            assistant_id=assistant_id,
            session_id=session_id,
            environment_id='48bceb2d-d598-4677-866a-a62a3946e656',
            input={
                'message_type': 'text',
                'text': message_text
            }
        ).get_result()

        output = response.get('output', {}).get('generic', [])
        for entry in output:
            if entry.get('response_type') == 'text':
                print("Watson Assistant: ", entry['text'])
    finally:
        assistant.delete_session(assistant_id=assistant_id, session_id=session_id)

def read_audio(ws, timeout):
    global RATE
    p = pyaudio.PyAudio()
    RATE = int(p.get_default_input_device_info()['defaultSampleRate'])

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("* Recording for", timeout, "seconds...")
    for _ in range(0, int(RATE / CHUNK * timeout)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        ws.send(data, ABNF.OPCODE_BINARY)

    stream.stop_stream()
    stream.close()
    p.terminate()

    print("* Done recording")
    ws.send(json.dumps({"action": "stop"}).encode('utf8'))
    time.sleep(1)
    ws.close()


def on_message(ws, msg):
    global LAST
    data = json.loads(msg)
    if "results" in data:
        if data["results"][0]["final"]:
            FINALS.append(data)
            LAST = None
        else:
            LAST = data
        print("📝", data['results'][0]['alternatives'][0]['transcript'].strip())


def on_error(ws, error):
    print("🚨 Error:", error)


def on_close(ws, close_status_code, close_msg):
    global LAST
    if LAST:
        FINALS.append(LAST)
    full_transcript = "".join(
        x['results'][0]['alternatives'][0]['transcript'] for x in FINALS
    ).strip()
    print("✅ Final Transcript:", full_transcript.strip())

    if full_transcript:
        send_to_assistant(full_transcript)


def on_open(ws):
    args = ws.args
    ws.send(json.dumps({
        "action": "start",
        "content-type": f"audio/l16;rate={RATE}",
        "continuous": True,
        "interim_results": True,
        "word_confidence": True,
        "timestamps": True,
        "max_alternatives": 1
    }).encode('utf8'))

    threading.Thread(target=read_audio, args=(ws, args.timeout)).start()


def get_auth_and_url():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    region = config.get('auth', 'region')
    apikey = config.get('auth', 'apikey')

    url = f"wss://api.{region}.speech-to-text.watson.cloud.ibm.com/v1/recognize?model=en-US_BroadbandModel"
    auth = "Basic " + base64.b64encode(f"apikey:{apikey}".encode()).decode()
    return url, auth


def parse_args():
    parser = argparse.ArgumentParser(description='🎙 Real-time IBM Watson STT')
    parser.add_argument('-t', '--timeout', type=int, default=5, help='Recording time in seconds')
    return parser.parse_args()

def main():
    args = parse_args()
    url, auth = get_auth_and_url()

    ws = websocket.WebSocketApp(url,
                                header={"Authorization": auth},
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.args = args

    websocket.enableTrace(False)
    ws.run_forever(sslopt={"ca_certs": certifi.where()})


if __name__ == '__main__':
    main()
