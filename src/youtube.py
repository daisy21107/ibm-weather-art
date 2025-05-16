import yt_dlp
import vlc
import time
import threading
import platform

# ----------- Music Player Class -----------
class MusicPlayer:
    def __init__(self):
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.media = None
        self.progress_thread = None
        self._stop_progress = False
        self.is_paused = False

    def open(self, url):
        self.media = self.instance.media_new(
            url,
            ":http-user-agent=Mozilla/5.0",
            ":http-referrer=https://www.youtube.com/"
        )
        self.player.set_media(self.media)
        self._stop_progress = False
        print("🎵 Media loaded.")

    def play(self):
        if self.media is None:
            print("⚠️ No media loaded.")
            return
        self.player.play()
        print("▶️ Playing...")
        self._start_progress_thread()

    def pause_resume(self):
        if self.player.is_playing():
            self.player.pause()
            self.is_paused = True
            print("⏸️ Paused.")
        elif self.is_paused:
            self.player.play()
            self.is_paused = False
            print("▶️ Resumed.")

    def stop(self):
        self.player.stop()
        self._stop_progress = True
        print("⏹️ Stopped.")

    def seek_forward(self, seconds=10):
        current = self.player.get_time()
        self.player.set_time(current + seconds * 1000)
        print(f"⏩ Forwarded {seconds} seconds.")

    def seek_backward(self, seconds=10):
        current = self.player.get_time()
        self.player.set_time(max(0, current - seconds * 1000))
        print(f"⏪ Rewinded {seconds} seconds.")

    def _start_progress_thread(self):
        def show_progress():
            while not self._stop_progress:
                if self.player.is_playing():
                    total = self.player.get_length() // 1000
                    current = self.player.get_time() // 1000
                    print(f"⏱️ {current//60:02}:{current%60:02} / {total//60:02}:{total%60:02}", end='\r')
                time.sleep(1)

        self.progress_thread = threading.Thread(target=show_progress)
        self.progress_thread.daemon = True
        self.progress_thread.start()

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
        print(f"{'No.':<4} {'Title':<50} {'Uploader':<25} {'Upload Date':<12} {'Duration':<8}")
        print("-" * 105)

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

# ----------- Keyboard Input Handling -----------
def get_single_key():
    if platform.system() == "Windows":
        import msvcrt
        key = msvcrt.getch()
        if key == b'\r':
            return 'enter'
        elif key == b' ':
            return 'space'
        elif key == b'\xe0':
            key2 = msvcrt.getch()
            if key2 == b'K': return 'left'
            elif key2 == b'M': return 'right'
        elif key == b'\x03':
            print("\nExiting...")
            exit(0)
        else:
            return ''
        return ''
    else:
        import sys, tty, termios, select
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            rlist, _, _ = select.select([fd], [], [], 0.1)
            if rlist:
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    if sys.stdin.read(1) == '[':
                        arrow = sys.stdin.read(1)
                        if arrow == 'D': return 'left'
                        elif arrow == 'C': return 'right'
                elif ch == ' ':
                    return 'space'
                elif ch == '\r':
                    return 'enter'
                elif ch == '\x03':
                    print("\nExiting...")
                    exit(0)
            return ''
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# ----------- Main Program -----------
if __name__ == "__main__":
    query = input("🔍 Enter a song or artist name: ")
    webpage_url, title = search_youtube(query)
    if not webpage_url:
        exit()

    print(f"🎵 Now playing: {title}")
    stream_url = resolve_stream_url(webpage_url)

    print("🎛️ Controls: [Space] Pause/Resume | [←/→] Rewind/Forward | [Enter] Stop/Exit")

    player = MusicPlayer()
    player.open(stream_url)
    player.play()

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
