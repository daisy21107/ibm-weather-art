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
        try:
            API_KEY = ''
            CITY = 'London'
            url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric&lang=en"
            
            response = requests.get(url)
            data = response.json()

            if response.status_code != 200:
                print(f"API Error: {data['message']}")
                self.root.ids.weather_icon.text = "❌"
                self.root.ids.weather_label.text = f"Error: {data['message']}"
                return

            description = data['weather'][0]['main']
            temp = data['main']['temp']

            emoji_map = {
                "Clear": "☀️",
                "Clouds": "☁️",
                "Rain": "🌧️",
                "Snow": "❄️",
                "Thunderstorm": "⚡",
                "Drizzle": "🌦️",
                "Mist": "🌫️",
                "Haze": "🌫️",
                "Fog": "🌁"
            }

            emoji = emoji_map.get(description, "🌈")
            self.root.ids.weather_icon.text = emoji
            self.root.ids.weather_label.text = f"{description}, {temp:.1f}°C"

        except Exception as e:
            print(f"Exception occurred: {e}")
            self.root.ids.weather_icon.text = "❌"
            self.root.ids.weather_label.text = "API error"


    def get_music(self):
        self.root.ids.music_icon.text = "🎵"
        self.root.ids.music_label.text = "Now Playing: Jazz FM"

    def ask_chatbot(self):
        self.root.ids.chatbot_icon.text = "🤖"
        self.root.ids.chatbot_output.text = "AI: You should take an umbrella today!"

if __name__ == "__main__":
    AIWeatherApp().run()
