# AIWeather – UI (weather • Guardian news • BERT NLU • YouTube music)

"""
AIWeather – UI (weather • Guardian news • BERT NLU • YouTube music)

"""
# ───────── standard lib ─────────
import os, platform, webbrowser, textwrap, csv, json, html, re, logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# ───────── third-party ──────────
import requests
from requests.exceptions import RequestException
from dotenv import load_dotenv
import yt_dlp

try:
    import vlc
except ModuleNotFoundError:
    vlc = None

# ───────── Kivy setup ───────────
from kivy.config import Config
Config.set("graphics", "width",  "800")
Config.set("graphics", "height", "480")

from kivy.resources import resource_add_path
from kivy.core.text import LabelBase
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# your Joint-BERT wrapper
from BERT import infer as nlu_infer

# ───────── env & thread pool ────
load_dotenv(Path(__file__).with_name(".env"))
EXECUTOR = ThreadPoolExecutor(max_workers=4)

# ───────── logging & CSV ────────
log_dir = Path.home() / "aiweather"; log_dir.mkdir(exist_ok=True)
logger = logging.getLogger("nlu"); logger.setLevel(logging.INFO)
fmt = logging.Formatter("[%(asctime)s] %(message)s")
sh = logging.StreamHandler(); sh.setFormatter(fmt); logger.addHandler(sh)
fh = RotatingFileHandler(log_dir / "nlu.log", maxBytes=300_000,
                         backupCount=5, encoding="utf-8")
fh.setFormatter(fmt); logger.addHandler(fh)

csv_path = log_dir / "nlu_log.csv"
if not csv_path.exists():
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp", "raw_text", "intent", "slots_json"])

# ───────── yt_dlp logger ────────
ydl_logger = logging.getLogger("yt_dlp")
ydl_handler = logging.StreamHandler()
ydl_formatter = logging.Formatter("[yt_dlp] %(message)s")
ydl_handler.setFormatter(ydl_formatter)
ydl_logger.addHandler(ydl_handler)
ydl_logger.setLevel(logging.WARNING)


def _append_csv(ts, raw, intent, slots):
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([ts, raw, intent,
                                json.dumps(slots, ensure_ascii=False)])

