# AIWeather – UI (weather • Guardian news • BERT NLU • YouTube music)

import os
import webbrowser
import html
import re
import csv
import json
import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import threading
from threading import Event
import wave
import uuid
from time import monotonic
import tempfile
import requests
from requests.exceptions import RequestException
import yt_dlp

try:
    import vlc
except ModuleNotFoundError:
    vlc = None

from kivy.config import Config
Config.set("graphics", "width",  "800")
Config.set("graphics", "height", "480")
Config.set('graphics', 'show_cursor', '1') #should change to 0 for pi

from kivy.resources import resource_add_path
from kivy.core.text import LabelBase
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.animation import Animation

from infer_onnx import infer_onnx as nlu_infer
#from BERT import infer as nlu_infer

# ─── load .env ───────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

# ─── IBM Watson helpers ──────────────────────────────────────
from stt import transcribe_audio_ibm     # must read env vars
from tts import text_to_speech_ibm       # must read env vars

# ─── Watsonx.ai Chatbot Setup ──────────────────────────────────────
from chatbot_helper import get_response

# ─── app-wide constants ────────────────────────────────────────────────
WEATHER_REFRESH_SEC    = 600      # 10 min
NEWS_REFRESH_SEC       = 300      # 5  min
MAX_REMINDERS_PER_SLOT = 3
MAX_RECORD_SEC         = 60       # audio hard limit

# ─── audio I/O setup ─────────────────────────────────────────
import pyaudio                        # sudo apt install python3-pyaudio

RATE, FORMAT, CHUNK = 44100, pyaudio.paInt16, 1024

def record_to_wav(path: str, stop_evt: Event, max_sec: int = MAX_RECORD_SEC) -> None:
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(format=FORMAT,
                         channels=1,
                         rate=RATE,
                         input=True,
                         frames_per_buffer=CHUNK)

        frames, start = [], monotonic()
        while not stop_evt.is_set() and (monotonic() - start) < max_sec:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        pa.terminate()

        if frames:
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(pa.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b"".join(frames))
            print("[DEBUG] Finished writing →", path)
    except Exception:
        logging.exception("Failed to record audio")


def play_wav(path: str):
    wf = wave.open(path, 'rb')
    pa = pyaudio.PyAudio()
    stream = pa.open(format=pa.get_format_from_width(wf.getsampwidth()),
                     channels=wf.getnchannels(),
                     rate=wf.getframerate(),
                     output=True)
    data = wf.readframes(1024)
    while data:
        stream.write(data)
        data = wf.readframes(1024)
    stream.stop_stream()
    stream.close()
    pa.terminate()


# ─── threading pool ───────────────────────────────────────────
EXECUTOR = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)

# ─── logging setup ────────────────────────────────────────────
log_dir = Path.home() / "aiweather"
log_dir.mkdir(exist_ok=True)

fmt = logging.Formatter("[%(asctime)s] %(message)s")

# --- NLU logger -------------------------------------------------------------
logger = logging.getLogger("nlu")
logger.setLevel(logging.INFO)

sh = logging.StreamHandler()          # to terminal
sh.setFormatter(fmt)
logger.addHandler(sh)

fh = RotatingFileHandler(log_dir / "nlu.log",
                         maxBytes=300_000, backupCount=5,
                         encoding="utf-8")          # to file
fh.setFormatter(fmt)
logger.addHandler(fh)

# --- Chatbot logger (new) ----------------------------------------------------
chatlog = logging.getLogger("chatbot")
chatlog.setLevel(logging.INFO)

chat_sh = logging.StreamHandler()      # to terminal
chat_sh.setFormatter(fmt)
chatlog.addHandler(chat_sh)

chat_fh = RotatingFileHandler(log_dir / "chatbot.log",
                              maxBytes=300_000, backupCount=5,
                              encoding="utf-8")     # to file
chat_fh.setFormatter(fmt)
chatlog.addHandler(chat_fh)

# ---------------------------------------------------------------------------
csv_path = log_dir / "nlu_log.csv"
if not csv_path.exists():
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp", "raw_text", "intent", "slots_json"])

def _append_csv(ts, raw, intent, slots):
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([ts, raw, intent,
                                json.dumps(slots, ensure_ascii=False)])

# ─── yt_dlp logger ────────────────────────────────────────────
ydl_logger = logging.getLogger("yt_dlp")
ydl_handler = logging.StreamHandler()
ydl_formatter = logging.Formatter("[yt_dlp] %(message)s")
ydl_handler.setFormatter(ydl_formatter)
ydl_logger.addHandler(ydl_handler)
ydl_logger.setLevel(logging.WARNING)


