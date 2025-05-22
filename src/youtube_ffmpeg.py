import yt_dlp
import subprocess
import platform

# ----------- YouTube Search -----------
def format_duration(seconds):
    minutes = seconds // 60
    secs = seconds % 60
    return f"{int(minutes)}:{int(secs):02d}"

def search_youtube(query, max_results=5):
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'default_search': f'ytsearch{max_results}',
        'noplaylist': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        entries = info.get('entries', [])

        if not entries:
            print("❌ No results found.")
            return None, None

        print("\n🎶 Search Results:")
        print(f"{'No.':<4} {'Title':<50} {'Uploader':<25} {'Duration':<8}")
        print("-" * 90)

        for i, entry in enumerate(entries):
            title = entry.get('title', '')[:48] + ('…' if len(entry.get('title', '')) > 48 else '')
            uploader = entry.get('uploader', '')[:23]
            duration = format_duration(entry.get('duration', 0)) if 'duration' in entry else "Unknown"
            print(f"{i + 1:<4} {title:<50} {uploader:<25} {duration:<8}")

        while True:
            try:
                choice = int(input(f"\nSelect a song (1-{len(entries)}): "))
                if 1 <= choice <= len(entries):
                    selected = entries[choice - 1]
                    return selected['url'], selected['title']
                else:
                    print("⚠️ Invalid choice.")
            except ValueError:
                print("⚠️ Please enter a number.")

# ----------- Stream Resolver -----------
def resolve_stream_url(webpage_url):
    ydl_opts = {
        'quiet': True,
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(webpage_url, download=False)
        return info['url']

# ----------- FFplay Player -----------
def play_with_ffplay(stream_url):
    print(f"\n▶️ Playing stream via ffplay...")
    print("🎛️ Controls (inside ffplay window): [p] Pause | [←/→] Seek | [q] Quit")
    try:
        subprocess.run([
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", stream_url
        ])
    except FileNotFoundError:
        print("❌ ffplay not found! Make sure ffmpeg is installed and ffplay is in your PATH.")

# ----------- Main Program -----------
if __name__ == "__main__":
    query = input("🔍 Enter a song or artist name: ")
    webpage_url, title = search_youtube(query)
    if not webpage_url:
        exit()

    print(f"🎵 Now playing: {title}")
    stream_url = resolve_stream_url(webpage_url)

    play_with_ffplay(stream_url)
