from kivy.config import Config
Config.set('graphics', 'width', '800')
Config.set('graphics', 'height', '480')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
import requests

# This class name must match <MainUI> in your .kv file
class MainUI(BoxLayout):
    pass

# App name = AIWeatherApp → Kivy looks for aiweather.kv
class AIWeatherApp(App):
    def build(self):
        return MainUI()

    def get_weather(self):
        # Simulated weather output
        weather = "☀️ Sunny, 22°C"
        self.root.ids.weather_label.text = f"Weather: {weather}"

    def get_music(self):
        self.root.ids.music_label.text = "🎵 Now Playing: Jazz FM"

    def ask_chatbot(self):
        response = "🤖 AI: You should take an umbrella today!"
        self.root.ids.chatbot_output.text = response

if __name__ == "__main__":
    AIWeatherApp().run()
