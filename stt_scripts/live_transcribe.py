# python3 transcibe.py -t 5
# above is an example of how to run the script for 5 seconds

import argparse
import base64
import configparser
import json
import threading
import time

import pyaudio
import websocket
from websocket._abnf import ABNF

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 5
FINALS = []
LAST = None

def read_audio(ws, timeout):
    """Read audio and sent it to the websocket port.

    This uses pyaudio to read from a device in chunks and send these
    over the websocket wire.

    """
    global RATE
    p = pyaudio.PyAudio()
    RATE = int(p.get_default_input_device_info()['defaultSampleRate'])
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("* recording")
    rec = timeout or RECORD_SECONDS

    for i in range(0, int(RATE / CHUNK * rec)):
        data = stream.read(CHUNK)
        ws.send(data, ABNF.OPCODE_BINARY)

    # Disconnect the audio stream
    stream.stop_stream()
    stream.close()
    print("* done recording")
    data = {"action": "stop"}
    ws.send(json.dumps(data).encode('utf8'))
    time.sleep(1)
    ws.close()

    p.terminate()


def on_message(self, msg):
    """Print whatever messages come in.

    While we are processing any non trivial stream of speech Watson
    will start chunking results into bits of transcripts that it
    considers "final", and start on a new stretch. It's not always
    clear why it does this. However, it means that as we are
    processing text, any time we see a final chunk, we need to save it
    off for later.
    """
    global LAST
    data = json.loads(msg)
    if "results" in data:
        if data["results"][0]["final"]:
            FINALS.append(data)
            LAST = None
        else:
            LAST = data
        # This prints out the current fragment that we are working on
        print(data['results'][0]['alternatives'][0]['transcript'])


def on_error(self, error):
    """Print any errors."""
    print(error)


def on_close(ws, close_status_code, close_msg):
    """Upon close, print the complete and final transcript."""
    global LAST
    if LAST:
        FINALS.append(LAST)
    transcript = "".join([x['results'][0]['alternatives'][0]['transcript']
                          for x in FINALS])
    print(transcript)


def on_open(ws):
    """Triggered as soon a we have an active connection."""
    args = ws.args
    data = {
        "action": "start",
        # this means we get to send it straight raw sampling
        "content-type": "audio/l16;rate=%d" % RATE,
        "continuous": True,
        "interim_results": True,
        # "inactivity_timeout": 5, # in order to use this effectively
        "word_confidence": True,
        "timestamps": True,
        "max_alternatives": 3
    }

    ws.send(json.dumps(data).encode('utf8'))
    threading.Thread(target=read_audio,
                     args=(ws, args.timeout)).start()

def get_url():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    # See
    # https://console.bluemix.net/docs/services/speech-to-text/websockets.html#websockets
    # for details on which endpoints are for each region.
    region = config.get('auth', 'region')
    return ('wss://api.eu-gb.speech-to-text.watson.cloud.ibm.com/'
            'v1/recognize?model=en-US_BroadbandModel')

def get_auth():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    apikey = config.get('auth', 'apikey')
    return ("apikey", apikey)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Transcribe Watson text in real time')
    parser.add_argument('-t', '--timeout', type=int, default=5)
    # parser.add_argument('-d', '--device')
    # parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    return args


def main():
    # Connect to websocket interfaces
    headers = {}
    userpass = ":".join(get_auth())
    headers["Authorization"] = "Basic " + base64.b64encode(
        userpass.encode()).decode()
    url = get_url()

    # If you really want to see everything going across the wire,
    # uncomment this. However realize the trace is going to also do
    # things like dump the binary sound packets in text in the
    # console.
    # websocket.enableTrace(True)
    ws = websocket.WebSocketApp(url,
                                header=headers,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.args = parse_args()
    import certifi
    ws.run_forever(sslopt={"ca_certs": certifi.where()})


if __name__ == "__main__":
    main()
