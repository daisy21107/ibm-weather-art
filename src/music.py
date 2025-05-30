# This script is not used for current project. 
import os
import requests
import vlc
import time
import threading

def play_music(audio_url):
    print(f"Playing: {audio_url}")
    player = vlc.MediaPlayer(audio_url)
    player.play()
    time.sleep(1)  # Allow VLC to start

    duration = player.get_length() / 1000  # Convert ms to seconds
    if duration <= 0:
        duration = 30  # Default to 30s if duration not available

    print(f"Playing duration: {duration:.2f} seconds")
    print("Press 'p' to Pause/Resume, 's' to Stop")

    stop_flag = threading.Event()

    def user_control():
        while not stop_flag.is_set():
            cmd = input().strip().lower()
            if cmd == 'p':
                if player.is_playing():
                    player.pause()
                    print("Paused. Press 'p' to Resume.")
                else:
                    player.play()
                    print("Resumed. Press 'p' to Pause again.")
            elif cmd == 's':
                player.stop()
                stop_flag.set()
                print("Stopped.")
            else:
                print("Unknown command. Use 'p' for Pause/Resume, 's' for Stop.")

    control_thread = threading.Thread(target=user_control, daemon=True)
    control_thread.start()

    start_time = time.time()
    while time.time() - start_time < duration:
        if stop_flag.is_set():
            break
        time.sleep(0.5)

    if not stop_flag.is_set():
        player.stop()
        print("Playback finished.")

if __name__ == '__main__':
    api_key = os.environ.get("JAMENDO_API_KEY")
    if not api_key:
        api_key = input("Enter your Jamendo API key: ").strip()
        if not api_key:
            raise ValueError("JAMENDO_API_KEY is not set.")

    query = input("🔍 Search for music: ").strip()
    if not query:
        print("Empty query. Exiting.")
        exit(0)

    url = "https://api.jamendo.com/v3.0/tracks/"
    params = {
        "client_id": api_key,
        "format": "json",
        "limit": 5,
        "namesearch": query,
        "audioformat": "mp32",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        exit(1)

    data = response.json()
    tracks = data.get("results", [])

    if not tracks:
        print("No results found.")
        exit(0)

    print("\nSearch Results:")
    for i, track in enumerate(tracks, 1):
        print(f"{i}. {track['name']} - {track['artist_name']}")

    try:
        choice = int(input(f"Select track to play (1-{len(tracks)}): "))
    except ValueError:
        print("Invalid input. Exiting.")
        exit(1)

    if 1 <= choice <= len(tracks):
        audio_url = tracks[choice - 1]["audio"]
        print(f"To pause/resume, press 'p'. To stop, press 's'.")
        play_music(audio_url)
    else:
        print("Invalid choice. Exiting.")
