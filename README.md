
# aiweather

*Raspberry Pi 4B powered kiosk dashboard that mixes live weather, news, YouTube-radio loops and IBM watsonx.ai text generation, all wrapped in a touch-friendly Kivy UI.*

---

# IBM – 3D-Printed AI Weather Art

An AI-enabled, **3D-printed case** companion aimed at supporting elderly individuals living alone. The installation blends the software in *aiweather* with a physical sculpture, using IBM Watson Assistant for conversation, live weather forecasting, voice interaction, and personalised media suggestions.

## Project Objectives

* Enable **multimodal interaction**  
  * 🎤 **Mic button** → speech-to-text only (fills the search bar)  
  * 🎙️ **Request** – feeds that text to NLU and can **fetch weather, pull topic-based news, start YouTube music, or add / cancel reminders**.  
  * 🤖 **Ask AI**  → free-form advice from IBM Watson, spoken aloud  
  * ⌨️ **Virtual keyboard** → typing fallback for all queries  
* Read **daily news aloud**—swipe headlines with *Refresh News* or tap **Read News** to hear the current article.  
* Let users **search, stream, and control music** from YouTube with large, touch-friendly buttons.  
* Offer a **weekly reminder grid** that persists across shutdowns and auto-clears every Monday.  
* Maintain an intuitive, emoji-rich interface that feels **friendly, familiar, and approachable**—especially for elderly users.

---

## 📦 Recommended hardware

| Part | Tested model | Buy-link |
|------|--------------|----------|
| 7″ Touch display | Official Raspberry Pi 7-inch display | <https://uk.rs-online.com/web/p/raspberry-pi-screens/8997466?gb=s> |
| USB microphone | Mini USB Microphone | <https://thepihut.com/products/mini-usb-microphone> |
| USB speaker | Mini External USB Stereo Speaker | <https://thepihut.com/products/mini-external-usb-stereo-speaker?variant=31955934801> |

---

## 📂 Project layout

```text
/home/pi/aiweather            # ← clone repo into this exact folder name
├── UI/                       # Kivy front-end
│   └── main.py               # application entry-point
├── requirements.txt          # python dependencies
├── setup.sh                  # one-shot bootstrap script
├── run.sh                    # programme starting script
├── data/                     # runtime downloads & cache
└── …                         # other source files, assets, docs
```

---

## 🚀 First-time installation (fresh Pi)

```bash
# 1) grab the code
cd /home/pi
git clone --depth 1 https://github.com/daisy21107/ibm-weather-art.git aiweather
cd aiweather

# 2) make the helper executable
chmod +x setup.sh

# 3) let the script do its thing (takes ~5–10 min on a Pi-4)
./setup.sh
```

---

## 🔑 Fill in your API keys

An empty `.env` will be created in the repo root by executing `./setup.sh` and add the credentials you obtained from each provider manually:

```ini
GUARDIAN_KEY=
OPENWEATHER_KEY=
IBM_STT_APIKEY=
IBM_STT_URL=
IBM_TTS_APIKEY=
IBM_TTS_URL=
WATSONX_AI_URL=
WATSONX_API_KEY=
WATSONX_PROJECT_ID=
WATSONX_MODEL_ID=
```

---

## ▶️ How to run (daily use)

Make sure the wifi connected
Just double-click the **AIWeather** icon that the installer put on your Desktop.

```bash
/home/pi/aiweather/run.sh       # does the same thing as the icon
```

### Updating later

```bash
cd /home/pi/aiweather
git pull
./setup.sh
```

---

## 👆 User manual

| UI area / button | Action | What happens |
|------------------|--------|--------------|
| **🎙️ Request** | Tap once | Sends the text in the search bar to NLU → routes to weather / news / music / reminder skills. |
| **🤖 Ask AI** | Tap once | Sends your prompt to the IBM Watson chatbot and reads the reply aloud. |
| **🌦️ Weather card** | Auto-refresh or search | Shows the latest temperature for the chosen city. |
| **📰 Refresh News** | Tap once | Loads the next Guardian headline. |
| **🗣️ Read News** | Tap once | IBM TTS speaks the current headline + preview through the USB speaker. |
| **🎤 Mic (Hold-to-talk)** | Hold → speak → release | Records audio → Watson STT → puts transcript in the search bar. |
| **🎵 Music search** | Search artist or song | Runs a YouTube search, lets you pick a track, then streams it. |
| **⏯ / ⏹ / ↩10 s / ↪10 s** | Playback controls | Play / pause, stop, seek backward 10 s, seek forward 10 s. |
| **🔔 Reminders** | Tap summary | Opens weekly grid; edit reminders via speech or typing. |


---

## 🤕 Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `setup.sh` stalls on `apt-get` / `pip` | Pi offline or DNS failure | Check Wi-Fi & DNS, then rerun `./setup.sh` once the connection is stable. |
| “Guardian API error” banner | Wrong `GUARDIAN_KEY` or quota exhausted | Verify key in `.env`; free tier is 12 000 calls/day. |
| Weather card shows “API error” | `OPENWEATHER_KEY` missing/invalid or exceeded | Double-check `.env`; free tier is 60 calls/min. |
| IBM STT or TTS fails (“401 Unauthorized”) | Wrong URL vs region or bad key | Re-paste keys *and* URLs from IBM dashboard into `.env`. |
| `ModuleNotFoundError: '_ffi'` | Skipped the `apt install` block | Rerun `./setup.sh` (it reinstalls system deps). |
| Window opens then crashes with GL / `bcm2835` error | Legacy GL driver | Enable FKMS in `sudo raspi-config` or `export KIVY_GL_BACKEND=sdl2`. |
| USB speaker silent / sample-rate error | TTS returned 22 kHz WAV | App auto-resamples; if you still see `Invalid sample rate`, reboot the Pi (rare ALSA quirk). |

---

Happy hacking — pull requests welcome! 🚀
