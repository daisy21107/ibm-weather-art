from MBERTtesting import infer
from src.news import GuardianNewsAPI
from src.weather import get_weather
from src.youtube import search_youtube, resolve_stream_url, MusicPlayer, get_single_key

# API KEYS
GUARDIAN_API_KEY = ""  # Replace with your Guardian API key
WEATHER_API_KEY = ""    # Replace with your weather API key

news_api = GuardianNewsAPI(GUARDIAN_API_KEY)

# Extract topic slot
def extract_topic(slots):
    topic = []
    collecting = False
    for word, tag in slots:
        if tag == "B-topic":
            if collecting:
                break
            topic = [word]
            collecting = True
        elif tag == "I-topic" and collecting:
            topic.append(word)
        else:
            if collecting:
                break
    return " ".join(topic) if topic else None

# Extract artist and song
def extract_music_query(slots):
    artist_words = []
    song_words = []
    curr_tag = None
    for word, tag in slots:
        if tag == "B-artist":
            artist_words = [word]
            curr_tag = "artist"
        elif tag == "I-artist" and curr_tag == "artist":
            artist_words.append(word)
        elif tag == "B-song":
            song_words = [word]
            curr_tag = "song"
        elif tag == "I-song" and curr_tag == "song":
            song_words.append(word)
        else:
            curr_tag = None
    artist = " ".join(artist_words) if artist_words else ""
    song = " ".join(song_words) if song_words else ""
    if artist and song:
        return f"{song} by {artist}"
    return song or artist or None

#Main interaction loop
if __name__ == "__main__":
    while True:
        try:
            text = input("\n🗣 Please enter an English request: ").strip()
            if not text:
                continue

            intent, slots = infer(text)
            if intent is None:
                continue

            print(f"\n🎯 Predicted intent: {intent}")
            print("📌 Slot tagging:")
            for word, tag in slots:
                print(f"  {word:<12} -> {tag}")

            if intent == "get_news":
                topic = extract_topic(slots)
                if topic:
                    print(f"\n🔎 Fetching news about: {topic}\n")
                    news_api.fetch_news(query=topic, result_num=5)
                else:
                    print("\n⚠️ No topic found in slots. Skipping news API.")

            elif intent == "get_weather":
                print("\n🌤 Fetching weather information...\n")
                get_weather()

            elif intent == "play_music":
                query = extract_music_query(slots)
                if query:
                    print(f"\n🎵 Searching YouTube for music: {query}")
                    webpage_url, title = search_youtube(query)
                    if webpage_url:
                        stream_url = resolve_stream_url(webpage_url)
                        player = MusicPlayer()
                        player.open(stream_url)
                        player.play()

                        print("🎛️ Controls: [space] pause/resume [←/→] seek [Enter] exit playback")
                        while True:
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

                        # Automatically exit to next prompt
                        continue
                    else:
                        print("❌ No YouTube video found.")
                else:
                    print("⚠️ No artist or song detected. Skipping playback.")

            else:
                print("✅ Intent not recognized as news, weather, or music. No API called.")

        except KeyboardInterrupt:
            print("\n👋 Exiting.")
            break