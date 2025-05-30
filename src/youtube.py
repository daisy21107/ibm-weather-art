import sys
import os
from typing import Optional, Tuple, Dict, Any

import vlc
import yt_dlp
import time
import threading
import platform

# ----------- Music Player Class -----------
class MusicPlayer:
    def __init__(self):
        self.instance: Optional[vlc.Instance] = vlc.Instance()
        if self.instance is None:
            raise RuntimeError("Failed to create VLC instance")
        self.player = self.instance.media_player_new()
        self.media = None
        self.progress_thread = None
        self._stop_progress = False
        self.is_paused = False

    def open(self, url: str) -> None:
        if self.instance is None:
            raise RuntimeError("VLC instance not initialized")
        self.media = self.instance.media_new(
            url,
            ":http-user-agent=Mozilla/5.0",
            ":http-referrer=https://www.youtube.com/"
        )
        self.player.set_media(self.media)
        self._stop_progress = False
        print("🎵 Media loaded.")

    def play(self) -> None:
        if self.media is None:
            print("⚠️ No media loaded.")
            return
        self.player.play()
        print("▶️ Playing...")
        self._start_progress_thread()

    def pause_resume(self) -> None:
        if self.player.is_playing():
            self.player.pause()
            self.is_paused = True
            print("⏸️ Paused.")
        elif self.is_paused:
            self.player.play()
            self.is_paused = False
            print("▶️ Resumed.")

    def stop(self) -> None:
        self.player.stop()
        self._stop_progress = True
        print("⏹️ Stopped.")

    def seek_forward(self, seconds: int = 10) -> None:
        current = self.player.get_time()
        self.player.set_time(current + seconds * 1000)
        print(f"⏩ Forwarded {seconds} seconds.")

    def seek_backward(self, seconds: int = 10) -> None:
        current = self.player.get_time()
        self.player.set_time(max(0, current - seconds * 1000))
        print(f"⏪ Rewinded {seconds} seconds.")

    def _start_progress_thread(self) -> None:
        def show_progress() -> None:
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
def format_duration(seconds: float) -> str:
    minutes = seconds // 60
    secs = seconds % 60
    return f"{int(minutes)}:{int(secs):02d}"

def search_youtube(query: str, max_results: int = 5) -> Tuple[Optional[str], Optional[str]]:
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'default_search': f'ytsearch{max_results*2}',
        'noplaylist': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if info is None:
            print("❌ No results found.")
            return None, None
            
        entries = info.get('entries', [])
        
        # 过滤掉超过6分钟的视频
        filtered_entries = [
            entry for entry in entries 
            if 'duration' in entry and entry['duration'] <= 360
        ]

        if not filtered_entries:
            print("❌ No results found (after filtering videos longer than 6 minutes).")
            return None, None

        print("\n🎶 Search Results (filtered to 6 minutes or less):")
        print(f"{'No.':<4} {'Title':<50} {'Uploader':<25} {'Duration':<8}")
        print("-" * 95)

        for i, entry in enumerate(filtered_entries[:max_results]):
            title = entry.get('title', '')[:48] + ('…' if len(entry.get('title', '')) > 48 else '')
            uploader = entry.get('uploader', '')[:23]
            duration = format_duration(entry.get('duration', 0))
            print(f"{i + 1:<4} {title:<50} {uploader:<25} {duration:<8}")

        while True:
            try:
                choice = int(input(f"\nSelect a song (1-{len(filtered_entries[:max_results])}): "))
                if 1 <= choice <= len(filtered_entries[:max_results]):
                    selected = filtered_entries[choice - 1]
                    return selected['url'], selected['title']
                else:
                    print("⚠️ Invalid choice.")
            except ValueError:
                print("⚠️ Please enter a number.")

# ----------- Stream Resolver -----------
def resolve_stream_url(webpage_url: str) -> str:
    ydl_opts = {
        'quiet': True,
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(webpage_url, download=False)
        if info is None:
            raise RuntimeError("Failed to extract video info")
        return info['url']

# ----------- Keyboard Input Handling -----------
def get_single_key() -> str:
    if platform.system() == "Windows":
        import msvcrt
        key = msvcrt.getch()  # type: ignore
        if key == b'\r':
            return 'enter'
        elif key == b' ':
            return 'space'
        elif key == b'\xe0':
            key2 = msvcrt.getch()  # type: ignore
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
