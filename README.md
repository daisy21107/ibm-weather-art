# aiweather

*Raspberry Pi 4 powered kiosk dashboard that mixes live weather, news, YouTube‑radio loops and IBM watsonx.ai text generation, all wrapped in a touch‑friendly Kivy UI.*

---

# IBM – 3D‑Printed AI Weather Art

An AI‑enabled, **3D‑printed kinetic art** companion aimed at supporting elderly individuals living alone. The installation blends the software in *aiweather* with a physical sculpture, using IBM Watson Assistant for conversation, live weather forecasting, voice interaction, and personalised media suggestions.

## Project Objectives

* Display live weather information in a **mechanical, artistic form**
* Use **voice commands** to read and reply to text messages
* Recommend and play **podcasts or music** suited to the user’s taste and mood
* Read daily news and suggest **positive activities**
* Make AI technology feel **friendly, familiar, and approachable**

---

## 📂 Project layout

```text
/home/pi/aiweather            # ← clone repo into this exact folder name
├── UI/                       # Kivy front‑end
│   └── main.py               # application entry‑point
├── requirements.txt          # python dependencies
├── setup.sh                  # one‑shot bootstrap script
├── data/                     # runtime downloads & cache
└── …                         # other source files, assets, docs
```

> **Why */home/pi/aiweather*?**  Cloning directly into that folder keeps everything self‑contained, making backups and SD‑card migrations dead‑simple.

---

## 🚀 First‑time installation (fresh Pi)

```bash
# 1) grab the code
cd /home/pi
git clone --depth 1 https://github.com/daisy21107/ibm-weather-art.git aiweather
cd aiweather

# 2) make the helper executable
chmod +x setup.sh

# 3) let the script do its thing (takes ~5–10 min on a Pi‑4)
./setup.sh
```

What *setup.sh* actually does:

| Phase              | Actions                                                                                                                   |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| **📦 System libs** | `sudo apt update && sudo apt install …` pulls SDL2, GStreamer, libVLC, OpenGL ES headers—the C libraries Kivy & VLC need. |
| **🐍 Virtual‑env** | Creates `iwa-venv/` using `python -m venv`, then upgrades `pip setuptools wheel`.                                         |
| **🔌 Python deps** | Installs `torch==2.3.0` first (quickest on ARM) and the rest of `requirements.txt`.                                   |
| **🔑 Secrets**     | Generates a blank `.env` with placeholders for API keys. Edit it before running the app!                                  |
| **📂 Folders**     | Ensures an empty `data/` directory exists, plus redirects all package caches into `./.cache/`.                            |

> **Note:** you can safely re‑run *setup.sh* after a `git pull`; it skips anything already done.

---

## 🔑 Fill in your API keys

Open `.env` in the repo root and add the credentials you obtained from each provider:

```ini
WATSONX_AI_URL=https://...-api.ai.cloud.ibm.com
WATSONX_API_KEY=************************
WATSONX_PROJECT_ID=xxxxxxxx-xxxx…
WATSONX_MODEL_ID=google/flan-t5-xl
OPENWEATHER_KEY=************************
GUARDIAN_KEY=************************
```
---

## ▶️ How to run (daily use)

```bash
cd /home/pi/aiweather
source iwa-venv/bin/activate   # activate the environment
python UI/main.py              # launch the kiosk UI
```

### Updating later

```bash
cd /home/pi/aiweather
git pull                        # grab latest commits
./setup.sh                      # installs new deps if any
source iwa-venv/bin/activate
python UI/main.py
```

---

## 🛠️ Optional tweaks

| Use‑case                  | Command / file                                                                                                             |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Smoother GL & hide cursor | Add to `~/.bashrc`:<br>`export KIVY_GL_BACKEND=sdl2`<br>`export KIVY_WINDOW=sdl2`                                          |
| Auto‑start on boot        | Create a systemd service pointing to `ExecStart=/home/pi/aiweather/iwa-venv/bin/python /home/pi/aiweather/UI/main.py`      |
| Clean rebuild             | `rm -rf iwa-venv && ./setup.sh`                                                                                            |

---

## 🤕 Troubleshooting

| Symptom                                   | Likely cause                         | Fix                                                                          |
| ----------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------- |
| `ModuleNotFoundError: '_ffi'`             | Forgot to run the `apt install` part | Rerun `./setup.sh` (it will trigger the apt block).                          |
| Window opens then crashes with GL error   | Old Pi OS driver                     | Enable the FKMS driver in `sudo raspi-config` or set `KIVY_GL_BACKEND=sdl2`. |
| `ImportError: libvlc.so.5`                | VLC dev lib missing                  | `sudo apt install libvlc-dev` (already in script).                           |

---

Happy hacking—pull requests welcome! 🚀