# ───────── register fonts ──────────────────────────────────────────
def _register_emoji_font() -> None:
    """Colour-emoji face used only for icons and buttons."""
    local = next((p for p in ("NotoColorEmoji.ttf", "seguiemj.ttf")
                  if Path(p).exists()), None)
    if not local:
        fallbacks = {
            "Windows": r"C:\Windows\Fonts\seguiemj.ttf",
            "Darwin":  "/System/Library/Fonts/Apple Color Emoji.ttc",
            "Linux":   "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        }
        local = fallbacks.get(platform.system(), "")
    if local and Path(local).exists():
        LabelBase.register(name="Emoji", fn_regular=str(Path(local)))


def _install_global_unicode_font() -> None:
    """Pick the first wide-Unicode sans font we can find and register it."""
    search = [
        # common full CJK or pan-Unicode faces
        "NotoSansCJK-Regular.ttc", "NotoSansKR-Regular.otf",
        "NanumGothic.ttf", "NanumGothic.otf", "NotoSansSC-Regular.otf",
        "NotoSans-Regular.ttf", "DejaVuSans.ttf", "msyh.ttc",
        # Windows
        r"C:\Windows\Fonts\malgun.ttf",  r"C:\Windows\Fonts\nanum.ttf",
        # macOS
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        # Linux distro locations
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in search:
        if Path(p).exists():
            resource_add_path(str(Path(p).parent))
            LabelBase.register(name="Roboto", fn_regular=str(Path(p)))
            LabelBase.register(name="UI",     fn_regular=str(Path(p)))
            print(f"✓ Unicode font installed: {Path(p).name}")
            return
    print("⚠️  No wide-Unicode font found; non-Latin glyphs may show □")

_register_emoji_font()
_install_global_unicode_font()

# ──────────────────── Reminder Manager ───────────────────────────────────────────────
class ReminderManager:
    def __init__(self):
        self.reminder_list = self._create_reminder_list()

    def _create_reminder_list(self):
        reminder_list = {}
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            reminder_list[day] = {
                "Morning": [None, None, None],
                "Afternoon": [None, None, None],
                "Evening": [None, None, None]
            }
        return reminder_list

    def add_one_time(self, day, time, reminder):
        for i in range(3):
            if self.reminder_list[day][time][i] is None:
                self.reminder_list[day][time][i] = reminder
                break

    def add_everyday(self, time, reminder):
        for day in self.reminder_list:
            for i in range(3):
                if self.reminder_list[day][time][i] is None:
                    self.reminder_list[day][time][i] = reminder
                    break

    def delete(self, day, time, reminder):
        try:
            index = self.reminder_list[day][time].index(reminder)
            self.reminder_list[day][time][index] = None
            self.reminder_list[day][time] = [x for x in self.reminder_list[day][time] if x is not None] + [None] * (3 - len(self.reminder_list[day][time]))
        except ValueError:
            pass

    def get_all(self):
        return self.reminder_list

# ───────── Guardian helper ──────
class GuardianNewsAPI:
    BASE_URL = "https://content.guardianapis.com/search"
    def __init__(self, key=None):
        self.key = key or os.getenv("GUARDIAN_KEY")
        if not self.key:
            raise ValueError("GUARDIAN_KEY missing")
    @staticmethod
    def _clean(raw): return html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
    def fetch_news(self, *, amount=10, keyword=None):
        p = {"api-key": self.key, "show-fields": "trailText",
             "order-by": "newest", "page-size": min(max(amount,1),200)}
        if keyword: p["q"] = keyword
        r = requests.get(self.BASE_URL, params=p, timeout=10); r.raise_for_status()
        news=[]
        for it in r.json()["response"]["results"]:
            preview = textwrap.shorten(
                self._clean(it.get("fields", {}).get("trailText",""))
                .replace("\n"," "),
                140, placeholder="…")
            news.append(dict(
                title=it["webTitle"],
                url=it["webUrl"],
                preview=preview,
                date=datetime.fromisoformat(
                       it["webPublicationDate"].replace("Z","+00:00")
                     ).strftime("%Y-%m-%d")
            ))
        return news

# ───────── KV root widget ───────
class MainUI(BoxLayout):
    def show_error(self, msg):
        self.ids.news_label.text = f"[color=ff3333]{msg}[/color]"
    def toggle_request_bar(self):
        bar = self.ids.request_bar
        if bar.height == 0:
            bar.height, bar.opacity = dp(44), 1
            self.ids.request_input.focus = True
        else:
            bar.height, bar.opacity = 0, 0

# ───────── main app class ───────
class AIWeatherApp(App):

    # ---- lifecycle ------------------------------------------------
    def build(self):
        self.reminder_manager = ReminderManager()
        self.news_api      = GuardianNewsAPI()
        self.current_city  = "London"
        self._news_keyword = None
        self._news_buffer  = deque(); self._recent_urls = deque(maxlen=50)
        self._init_player()
        return MainUI()

    def on_start(self):
        self.get_weather(); self.refresh_news()
        self.update_today_reminder_summary()
        Clock.schedule_interval(self.get_weather, 600)
        Clock.schedule_interval(self.refresh_news, 300)

    # ---- weather --------------------------------------------------
    def get_weather(self, city=None, *_):
        city = city or self.current_city or "London"
        def task():
            key=os.getenv("OPENWEATHER_KEY")
            if not key:
                Clock.schedule_once(lambda *_:
                    self._upd_weather("❌","OPENWEATHER_KEY missing")); return
            try:
                r=requests.get("https://api.openweathermap.org/data/2.5/weather",
                               params=dict(q=city,appid=key,units="metric",lang="en"),
                               timeout=8); r.raise_for_status(); d=r.json()
                desc,temp=d["weather"][0]["main"], d["main"]["temp"]
                emoji={"Clear":"☀️","Clouds":"☁️","Rain":"🌧️","Snow":"❄️",
                       "Thunderstorm":"⚡","Drizzle":"🌦️",
                       "Mist":"🌫️","Haze":"🌫️","Fog":"🌁"}.get(desc,"🌈")
                Clock.schedule_once(lambda *_:
                    self._upd_weather(emoji, f"{city}: {desc}, {temp:.1f} °C"))
            except Exception as exc:
                Clock.schedule_once(lambda *_:
                    self._upd_weather("❌","API error")); print(exc)
        EXECUTOR.submit(task)
    def _upd_weather(self, icon, line):
        self.root.ids.weather_icon.text=icon
        self.root.ids.weather_label.text=line

    # ---- news -----------------------------------------------------
    def refresh_news(self,*_):
        if self._news_buffer:
            art=self._news_buffer.popleft(); self._recent_urls.append(art["url"])
            Clock.schedule_once(lambda *_: self._show_headline(art))
        else:
            EXECUTOR.submit(self._fill_buffer)
    def _fill_buffer(self):
        try:
            items=self.news_api.fetch_news(amount=50, keyword=self._news_keyword)
            fresh=[a for a in items if a["url"] not in self._recent_urls]
            if not fresh: self._recent_urls.clear(); fresh=items
            self._news_buffer.extend(fresh)
        except (RequestException,ValueError) as e:
            Clock.schedule_once(lambda *_:
                self.root.show_error(f"Guardian API error: {e}")); return
        if self._news_buffer:
            art=self._news_buffer.popleft(); self._recent_urls.append(art["url"])
            Clock.schedule_once(lambda *_: self._show_headline(art))
    def _show_headline(self, art):
        lbl=self.root.ids.news_label; lbl.opacity=0
        lbl.text=(f"[ref={art['url']}][b]{art['title']}[/b]\n{art['preview']}[/ref]\n"
                  f"[size=24]via The Guardian · {art['date']}[/size]")
        Animation(opacity=1, d=.25).start(lbl)
    def open_article(self, url): webbrowser.open(url)

    # ---- NLU routing ---------------------------------------------
    def process_request(self,*_):
        t=self.root.ids.request_input.text.strip()
        if not t: return
        EXECUTOR.submit(nlu_infer, t)\
                .add_done_callback(partial(self._route_from_nlu, raw=t))
    def _route_from_nlu(self, fut, raw):
        ts=datetime.utcnow().isoformat(timespec="seconds")
        try: intent, slots=fut.result()
        except Exception as e:
            Clock.schedule_once(lambda *_: self.root.show_error("NLU error")); print(e); return
        buckets=defaultdict(list)
        for w,t in slots:
            if t and t!="O": buckets[t.split("-")[-1].lower()].append(w)
        slot_json={k:" ".join(v) for k,v in buckets.items()}
        logger.info('INTENT=%s  SLOTS=%s  RAW="%s"', intent, slot_json, raw)
        _append_csv(ts, raw, intent, slot_json)
        Clock.schedule_once(lambda *_: self._apply_nlu_result(intent, buckets))
    def _apply_nlu_result(self, intent, buckets):
        loc=" ".join(buckets.get("location",[])).title()
        topic=" ".join(buckets.get("topic",[])); words=" ".join(sum(buckets.values(),[]))
        if intent=="get_weather":
            if loc: self.current_city=loc; self.get_weather()
        elif intent=="get_news":
            self._news_keyword=topic or words or None
            self._news_buffer.clear(); self.refresh_news()
        elif intent=="play_music":
            query=(topic or words).strip(); self.get_music(query=query or None)
        else:
            self.root.ids.request_input.hint_text="Try “weather in Berlin” or “news about rugby”."
            return
        self.root.ids.request_input.text=""; self.root.toggle_request_bar()

    # ───────── YouTube music (yt_dlp + python-vlc) ─────────
    def _init_player(self):
        if vlc is None: self._vlc=self.player=None; return
        self._vlc=vlc.Instance("--no-xlib","--quiet","--novideo")
        self.player=self._vlc.media_player_new()

    # -- public entry --
    def get_music(self, query=None, *_):
        if not query: self._music_error("No music keywords found"); return
        ids=self.root.ids; ids.music_icon.text="🔍"; ids.music_label.text=f"Searching “{query}”…"
        EXECUTOR.submit(self._yt_search, query).add_done_callback(self._after_search)

    # -- background helpers --
    @staticmethod
    def _yt_search(query, max_results=5):
        opts={
            "quiet": True,
            "extract_flat": "in_playlist",
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "default_search": f"ytsearch{max_results}",
            "noplaylist": True,
            "logger": ydl_logger,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            entries=(ydl.extract_info(query, download=False).get("entries",[]) or [])
        out=[]
        for e in entries:
            url=e.get("url") or e.get("webpage_url")
            if url: out.append(dict(url=url,title=e.get("title","No title"),
                                    uploader=e.get("uploader") or "YouTube"))
        return out

    @staticmethod
    def _yt_fetch_url(video_url):
        opts={
            "quiet": True,
            "skip_download": True,
            "forceurl": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "logger": ydl_logger,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(video_url, download=False)["url"]

    # -- UI helpers --
    def _music_error(self,msg):
        Clock.schedule_once(lambda *_:(
            setattr(self.root.ids.music_icon,"text","❌"),
            setattr(self.root.ids.music_label,"text",msg)))
    def _after_search(self,fut):
        try: results=fut.result()
        except Exception as e: self._music_error(str(e)); return
        if not results: self._music_error("No results"); return
        Clock.schedule_once(lambda *_: self._show_results(results))
    def _show_results(self, results):
        ROW_H=dp(40)
        inner=GridLayout(cols=1,spacing=dp(5),
                         padding=[dp(8),dp(8),dp(8),dp(8)],
                         size_hint_y=None)
        inner.bind(minimum_height=inner.setter("height"))
        for r in results:
            btn=Button(text=r["title"],size_hint_y=None,height=ROW_H,
                       halign="center",valign="middle")
            btn.bind(size=lambda b,*_: setattr(b,"text_size",(b.width-dp(20),None)))
            btn.bind(on_release=lambda b,res=r: (
                popup.dismiss(),
                EXECUTOR.submit(self._prepare_and_play,res)))
            inner.add_widget(btn)
        scroll=ScrollView(do_scroll_x=False); scroll.add_widget(inner)
        popup=Popup(title="Select a track",content=scroll,
                    size_hint=(0.8,None),height=dp(300),auto_dismiss=True)
        popup.open()
    def _prepare_and_play(self, res):
        try:
            stream=self._yt_fetch_url(res["url"])
            Clock.schedule_once(lambda *_: self._play(stream,res["title"]))
        except Exception as e: self._music_error(str(e))
    def _play(self, stream_url, title):
        if self.player is None: self._music_error("python-vlc not installed"); return
        media=self._vlc.media_new(stream_url); self.player.set_media(media); self.player.play()
        ids=self.root.ids; ids.music_icon.text="🎵"; ids.music_label.text=title; ids.btn_play.text="⏸️"
    # playback controls
    def music_play_pause(self,*_):
        if not self.player: return
        if self.player.is_playing(): self.player.pause(); self.root.ids.btn_play.text="▶️"
        else: self.player.play(); self.root.ids.btn_play.text="⏸️"
    def music_stop(self,*_):
        if self.player: self.player.stop()
        ids=self.root.ids; ids.music_icon.text="🎵"; ids.music_label.text="Stopped"; ids.btn_play.text="▶️"
    def _seek(self, sec):
        if not self.player: return
        pos=self.player.get_time()/1000; self.player.set_time(int(max(pos+sec,0)*1000))
    def music_back(self,*_):   self._seek(-10)
    def music_forward(self,*_):self._seek(+10)

    # ---- chatbot placeholder ----
    def ask_chatbot(self,*_):
        self.root.ids.chatbot_icon.text="🤖"
        self.root.ids.chatbot_output.text="Don’t forget your umbrella!"
    
    def open_reminder_popup(self):
        popup = Popup(title="Weekly Reminders", size_hint=(0.95, 0.95))
        
        # Outer scrollable area
        scroll = ScrollView()
        
        # Table grid: 8 columns (1 for time label + 7 for each day)
        grid = GridLayout(cols=8, spacing=dp(5), padding=dp(10),
                        size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        # Header row
        grid.add_widget(Label(text="", bold=True))  # Empty corner
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            grid.add_widget(Label(text=f"[b]{day}[/b]", markup=True, font_name="UI", size_hint_y=None, height=dp(30)))

        # Fill grid with reminders
        times = ["Morning", "Afternoon", "Evening"]
        data = self.reminder_manager.get_all()
        for time in times:
            grid.add_widget(Label(text=f"[b]{time}[/b]", markup=True, font_name="UI", size_hint_y=None, height=dp(60)))
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
                reminders = data[day][time]
                msg = "\n".join(r for r in reminders if r) or "—"
                grid.add_widget(Label(text=msg, font_name="UI", font_size="13sp",
                                    halign="left", valign="top",
                                    size_hint_y=None, height=dp(60),
                                    text_size=(dp(100), None)))

        scroll.add_widget(grid)
        popup.content = scroll
        popup.open()

    def open_add_reminder_popup(self):
        popup = Popup(title="Add Reminder", size_hint=(0.8, 0.6))
        
        layout = GridLayout(cols=2, spacing=dp(10), padding=dp(20),
                            row_default_height=dp(40), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        # Day selector
        layout.add_widget(Label(text="Day:", font_name="UI"))
        day_spinner = Spinner(
            text="Monday",
            values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        )
        layout.add_widget(day_spinner)

        # Time selector
        layout.add_widget(Label(text="Time:", font_name="UI"))
        time_spinner = Spinner(
            text="Morning",
            values=["Morning", "Afternoon", "Evening"]
        )
        layout.add_widget(time_spinner)

        # Reminder input
        layout.add_widget(Label(text="Reminder:", font_name="UI"))
        reminder_input = TextInput(multiline=False, font_name="UI")
        layout.add_widget(reminder_input)

        # Submit button
        def submit_reminder(*_):
            day = day_spinner.text
            time = time_spinner.text
            text = reminder_input.text.strip()
            if text:
                self.reminder_manager.add_one_time(day, time, text)
                popup.dismiss()
            self.update_today_reminder_summary()


        layout.add_widget(Widget())  # spacer
        layout.add_widget(Button(text="Add", on_release=submit_reminder))

        scroll = ScrollView(); scroll.add_widget(layout)
        popup.content = scroll
        popup.open()
        
    def update_today_reminder_summary(self):
        today = datetime.now().strftime("%A")  # e.g., "Monday"
        reminders = self.reminder_manager.get_all().get(today, {})
        summary_lines = []
        for time in ["Morning", "Afternoon", "Evening"]:
            entries = [r for r in reminders.get(time, []) if r]
            if entries:
                summary_lines.append(f"{time}: {', '.join(entries)}")
        summary = "\n".join(summary_lines) if summary_lines else "No reminders today"
        self.root.ids.reminder_summary.text = summary




# ───────── bootstrap ────────────
if __name__=="__main__":
    AIWeatherApp().run()