# ─── font registration ─────────────────────────────────────────
def _register_emoji_font() -> None:
    fonts_dir = Path(__file__).with_name("fonts")
    noto_sym = fonts_dir / "NotoSansSymbols2-Regular.ttf"
    if noto_sym.exists():
        LabelBase.register(name="Emoji", fn_regular=str(noto_sym))
    fa_solid = fonts_dir / "fa-solid-900.ttf"
    if fa_solid.exists():
        LabelBase.register(name="FA", fn_regular=str(fa_solid))

def _install_global_unicode_font() -> None:
    search = [
        "NotoSansCJK-Regular.ttc", "NotoSansKR-Regular.otf",
        "NanumGothic.ttf", "NanumGothic.otf", "NotoSansSC-Regular.otf",
        "NotoSans-Regular.ttf", "DejaVuSans.ttf", "msyh.ttc",
        r"C:\Windows\Fonts\malgun.ttf",  r"C:\Windows\Fonts\nanum.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in search:
        if Path(p).exists():
            resource_add_path(str(Path(p).parent))
            LabelBase.register(name="Roboto", fn_regular=str(Path(p)))
            LabelBase.register(name="UI",     fn_regular=str(Path(p)))
            return

_register_emoji_font()
_install_global_unicode_font()

class ReminderManager:
    """Weekly reminder grid that survives reboots."""
    SAVE_PATH = Path.home() / ".aiweather_reminders.json"

    def __init__(self):
        monday_reset = datetime.today().weekday() == 0
        saved = None if monday_reset else self._load()
        self.reminder_list = saved or self._blank()

        # If we wiped the week, save the fresh blank grid immediately
        if monday_reset:
            self._save()

    # ── public API ─────────────────────────────────────────────────────
    def add_one_time(self, day, period, text):
        slot = self.reminder_list[day][period]
        if text in slot:                       # no duplicates
            return
        for i in range(MAX_REMINDERS_PER_SLOT):
            if slot[i] is None:
                slot[i] = text
                self._save()
                break

    def add_everyday(self, period, text):
        for day in self.reminder_list:
            self.add_one_time(day, period, text)

    def delete(self, day, period, text):
        slot = self.reminder_list[day][period]
        try:
            idx = slot.index(text)
            slot[idx] = None
            slot[:] = [r for r in slot if r] + [None] * (MAX_REMINDERS_PER_SLOT - len([r for r in slot if r]))
            self._save()
        except ValueError:
            pass

    def get_all(self):
        return self.reminder_list

    # ── internal helpers ───────────────────────────────────────────────
    def _blank(self):
        return {
            d: {p: [None] * MAX_REMINDERS_PER_SLOT
                for p in ("Morning", "Afternoon", "Evening")}
            for d in ("Monday", "Tuesday", "Wednesday",
                      "Thursday", "Friday", "Saturday", "Sunday")
        }

    def _load(self):
        if self.SAVE_PATH.exists():
            try:
                with self.SAVE_PATH.open(encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                logging.exception("Failed to load reminders; starting fresh")
        return None

    def _save(self):
        try:
            with self.SAVE_PATH.open("w", encoding="utf-8") as fh:
                json.dump(self.reminder_list, fh, ensure_ascii=False, indent=2)
        except Exception:
            logging.exception("Failed to save reminders")


class GuardianNewsAPI:
    BASE_URL = "https://content.guardianapis.com/search"
    def __init__(self, key=None):
        self.key = key or os.getenv("GUARDIAN_KEY")
        if not self.key:
            raise ValueError("GUARDIAN_KEY missing")

    @staticmethod
    def _clean(raw):
        return html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()

    def fetch_news(self, *, amount=10, keyword=None):
        p = {
            "api-key": self.key,
            "show-fields": "trailText",
            "order-by": "newest",
            "page-size": min(max(amount, 1), 200)
        }
        if keyword:
            p["q"] = keyword
        r = requests.get(self.BASE_URL, params=p, timeout=10)
        r.raise_for_status()
        news = []
        for it in r.json()["response"]["results"]:
            raw_html = it.get("fields", {}).get("trailText", "")
            preview_full = self._clean(raw_html)
            # Truncate to 400 characters as before
            if len(preview_full) > 400:
                preview_full = preview_full[:400].rstrip() + "…"
            news.append({
                "title": it["webTitle"],
                "url": it["webUrl"],
                "preview": preview_full,
                "date": datetime.fromisoformat(
                    it["webPublicationDate"].replace("Z", "+00:00")
                ).strftime("%Y-%m-%d")
            })
        return news

class MainUI(BoxLayout):
    def show_error(self, msg):
        # On error, clear title/footer and place msg into preview (in red)
        self.ids.news_title.text = ""
        self.ids.news_preview.text = f"[color=ff3333]{msg}[/color]"
        self.ids.news_footer.text = ""

class AIWeatherApp(App):
    tmp_rec = Path(__file__).with_name("speech_tmp.wav")
    _stop_rec_evt: Event

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_speaking = False
        self._speak_stream = None
        
    def build(self):
        self.reminder_manager = ReminderManager()
        self.news_api      = GuardianNewsAPI()
        self.current_city  = "London"
        self._news_keyword = None
        self._news_buffer  = deque()
        self._recent_urls  = deque(maxlen=50)
        self._init_player()
        return MainUI()

    def on_start(self):
        self.get_weather()
        self.refresh_news()
        self.update_today_reminder_summary()
        Clock.schedule_interval(self.get_weather, WEATHER_REFRESH_SEC)
        Clock.schedule_interval(self.refresh_news, NEWS_REFRESH_SEC)

    def on_stop(self):
        EXECUTOR.shutdown(wait=False)

    # ─── Weather ───────────────────────────────────────────────────────────────
    def get_weather(self, city=None, *_):
        if not isinstance(city, str):
            city = None
        city = city or self.current_city or "London"
        def task():
            key = os.getenv("OPENWEATHER_KEY")
            if not key:
                Clock.schedule_once(lambda *_:
                    self._upd_weather("✖", "OPENWEATHER_KEY missing")
                )
                return
            try:
                r = requests.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params=dict(q=city, appid=key, units="metric", lang="en"),
                    timeout=8
                )
                r.raise_for_status()
                d = r.json()
                desc  = d["weather"][0]["main"]
                temp  = d["main"]["temp"]
                emoji = {
                    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Snow": "❄️",
                    "Thunderstorm": "⚡", "Drizzle": "🌦️",
                    "Mist": "🌫️", "Haze": "🌫️", "Fog": "🌁"
                }.get(desc, "🌈")
                Clock.schedule_once(lambda *_:
                    self._upd_weather(emoji, f"{city}: {desc}, {temp:.1f} °C")
                )
            except Exception:
                Clock.schedule_once(lambda *_:
                    self._upd_weather("✖", "API error")
                )
        EXECUTOR.submit(task)

    def _upd_weather(self, icon, line):
        self.root.ids.weather_icon.text = icon
        self.root.ids.weather_label.text = line

    # ─── News ──────────────────────────────────────────────────────────────────
    def refresh_news(self, *_):
        if self._news_buffer:
            art = self._news_buffer.popleft()
            self._recent_urls.append(art["url"])
            Clock.schedule_once(lambda *_: self._show_headline(art))
        else:
            EXECUTOR.submit(self._fill_buffer)

    def _fill_buffer(self):
        try:
            items = self.news_api.fetch_news(amount=50, keyword=self._news_keyword)
            fresh = [a for a in items if a["url"] not in self._recent_urls]
            if not fresh:
                self._recent_urls.clear()
                fresh = items
            self._news_buffer.extend(fresh)
        except (RequestException, ValueError) as e:
            Clock.schedule_once(lambda *_:
                self.root.show_error(f"Guardian API error: {e}")
            )
            return
        if self._news_buffer:
            art = self._news_buffer.popleft()
            self._recent_urls.append(art["url"])
            Clock.schedule_once(lambda *_: self._show_headline(art))

    def _show_headline(self, art):
        """
        Split the “preview” text into sentences and take at most the first 5.
        Then assign raw strings to news_title, news_preview, news_footer.
        All font sizes and bolding live in KV, not here.
        """
        def first_n_sentences(text, n=5):
            # A very simple sentence‐splitter by punctuation.
            parts = re.split(r'(?<=[.!?])\s+', text)
            if len(parts) <= n:
                return text
            return " ".join(parts[:n]).rstrip(" .!?,;:") + "…"

        lbl_title   = self.root.ids.news_title
        lbl_preview = self.root.ids.news_preview
        lbl_footer  = self.root.ids.news_footer

        lbl_title.opacity   = 0
        lbl_preview.opacity = 0
        lbl_footer.opacity  = 0

        # Title is raw
        lbl_title.text = art["title"]

        # Preview: only first 5 sentences
        preview_text = first_n_sentences(art["preview"], n=5)
        lbl_preview.text = preview_text

        # Footer as before
        lbl_footer.text = f"via The Guardian · {art['date']}"

        Animation(opacity=1, d=0.25).start(lbl_title)
        Animation(opacity=1, d=0.25).start(lbl_preview)
        Animation(opacity=1, d=0.25).start(lbl_footer)

    def open_article(self, instance, url):
        webbrowser.open(url)

 # ── Chatbot ───────────────────────────────────────────

    def ask_chatbot(self):
        query = self.root.ids.request_input.text.strip()
        if not query:
            return

        self.root.ids.chatbot_output.text = "Thinking..."
        EXECUTOR.submit(lambda: get_response(query))\
                .add_done_callback(lambda fut: Clock.schedule_once(
                    lambda *_: setattr(self.root.ids.chatbot_output, "text", fut.result())))

    def ask_ai_and_speak(self):
        if self._is_speaking:
            if self._speak_stream:
                self._is_speaking = False
            return

        user_input = self.root.ids.request_input.text.strip()
        if not user_input:
            return
        chatlog.info("Prompt : %s", user_input)
        prompt = f"Reply in one paragraph. {user_input}"
        self.root.ids.chatbot_output.text = "Thinking..."

        def task():
            reply = get_response(prompt)
            self._speak_chatbot_response(reply)

        EXECUTOR.submit(task)
        
        self.root.ids.request_input.text = ""
        
    def _show_chatbot_popup(self, reply_text):
        label = Label(
            text=reply_text,
            font_name="UI",
            font_size="18sp",
            halign="left",
            valign="top",
            text_size=(dp(400), None),
            size_hint_y=None
        )
        popup = Popup(
            title="AI Response",
            content=label,
            size_hint=(0.9, 0.6),
            auto_dismiss=True
        )

        # Store reference to popup so we can close or track it
        self._chatbot_popup = popup

        # Bind close action to stop speaking
        popup.bind(on_dismiss=lambda *_: self._stop_chatbot_speech())

        popup.open()
        
    def _stop_chatbot_speech(self):
        self._is_speaking = False
        if self._speak_stream:
            try:
                self._speak_stream.stop_stream()
                self._speak_stream.close()
            except Exception:
                pass
            self._speak_stream = None
        self.root.ids.chatbot_output.font_name = "UI"
        self.root.ids.chatbot_output.text = "Ask AI"

    def _speak_chatbot_response(self, reply):
        chatlog.info("Reply  : %s", reply)
        # Show popup immediately
        Clock.schedule_once(lambda *_: self._show_chatbot_popup(reply))  
        
        out = Path(tempfile.gettempdir()) / f"chatbot_{uuid.uuid4().hex}.wav"
        
        try:
            text_to_speech_ibm(reply, str(out))
        except Exception as e:
            logger.exception("TTS failed")
            Clock.schedule_once(lambda *_: setattr(self.root.ids.chatbot_output, "text", "TTS error"))
            return

        def update_ui(*_):

            if self._is_speaking and self._speak_stream is not None:
                self._speak_stream.stop_stream()
                self._speak_stream.close()
                self._speak_stream = None
                self._is_speaking = False
                return

            wf = wave.open(str(out), 'rb')
            pa = pyaudio.PyAudio()
            self._speak_stream = pa.open(format=pa.get_format_from_width(wf.getsampwidth()),
                                        channels=wf.getnchannels(),
                                        rate=wf.getframerate(),
                                        output=True)

            self._is_speaking = True
            self.root.ids.chatbot_output.font_name = "FA"
            self.root.ids.chatbot_output.text = u"\uf04c"  # pause icon

            def play():
                data = wf.readframes(1024)
                while data and self._is_speaking:
                    self._speak_stream.write(data)
                    data = wf.readframes(1024)
                self._speak_stream.stop_stream()
                self._speak_stream.close()
                self._speak_stream = None
                pa.terminate()
                self._is_speaking = False
                self.root.ids.chatbot_output.font_name = "UI"
                self.root.ids.chatbot_output.text = "Ask AI"
                
                if getattr(self, "_chatbot_popup", None):
                    Clock.schedule_once(lambda *_: self._chatbot_popup.dismiss())
                    self._chatbot_popup = None


            threading.Thread(target=play, daemon=True).start()

        Clock.schedule_once(update_ui)



 # ── Speech capture ───────────────────────────────────────────
    def start_record(self):
        if self.tmp_rec.exists():
            try:
                self.tmp_rec.unlink()
            except Exception:
                logging.exception("Could not delete previous temp WAV")

        if getattr(self, "_rec_thr", None) and self._rec_thr.is_alive():
            return                           # debounce if still recording
        self._stop_rec_evt = Event()         # ← create a fresh stop flag

        self.root.ids.btn_request.text = u"\U0001F399"
        self.root.ids.btn_request.font_name = "Emoji"
        logger.info("[MIC] Recording started…")
        self._listen_evt = Clock.schedule_once(self._show_listen_icon, 2)
        self._rec_thr = threading.Thread(
            target=record_to_wav,
            args=(str(self.tmp_rec), self._stop_rec_evt),
            daemon=True)
        self._rec_thr.start()


    def stop_record(self):
        if not getattr(self, "_stop_rec_evt", None):
            return                           # safety
        self._stop_rec_evt.set()             # ← tell thread to finish
        self._rec_thr.join(timeout=2)        # wait up to 2 s for flush
        if getattr(self, "_listen_evt", None):
            self._listen_evt.cancel()
            self._listen_evt = None
        if not self.tmp_rec.exists():
            logger.warning("Recording file not found: %s", self.tmp_rec)
            self._reset_mic_icon()
            return
        self._reset_mic_icon()
        logger.info("[STT] Submitting audio file: %s", self.tmp_rec)
        EXECUTOR.submit(transcribe_audio_ibm, str(self.tmp_rec))\
                .add_done_callback(self._after_stt)

    def _reset_mic_icon(self):
        self.root.ids.btn_request.text = u"\u23F3"
        self.root.ids.btn_request.font_name = "Emoji"

    def _show_listen_icon(self, *_):
        self.root.ids.btn_request.text = u"\u25C9"
        self.root.ids.btn_request.font_name = "Emoji"

    def _after_stt(self, fut):
        try:
            spoken = fut.result().strip()
            logger.info(f"[STT] Transcript: {spoken!r}")
        except Exception as e:
            logger.exception("STT failed")
            spoken = ""

        def _ui(_):
            self.root.ids.btn_request.text = u"\U0001F399"
            self.root.ids.btn_request.font_name = "Emoji"
            if spoken:
                self.root.ids.request_input.text = spoken
                #self.process_request()

        Clock.schedule_once(_ui)


    # ── Read-news TTS ────────────────────────────────────────────
    def read_news_aloud(self):
        title   = self.root.ids.news_title.text
        preview = self.root.ids.news_preview.text
        spoken  = f"{title}. {preview}".strip("— ").strip()
        if not spoken:
            return
        out = Path(tempfile.gettempdir()) / f"news_{uuid.uuid4().hex}.wav"
        def _do_tts():
            text_to_speech_ibm(spoken, str(out))
            return out
        EXECUTOR.submit(_do_tts)\
                .add_done_callback(lambda fut: play_wav(str(fut.result())))
        
    # ─── NLU routing ────────────────────────────────────────────────────────────
    def process_request(self, *_):
        t = self.root.ids.request_input.text.strip()
        if not t:
            return
        EXECUTOR.submit(nlu_infer, t)\
                .add_done_callback(partial(self._route_from_nlu, raw=t))

    def _route_from_nlu(self, fut, raw):
        ts = datetime.utcnow().isoformat(timespec="seconds")
        try:
            intents, slots = fut.result()
            if isinstance(intents, str):
                intents = [intents]
        except Exception:
            Clock.schedule_once(lambda *_: self.root.show_error("NLU error"))
            return

        buckets = defaultdict(list)
        for w, t in slots:
            if t and t != "O":
                buckets[t.split("-")[-1].lower()].append(w)
        slot_json = {k: " ".join(v) for k, v in buckets.items()}
        logger.info('INTENTS=%s  SLOTS=%s  RAW="%s"',  ",".join(intents), slot_json, raw)
        _append_csv(ts, raw, ",".join(intents), slot_json)
        Clock.schedule_once(lambda *_: self._apply_nlu_result(intents, buckets))


    def _apply_nlu_result(self, intents, buckets):
        """
        Handle every intent returned by the NLU engine.

        Supported skills
        ----------------
        get_weather      — uses 'location'
        get_news         — uses 'topic' (fallback: all slot words)
        play_music       — uses 'artist' and/or 'song' (no other fallback)
        reminder_add     — uses 'behavior' + 'time'
        reminder_cancel  — uses 'behavior' + 'time'
        reminder_clear   — clears all reminders for the week
        """

        # ---------- normalise & deduplicate ---------------------------------
        if isinstance(intents, str):
            intents = [intents]
        intents = list(dict.fromkeys(intents))             # preserve order

        # ---------- generic slot helpers ------------------------------------
        loc     = " ".join(buckets.get("location", [])).title()
        topic   = " ".join(buckets.get("topic", []))
        words   = " ".join(sum(buckets.values(), []))

        artist  = " ".join(buckets.get("artist", []))
        song    = " ".join(buckets.get("song", []))

        behavior = " ".join(buckets.get("behavior", []))
        time_str = " ".join(buckets.get("time", []))

        # ---------- time parsing helper -------------------------------------
        def _parse_day_period(s: str):
            """
            Convert a free-text time phrase into (weekday, period).

            * weekday:  'Monday' … 'Sunday'
            * period:   'Morning' | 'Afternoon' | 'Evening'

            Falls back to today's weekday and 'Morning' if missing.
            Handles 'today', 'tomorrow' automatically.
            """
            weekdays = ["Monday", "Tuesday", "Wednesday",
                        "Thursday", "Friday", "Saturday", "Sunday"]
            s_low = s.lower()

            # weekday
            if "today" in s_low:
                day_idx = datetime.today().weekday()
            elif "tomorrow" in s_low:
                day_idx = (datetime.today().weekday() + 1) % 7
            else:
                day_idx = next((i for i, d in enumerate(weekdays)
                                if d.lower() in s_low), None)
                if day_idx is None:
                    day_idx = datetime.today().weekday()
            weekday = weekdays[day_idx]

            # period
            if "afternoon" in s_low:
                period = "Afternoon"
            elif "evening" in s_low or "night" in s_low:
                period = "Evening"
            else:                                    # default / morning
                period = "Morning"

            return weekday, period

        handled = False

        # ---------- dispatch loop -------------------------------------------
        for intent in intents:

            # ── Weather ────────────────────────────────────────────────────
            if intent == "get_weather":
                if loc:
                    self.current_city = loc
                self.get_weather()
                handled = True

            # ── News ───────────────────────────────────────────────────────
            elif intent == "get_news":
                self._news_keyword = topic or words or None
                self._news_buffer.clear()
                self.refresh_news()
                handled = True

            # ── Music ──────────────────────────────────────────────────────
            elif intent == "play_music":
                if artist or song:
                    query = f"{artist} {song}".strip()
                    self.get_music(query)
                    handled = True

            # ── Reminders: add / cancel / clear-day ───────────────────────────
            elif intent in ("reminder_add", "reminder_cancel"):
                rm = self.reminder_manager
                weekday, period = _parse_day_period(time_str)

                # ---------- ADD -------------------------------------------------
                if intent == "reminder_add":
                    if not behavior:                 # nothing to add
                        continue
                    rm.add_one_time(weekday, period, behavior)

                # ---------- CANCEL ----------------------------------------------
                else:  # intent == "reminder_cancel"
                    if behavior:                     # cancel just that task
                        rm.delete(weekday, period, behavior)
                    else:
                        # no behaviour ⇒ wipe the chosen day / period(s)
                        t_low = time_str.lower()
                        keywords = ("morning", "afternoon", "evening", "night")

                        def _blank_slot():
                            return [None] * MAX_REMINDERS_PER_SLOT

                        if any(k in t_low for k in keywords):
                            # e.g. "tomorrow evening" → clear only that bucket
                            rm.reminder_list[weekday][period] = _blank_slot()
                        else:
                            # e.g. "tomorrow" → clear the whole day
                            rm.reminder_list[weekday] = {
                                p: _blank_slot() for p in ("Morning", "Afternoon", "Evening")
                            }
                        rm._save()

                self.update_today_reminder_summary()
                handled = True


            # ── Reminders: clear the entire week ──────────────────────────
            elif intent == "reminder_clear":
                rm = self.reminder_manager
                rm.reminder_list = rm._blank()
                rm._save()
                self.update_today_reminder_summary()
                handled = True
        # ---------- UX feedback --------------------------------------------
        if not handled:
            self.root.ids.request_input.hint_text = (
                "Try “weather in Berlin”, “news about rugby”, "
                "“play song Yellow by Coldplay”, or "
                "“I have a meeting on Monday morning”."
            )
            return

        # clear the input after success
        self.root.ids.request_input.text = ""
        self.root.ids.request_input.focus = False


    # ─── YouTube music ─────────────────────────────────────────────────────────
    def _init_player(self):
        if vlc is None:
            self._vlc = self.player = None
            return
        self._vlc   = vlc.Instance("--no-xlib", "--quiet", "--novideo")
        self.player = self._vlc.media_player_new()

    def get_music(self, query=None, *_):
        if not query:
            self._music_error("No music keywords found")
            return
        ids = self.root.ids
        ids.music_icon.text  = "🔍"
        ids.music_label.text = f"Searching “{query}”…"
        EXECUTOR.submit(self._yt_search, query).add_done_callback(self._after_search)

    @staticmethod
    def _yt_search(query, max_results=5):
        opts = {
            "quiet": True,
            "extract_flat": "in_playlist",
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "default_search": f"ytsearch{max_results}",
            "noplaylist": True,
            "logger": ydl_logger,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            entries = (ydl.extract_info(query, download=False)
                       .get("entries", []) or [])
        out = []
        for e in entries:
            url = e.get("url") or e.get("webpage_url")
            if url:
                out.append({
                    "url": url,
                    "title": e.get("title", "No title"),
                    "uploader": e.get("uploader") or "YouTube"
                })
        return out

    @staticmethod
    def _yt_fetch_url(video_url):
        opts = {
            "quiet": True,
            "skip_download": True,
            "forceurl": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "logger": ydl_logger,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(video_url, download=False)["url"]

    def _music_error(self, msg):
        Clock.schedule_once(lambda *_: (
            setattr(self.root.ids.music_icon, "text", "✖"),
            setattr(self.root.ids.music_label, "text", msg)
        ))

    def _after_search(self, fut):
        try:
            results = fut.result()
        except Exception as e:
            self._music_error(str(e))
            return
        if not results:
            self._music_error("No results")
            return
        Clock.schedule_once(lambda *_: self._show_results(results))

    def _show_results(self, results):
        ROW_H = dp(40)
        inner = GridLayout(
            cols=1, spacing=dp(5),
            padding=[dp(8), dp(8), dp(8), dp(8)],
            size_hint_y=None
        )
        inner.bind(minimum_height=inner.setter("height"))

        # ↓ Make each track‐button slightly smaller (18sp)
        for r in results:
            btn = Button(
                text=r["title"],
                size_hint_y=None,
                height=ROW_H,
                font_size="18sp",   # was "20sp"
                halign="center",
                valign="middle"
            )
            btn.bind(
                size=lambda b, *_: setattr(b, "text_size", (b.width - dp(20), None))
            )
            btn.bind(on_release=lambda b, res=r: (
                popup.dismiss(),
                EXECUTOR.submit(self._prepare_and_play, res)
            ))
            inner.add_widget(btn)

        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(inner)
        popup = Popup(
            title="Select a track",
            content=scroll,
            size_hint=(0.8, None),
            height=dp(300),
            auto_dismiss=True
        )
        popup.open()

    def _prepare_and_play(self, res):
        try:
            stream = self._yt_fetch_url(res["url"])
            Clock.schedule_once(lambda *_: self._play(stream, res["title"]))
        except Exception as e:
            self._music_error(str(e))

    def _play(self, stream_url, title):
        if self.player is None:
            self._music_error("python-vlc not installed")
            return
        media = self._vlc.media_new(stream_url)
        self.player.set_media(media)
        self.player.play()
        ids = self.root.ids
        ids.music_icon.text  = "🎵"
        ids.music_label.text = title
        ids.btn_play.text    = "⏸️"

    def music_play_pause(self, *_):
        if not self.player:
            return
        if self.player.is_playing():
            self.player.pause()
            self.root.ids.btn_play.text = "▶️"
        else:
            self.player.play()
            self.root.ids.btn_play.text = "⏸️"

    def music_stop(self, *_):
        if self.player:
            self.player.stop()
        ids = self.root.ids
        ids.music_icon.text  = "🎵"
        ids.music_label.text = "Stopped"
        ids.btn_play.text    = "▶️"

    def _seek(self, sec):
        if not self.player:
            return
        pos = self.player.get_time() / 1000
        self.player.set_time(int(max(pos + sec, 0) * 1000))

    def music_back(self, *_):
        self._seek(-10)

    def music_forward(self, *_):
        self._seek(+10)

    def open_reminder_popup(self):
        days    = ["Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday", "Saturday", "Sunday"]
        periods = ["Morning", "Afternoon", "Evening"]

        popup  = Popup(title="Weekly Reminders", size_hint=(0.95, 0.95))
        scroll = ScrollView(do_scroll_x=False)

        # Column count: one for period labels + 7 weekdays
        grid = GridLayout(
            cols=len(days) + 1,
            padding=dp(16),
            spacing=dp(10),
            size_hint_y=None
        )
        grid.bind(minimum_height=grid.setter("height"))

        def _label(text, *, bold=False, height=dp(40)):
            lbl = Label(
                text=f"[b]{text}[/b]" if bold else text,
                markup=True,
                font_name="UI",
                font_size="18sp",
                halign="center" if bold else "left",
                valign="middle" if bold else "top",
                size_hint_y=None,
                height=height,
                text_size=(None, None)   # let Kivy compute wrapping
            )
            return lbl

        # ── Header row ───────────────────────────────────────────────────────
        grid.add_widget(_label(""))  # empty top-left corner
        for d in days:
            grid.add_widget(_label(d, bold=True))

        # ── Body rows ────────────────────────────────────────────────────────
        data = self.reminder_manager.get_all()
        CELL_H = dp(120)   # more vertical space for wrapped reminders

        for p in periods:
            grid.add_widget(_label(p, bold=True, height=CELL_H))

            for d in days:
                reminders = [r for r in data[d][p] if r]
                text = "• " + "\n• ".join(reminders) if reminders else "—"
                grid.add_widget(_label(text, height=CELL_H))

        # ── Finish ───────────────────────────────────────────────────────────
        scroll.add_widget(grid)
        popup.content = scroll
        popup.open()

        # ─── Add / edit reminder dialog ─────────────────────────────────────────
    from kivy.uix.boxlayout import BoxLayout   # already imported, listed for clarity

    # ─── Add / edit reminder dialog ─────────────────────────────────────────
    def open_add_reminder_popup(self):
        rm       = self.reminder_manager
        days     = ["Monday", "Tuesday", "Wednesday",
                    "Thursday", "Friday", "Saturday", "Sunday"]
        periods  = ["Morning", "Afternoon", "Evening"]

        popup = Popup(title="Edit Reminder", size_hint=(0.8, 0.7))

        # outer container: vertical box → [ScrollView | Save-button]
        root_box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))

        # ── form inside a ScrollView -----------------------------------------
        form_grid = GridLayout(
            cols=2, spacing=dp(10), padding=dp(20),
            row_default_height=dp(50), size_hint_y=None
        )
        form_grid.bind(minimum_height=form_grid.setter("height"))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(form_grid)

        # day selector
        form_grid.add_widget(Label(text="Day:", font_name="UI", font_size="18sp"))
        day_spinner = Spinner(text=datetime.now().strftime("%A"),
                            values=days, font_size="18sp")
        form_grid.add_widget(day_spinner)

        # period selector
        form_grid.add_widget(Label(text="Time:", font_name="UI", font_size="18sp"))
        time_spinner = Spinner(text="Morning", values=periods, font_size="18sp")
        form_grid.add_widget(time_spinner)

        # text input
        form_grid.add_widget(Label(text="Reminders:", font_name="UI",
                                font_size="18sp"))
        txt = TextInput(multiline=True, font_name="UI", font_size="18sp",
                        size_hint_y=None, height=dp(140))
        form_grid.add_widget(txt)

        # preload text box with current slot ---------------------------------
        def _sync_text(*_):
            slot = rm.get_all()[day_spinner.text][time_spinner.text]
            txt.text = "\n".join(r for r in slot if r)
        day_spinner.bind(text=_sync_text)
        time_spinner.bind(text=_sync_text)
        _sync_text()

        # save handler -------------------------------------------------------
        def _save(*_):
            items = [s.strip() for line in txt.text.splitlines()
                                for s in line.split(",") if s.strip()]
            slot  = items[:MAX_REMINDERS_PER_SLOT] \
                + [None] * (MAX_REMINDERS_PER_SLOT - len(items[:MAX_REMINDERS_PER_SLOT]))
            rm.reminder_list[day_spinner.text][time_spinner.text] = slot
            rm._save()
            self.update_today_reminder_summary()
            popup.dismiss()

        # fixed footer button (always visible) -------------------------------
        btn_box = BoxLayout(size_hint_y=None, height=dp(50))
        btn_box.add_widget(Button(text="Save", font_size="18sp", on_release=_save))

        # assemble popup -----------------------------------------------------
        root_box.add_widget(scroll)
        root_box.add_widget(btn_box)
        popup.content = root_box
        popup.open()


    def update_today_reminder_summary(self):
        today = datetime.now().strftime("%A")
        reminders = self.reminder_manager.get_all().get(today, {})
        summary_lines = []
        for time in ["Morning", "Afternoon", "Evening"]:
            entries = [r for r in reminders.get(time, []) if r]
            if entries:
                summary_lines.append(f"{time}: {', '.join(entries)}")
        summary = "\n".join(summary_lines) if summary_lines else "No reminders today"
        self.root.ids.reminder_summary.text = summary

if __name__ == "__main__":
    AIWeatherApp().run()
