from MBERTtesting import infer
from src.news import GuardianNewsAPI
from src.weather import get_weather
from src.youtube import search_youtube, resolve_stream_url, MusicPlayer, get_single_key

# API KEYS
GUARDIAN_API_KEY = ""  # Replace with your Guardian API key
WEATHER_API_KEY = ""    # Replace with your weather API key

news_api = GuardianNewsAPI(GUARDIAN_API_KEY)

# Main interaction loop
if __name__ == "__main__":
    while True:
        try:
            text = input("\n🗣 Please enter an English request: ").strip()
            if not text:
                continue

            intent, slots = infer(text)
            if intent is None:
                continue

            print(f"\n🎯 Predicted inte"
                  f"nt: {intent}")
            print("📌 Slot tagging:")
            for word, tag in slots:
                print(f"  {word:<12} -> {tag}")

            # Extract all labeled keywords
            labeled_words = [word for word, tag in slots if tag != 'O']
            if labeled_words:
                print(f"\n📌 Labeled keywords: {labeled_words}")
                query = " ".join(labeled_words)
            else:
                query = None

            if intent == "get_news":
                if query:
                    print(f"\n🔎 Fetching news about: {query}\n")
                    news_api.fetch_news(query=query, result_num=5)
                else:
                    print("\n⚠️ No topic found in slots. Skipping news API.")

            elif intent == "get_weather":
                if query:
                    print(f"\n🌤 Fetching weather for: {query}\n")
                else:
                    print("\n🌤 Fetching general weather information...\n")
                get_weather()

            elif intent == "play_music":
                if query:
                    print(f"\n🎵 Searching YouTube for music: {query}")
                    webpage_url, title = search_youtube(query)
                    if webpage_url:
                        stream_url = resolve_stream_url(webpage_url)
                        player = MusicPlayer()
                        player.open(stream_url)
                        player.play()

                        print("🎛️ Controls: [space] pause/resume [←/→] seek [Enter] exit playback")
                        while player.play():
                            key = get_single_key()
                            if key == "space":
                                player.pause_resume()
                            elif key == "left":
                                player.seek_backward()
                            elif key == "right":
                                player.seek_forward()
                            elif key == "enter":
                                player.stop()
                                break
                        continue  # Automatically return to next input
                    else:
                        print("❌ No YouTube video found.")
                else:
                    print("⚠️ No artist or song detected. Skipping playback.")

            else:
                print("✅ Intent not recognized as news, weather, or music. No API called.")

        except KeyboardInterrupt:
            print("\n👋 Exiting.")
            break