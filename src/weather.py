import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('OPENWEATHER_API_KEY')
CITY = 'London'
URL = f'http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric&lang=en'

def get_weather():
    try:
        response = requests.get(URL)
        data = response.json()

        if response.status_code != 200:
            print(f"failed to get weather data: {data['message']}")
            return

        weather = data['weather'][0]['description']
        temp = data['main']['temp']
        humidity = data['main']['humidity']
        wind_speed = data['wind']['speed']

        print(f"🌤 City: {CITY}")
        print(f"🌡 Weather: {temp}°C")
        print(f"🌫 Temperature: {weather}")
        print(f"💧 Humidity: {humidity}%")
        print(f"💨 Wind Speed: {wind_speed} m/s")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    get_weather()
