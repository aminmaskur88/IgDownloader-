import time
import os
import sys
import requests
import json
import re
import shutil
import subprocess
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import yt_dlp
import instaloader

# --- SELENIUM IMPORTS ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException


# ==============================================================================
# CONFIGURATION, STORAGE & SYSTEM CHECKS
# ==============================================================================

def is_path_writable(path):
    """Memeriksa apakah direktori benar-benar memiliki izin tulis (write permission) di Android/Termux."""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, f".perm_probe_{os.getpid()}")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False


def get_base_download_dir():
    """Mendapatkan direktori penyimpanan utama di internal storage Android atau fallback lokal."""
    # 1. Cek ~/storage/shared/Download (shortcut standar termux-setup-storage)
    termux_shared = os.path.expanduser("~/storage/shared/Download")
    if is_path_writable(termux_shared):
        return termux_shared

    # 2. Cek path langsung Android internal storage
    android_dir = "/storage/emulated/0/Download"
    if is_path_writable(android_dir):
        return android_dir

    # 3. Fallback ke folder lokal proyek 'downloads/'
    local_dir = os.path.abspath("downloads")
    try:
        os.makedirs(local_dir, exist_ok=True)
    except Exception:
        pass
    return local_dir


BASE_DOWNLOAD_DIR = get_base_download_dir()


def safe_ensure_dir(target_dir):
    """
    Membuat direktori dengan aman. Jika izin Android ditolak (Permission denied),
    otomatis dialihkan ke folder lokal 'downloads/' tanpa membuat program crash.
    """
    try:
        os.makedirs(target_dir, exist_ok=True)
        probe = os.path.join(target_dir, f".probe_{os.getpid()}")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return target_dir
    except (PermissionError, OSError):
        # Ekstrak subfolder relatif (misal 'YouTube', 'TikTok', 'Instagram/username')
        if "/Download/" in target_dir:
            sub = target_dir.split("/Download/")[-1]
        elif "/downloads/" in target_dir:
            sub = target_dir.split("/downloads/")[-1]
        else:
            sub = os.path.basename(target_dir)

        local_fallback = os.path.abspath(os.path.join("downloads", sub))
        os.makedirs(local_fallback, exist_ok=True)

        print("\n" + "!" * 62)
        print("⚠️  IZIN PENYIMPANAN ANDROID BELUM DIBERIKAN!")
        print(f"   Target gagal diakses : {target_dir}")
        print("💡 AGAR TERSIMPAN KE DOWNLOAD/GALERI HP:")
        print("   Jalankan perintah ini di Termux:")
        print("   👉 termux-setup-storage")
        print("   Lalu klik 'Izinkan' (Allow) pada pop-up Android.")
        print(f"🔄 File dialihkan sementara ke folder lokal: {local_fallback}/")
        print("!" * 62 + "\n")
        return local_fallback


def get_ffmpeg_path():
    """Mendeteksi lokasi binary ffmpeg di Termux atau Linux."""
    path = shutil.which('ffmpeg')
    if path:
        return path
    termux_candidates = [
        '/data/data/com.termux/files/usr/bin/ffmpeg',
        os.path.expanduser('~/../usr/bin/ffmpeg'),
        '/system/bin/ffmpeg',
    ]
    for p in termux_candidates:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
    return None


def check_environment():
    """Memeriksa kesiapan lingkungan (Storage & FFmpeg) dan menampilkan panduan jika belum siap."""
    base_dir = get_base_download_dir()
    has_shared_storage = ("/storage/emulated/0" in base_dir or "/shared/" in base_dir)
    has_ffmpeg = bool(get_ffmpeg_path())

    issues = []
    if not has_shared_storage:
        issues.append("📁 Izin Penyimpanan: Belum ada izin storage HP. Jalankan 'termux-setup-storage' di Termux.")
    if not has_ffmpeg:
        issues.append("🎬 FFmpeg: Belum terpasang (Wajib untuk 1080p & MP3). Jalankan 'pkg install ffmpeg -y'.")

    if issues:
        print("\n" + "=" * 62)
        print("  ⚠️  CATATAN PERSIAPAN PERANGKAT INI:")
        for issue in issues:
            print(f"  • {issue}")
        print("=" * 62)


# ==============================================================================
# 1. URL & PLATFORM DETECTION UTILITIES
# ==============================================================================

def extract_clean_url(raw_input):
    """Mengekstrak URL bersih dari input teks (menangani teks tambahan saat copy-paste)."""
    if not raw_input:
        return ""
    raw_input = raw_input.strip()
    match = re.search(r'https?://[^\s]+', raw_input)
    if match:
        return match.group(0).rstrip('.,;)]}>"\'')
    return raw_input


def detect_platform_and_type(url):
    """
    Mendeteksi platform dan jenis konten secara otomatis dari URL.
    Returns: (platform_name, content_type, details)
    """
    clean_url = extract_clean_url(url)
    try:
        parsed = urlparse(clean_url if clean_url.startswith(('http://', 'https://')) else 'https://' + clean_url)
        domain = parsed.netloc.lower()
        path = parsed.path.strip('/')
        parts = [p for p in path.split('/') if p]
    except Exception:
        domain = ""
        parts = []

    # Instagram
    if any(ig in domain for ig in ['instagram.com', 'instagr.am']):
        if any(p in ['p', 'reel', 'reels', 'tv'] for p in parts):
            return 'Instagram', 'post', clean_url
        elif parts and parts[0] not in ['explore', 'stories', 'direct', 'accounts', 'api']:
            return 'Instagram', 'profile', parts[0]
        return 'Instagram', 'unknown', clean_url

    # YouTube
    if any(yt in domain for yt in ['youtube.com', 'youtu.be']):
        if 'shorts' in parts:
            return 'YouTube', 'shorts', clean_url
        return 'YouTube', 'video', clean_url

    # TikTok
    if 'tiktok.com' in domain:
        return 'TikTok', 'video', clean_url

    # Twitter / X
    if any(tw in domain for tw in ['twitter.com', 'x.com']):
        return 'Twitter_X', 'media', clean_url

    # Facebook
    if any(fb in domain for fb in ['facebook.com', 'fb.watch', 'fb.com']):
        return 'Facebook', 'media', clean_url

    # Reddit
    if any(rd in domain for rd in ['reddit.com', 'redd.it']):
        return 'Reddit', 'media', clean_url

    # Pinterest
    if any(pin in domain for pin in ['pinterest.com', 'pin.it']):
        return 'Pinterest', 'media', clean_url

    # Threads
    if 'threads.net' in domain:
        return 'Threads', 'media', clean_url

    # SoundCloud
    if 'soundcloud.com' in domain:
        return 'SoundCloud', 'audio', clean_url

    # Generic / Universal
    if domain:
        name = domain.replace('www.', '').split('.')[0].capitalize()
        return name, 'universal', clean_url

    return 'Universal', 'unknown', clean_url


def get_username_from_url(url):
    """Mengekstrak username Instagram dari URL atau teks."""
    url = url.strip().lstrip('@')
    if ' ' in url:
        url = url.split(' ')[-1]
        
    if 'instagram.com' in url or 'instagr.am' in url:
        path = urlparse(url if url.startswith('http') else 'https://' + url).path
        parts = [p for p in path.split('/') if p]
        if parts:
            if parts[0] in ['p', 'reel', 'reels', 'tv'] and len(parts) > 1:
                return parts[1]
            return parts[0]
    return url


def get_shortcode_from_url(url):
    """Mengekstrak shortcode postingan Instagram dari URL."""
    try:
        path = urlparse(url).path
        parts = [p for p in path.strip('/').split('/') if p]
        if 'p' in parts:
            return parts[parts.index('p') + 1]
        elif 'reel' in parts:
            return parts[parts.index('reel') + 1]
        elif 'reels' in parts:
            return parts[parts.index('reels') + 1]
        return url
    except Exception:
        return url


# ==============================================================================
# 2. UNIVERSAL DOWNLOAD ENGINE (yt-dlp + ffmpeg)
# ==============================================================================

def check_video_codecs(file_path):
    """Mendapatkan nama codec video dan audio dari file menggunakan ffprobe."""
    ffprobe_path = shutil.which('ffprobe') or '/data/data/com.termux/files/usr/bin/ffprobe'
    if not os.path.exists(ffprobe_path) and not shutil.which('ffprobe'):
        return None, None
    try:
        cmd_v = [
            ffprobe_path, '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        res_v = subprocess.run(cmd_v, capture_output=True, text=True, timeout=10)
        vcodec = res_v.stdout.strip().lower()

        cmd_a = [
            ffprobe_path, '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        res_a = subprocess.run(cmd_a, capture_output=True, text=True, timeout=10)
        acodec = res_a.stdout.strip().lower()
        return vcodec, acodec
    except Exception:
        return None, None


def ensure_social_ready(file_path):
    """
    Mengonversi video ke format standar H.264 (AVC) + AAC MP4 (+faststart)
    agar dijamin 100% bisa di-post di Instagram, WhatsApp, TikTok, FB, dll.
    """
    if not file_path or not os.path.exists(file_path):
        return file_path

    vcodec, acodec = check_video_codecs(file_path)
    # Jika sudah H.264 dan AAC, tidak perlu di-transcode (langsung siap!)
    if vcodec == 'h264' and (acodec == 'aac' or not acodec):
        return file_path

    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        return file_path

    print(f"\n[🔄 OPTIMASI CODEC SOSMED] Codec asal: Video={vcodec}, Audio={acodec}")
    print("    Instagram & WhatsApp mewajibkan video H.264 (AVC) dan audio AAC.")
    print("    Mengonversi otomatis agar siap diposting & dikirim...", end=" ", flush=True)

    base, ext = os.path.splitext(file_path)
    temp_out = base + "_social.mp4"

    cmd = [ffmpeg_path, '-y', '-i', file_path]

    # Video: Jika bukan h264, transcode ke libx264 dengan pixel format yuv420p
    if vcodec != 'h264':
        cmd.extend(['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '22', '-pix_fmt', 'yuv420p'])
    else:
        cmd.extend(['-c:v', 'copy'])

    # Audio: Jika bukan aac, transcode ke aac 192k
    if acodec != 'aac':
        cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
    else:
        cmd.extend(['-c:a', 'copy'])

    cmd.extend(['-movflags', '+faststart', temp_out])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode == 0 and os.path.exists(temp_out) and os.path.getsize(temp_out) > 0:
            final_path = base + ".mp4"
            if os.path.exists(file_path) and file_path != final_path:
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            os.replace(temp_out, final_path)
            print("SELESAI! ✓ (Format: H.264/AAC MP4)")
            return final_path
        else:
            if os.path.exists(temp_out):
                os.remove(temp_out)
            print("Gagal optimasi, menggunakan file asli.")
            return file_path
    except Exception as e:
        if os.path.exists(temp_out):
            try:
                os.remove(temp_out)
            except Exception:
                pass
        print(f"Bypass optimasi ({e})")
        return file_path


YOUTUBE_QUALITY_PRESETS = {
    '1': {
        'label': '1080p (Full HD - Siap Post IG/WA)',
        'format': 'bestvideo[height<=1080][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=1080][vcodec^=avc1]+bestaudio/bestvideo[width<=1080][vcodec^=avc1]+bestaudio/bestvideo[height<=1080]+bestaudio/bestvideo[width<=1080]+bestaudio/best[height<=1080]/best',
        'is_audio': False,
    },
    '2': {
        'label': '720p (HD - Siap Post IG/WA)',
        'format': 'bestvideo[height<=720][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=720][vcodec^=avc1]+bestaudio/bestvideo[width<=720][vcodec^=avc1]+bestaudio/bestvideo[height<=720]+bestaudio/bestvideo[width<=720]+bestaudio/best[height<=720]/best',
        'is_audio': False,
    },
    '3': {
        'label': '480p (Standar / Hemat Kuota)',
        'format': 'bestvideo[height<=480][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=480][vcodec^=avc1]+bestaudio/bestvideo[width<=480][vcodec^=avc1]+bestaudio/bestvideo[height<=480]+bestaudio/best[height<=480]/best',
        'is_audio': False,
    },
    '4': {
        'label': '360p (Rendah / Super Hemat)',
        'format': 'bestvideo[height<=360][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=360][vcodec^=avc1]+bestaudio/bestvideo[width<=360][vcodec^=avc1]+bestaudio/bestvideo[height<=360]+bestaudio/best[height<=360]/best',
        'is_audio': False,
    },
    '5': {
        'label': 'Kualitas Tertinggi (Maksimal / Best Available)',
        'format': 'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo*+bestaudio/best',
        'is_audio': False,
    },
    '6': {
        'label': 'Audio Saja (MP3)',
        'format': 'bestaudio/best',
        'is_audio': True,
    },
}


def prompt_youtube_quality():
    """Menampilkan pilihan kualitas khusus untuk download YouTube."""
    print("\n" + "="*50)
    print("  🎬 PILIH KUALITAS DOWNLOAD YOUTUBE")
    print("="*50)
    print(" [1] 1080p (Full HD - Siap Post IG/WA)")
    print(" [2] 720p (HD - Siap Post IG/WA)")
    print(" [3] 480p (Standar / Hemat Kuota)")
    print(" [4] 360p (Rendah / Super Hemat)")
    print(" [5] Kualitas Tertinggi (Maksimal / Best Available)")
    print(" [6] Audio Saja (MP3)")
    print("-" * 50)
    
    try:
        pilihan = input("Pilih kualitas (1-6 / Enter untuk 1080p): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        pilihan = '1'

    # Mapping fleksibel jika pengguna mengetik nomor menu atau resolusinya langsung
    if pilihan in ['1', '1080', '1080p', '']:
        key = '1'
    elif pilihan in ['2', '720', '720p']:
        key = '2'
    elif pilihan in ['3', '480', '480p']:
        key = '3'
    elif pilihan in ['4', '360', '360p']:
        key = '4'
    elif pilihan in ['5', 'max', 'best', 'tertinggi']:
        key = '5'
    elif pilihan in ['6', 'mp3', 'audio']:
        key = '6'
    else:
        print(f"[!] Pilihan '{pilihan}' tidak dikenal. Menggunakan default: 1080p.")
        key = '1'

    selected = YOUTUBE_QUALITY_PRESETS[key]
    return selected['format'], selected['is_audio'], selected['label']


def download_with_ytdlp(url, output_dir=None, platform_name="Universal", format_spec=None, is_audio=False, quality_label=None):
    """
    Mendownload media dari ribuan platform (YouTube, TikTok, FB, X, dll) menggunakan yt-dlp.
    Hasil otomatis disimpan di direktori output_dir.
    """
    clean_url = extract_clean_url(url)
    if not output_dir:
        output_dir = os.path.join(BASE_DOWNLOAD_DIR, platform_name)

    # Pastikan folder bisa ditulis (fallback otomatis jika Permission Denied di Android)
    output_dir = safe_ensure_dir(output_dir)

    ffmpeg_path = get_ffmpeg_path()
    has_ffmpeg = bool(ffmpeg_path)

    if not has_ffmpeg:
        print("\n" + "!" * 62)
        print("⚠️  PAKET 'ffmpeg' TIDAK DITEMUKAN DI PERANGKAT INI!")
        print("   YouTube memisahkan video kualitas tinggi (1080p) & audio.")
        print("   Tanpa ffmpeg, format terpisah tidak bisa digabung.")
        print("💡 SOLUSI AGAR BISA 1080p, 720p HD & MP3:")
        print("   Jalankan perintah ini di terminal Termux:")
        print("   👉 pkg install ffmpeg -y")
        print("🔄 Otomatis mengunduh format langsung terbaik (single-stream)...")
        print("!" * 62 + "\n")

        # Format tanpa merge (progressive stream) agar TIDAK error di yt-dlp
        if is_audio:
            format_spec = 'bestaudio/best'
        else:
            format_spec = 'best[vcodec^=avc1][ext=mp4]/best[ext=mp4]/best'
    else:
        if not format_spec:
            format_spec = 'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo*+bestaudio/best'

    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(title).80B [%(id)s].%(ext)s'),
        'format': format_spec,
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
    }

    if has_ffmpeg:
        ydl_opts['ffmpeg_location'] = ffmpeg_path
        if is_audio:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            ydl_opts['merge_output_format'] = 'mp4'

    # Gunakan cookiefile jika tersedia
    for cookie_name in ['cookies.txt', 'youtube_cookies.txt']:
        if os.path.exists(cookie_name):
            ydl_opts['cookiefile'] = cookie_name
            break

    print(f"\n[+] Mengunduh via Universal Engine (yt-dlp)...")
    print(f"[+] Target Platform : {platform_name}")
    if quality_label:
        print(f"[+] Kualitas Pilihan: {quality_label}")
    print(f"[+] Folder Output   : {output_dir}/")
    print("-" * 55)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            title = info.get('title', 'Unknown Title') if info else 'Unknown'

            # Optimasi otomatis ke H.264 + AAC MP4 jika format belum standar sosmed
            if not is_audio and has_ffmpeg and info:
                downloaded_file = None
                if '_filename' in info and os.path.exists(info['_filename']):
                    downloaded_file = info['_filename']
                else:
                    cand = ydl.prepare_filename(info)
                    if os.path.exists(cand):
                        downloaded_file = cand
                    else:
                        base_cand, _ = os.path.splitext(cand)
                        for ext in ['.mp4', '.mkv', '.webm']:
                            if os.path.exists(base_cand + ext):
                                downloaded_file = base_cand + ext
                                break
                if downloaded_file:
                    ensure_social_ready(downloaded_file)

            print("-" * 55)
            print(f"[✓] SUKSES DIDOWNLOAD : {title}")
            print(f"[✓] Tersimpan di      : {output_dir}/")
            return True, title
    except Exception as e:
        err_msg = str(e)
        print("-" * 55)
        print(f"[!] Gagal download: {err_msg}")
        if "ffmpeg is not installed" in err_msg:
            print("\n💡 Tips: Instal FFmpeg dengan perintah: pkg install ffmpeg -y")
        elif "Permission denied" in err_msg:
            print("\n💡 Tips: Izinkan storage dengan perintah: termux-setup-storage")
        return False, err_msg


def handle_universal_download(link):
    """Router otomatis untuk download link dari mana saja dan simpan ke /storage/emulated/0/Download."""
    clean_url = extract_clean_url(link)
    if not clean_url:
        print("[!] Link tidak valid atau kosong!")
        return

    platform, content_type, details = detect_platform_and_type(clean_url)
    print(f"\n[+] Link Terdeteksi : {clean_url}")
    print(f"[+] Platform        : {platform} ({content_type.upper()})")

    # Kasus: Link Profil Instagram
    if platform == 'Instagram' and content_type == 'profile':
        username = details
        print(f"\n[ℹ] Tautan ini adalah profil Instagram: @{username}")
        print("Pilih tindakan:")
        print("1. Scrape 12 Postingan Terbaru (Mode Ringan - Tanpa Scroll)")
        print("2. Scrape Profil Lengkap (Custom Scroll Selenium)")
        print("0. Batal")
        sub_choice = input("Masukkan pilihan (1/2/0): ").strip()
        if sub_choice == '1':
            run_instagram_profile_scraper(username, max_scroll=0)
        elif sub_choice == '2':
            run_instagram_profile_scraper(username, max_scroll=None)
        return

    # Kasus: Postingan / Reels Instagram
    if platform == 'Instagram':
        target_dir = safe_ensure_dir(os.path.join(BASE_DOWNLOAD_DIR, "Instagram"))
        cookies_dict = load_cookies(prompt_if_missing=False)
        if cookies_dict:
            print("[+] Menggunakan sesi login cookies.json untuk Instagram...")
            try:
                username = get_username_from_post(clean_url, cookies_dict)
            except Exception:
                username = "Instagram_Downloads"
            if not username or username == "Unknown_User":
                username = "Instagram_Downloads"

            user_dir = safe_ensure_dir(os.path.join(target_dir, username))

            sukses, pesan = download_post_media(clean_url, user_dir, cookies_dict)
            if sukses:
                print(f"[✓] {pesan}")
                return
            else:
                print(f"[!] Instaloader info ({pesan}), beralih ke Universal Engine yt-dlp...")
        else:
            print("[ℹ] cookies.json tidak ditemukan, mengunduh via Universal Engine...")

        sukses, res = download_with_ytdlp(clean_url, output_dir=target_dir, platform_name="Instagram")
        if not sukses and not cookies_dict:
            print("\n[💡 TIPS] Jika konten Instagram ini bersifat privat, silakan siapkan cookies.json.")
        return

    # Kasus: YouTube (Pilihan Resolusi 1080p, 720p, 480p, dll)
    if platform == 'YouTube':
        format_spec, is_audio, quality_label = prompt_youtube_quality()
        target_dir = safe_ensure_dir(os.path.join(BASE_DOWNLOAD_DIR, "YouTube"))
        download_with_ytdlp(
            clean_url,
            output_dir=target_dir,
            platform_name="YouTube",
            format_spec=format_spec,
            is_audio=is_audio,
            quality_label=quality_label
        )
        return

    # Kasus: Semua Platform Lain (TikTok, X/Twitter, FB, Pinterest, Reddit, dll)
    target_dir = safe_ensure_dir(os.path.join(BASE_DOWNLOAD_DIR, platform))
    download_with_ytdlp(clean_url, output_dir=target_dir, platform_name=platform)


# ==============================================================================
# 3. INSTAGRAM SCRAPER & SELENIUM SUITE
# ==============================================================================

def setup_driver():
    """Mengatur dan menjalankan Chromium dalam mode headless di Termux."""
    print("[+] Menyiapkan Browser (Chromium)... ini mungkin memakan waktu sebentar.")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--window-size=1920,1080")
    
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
    chrome_options.add_argument(f"user-agent={user_agent}")
    
    chrome_options.binary_location = "/data/data/com.termux/files/usr/bin/chromium-browser"
    service = Service("/data/data/com.termux/files/usr/bin/chromedriver")
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except WebDriverException as e:
        print(f"\n[!] GAGAL MENJALANKAN BROWSER: {e}")
        print("Pastikan chromium-browser terinstal dengan benar (pkg install chromium).")
        return None


def load_cookies(file_path='cookies.json', prompt_if_missing=True):
    """Membaca cookies dari JSON atau meminta input jika file tidak ada."""
    data = None
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"[!] Error: Format JSON di {file_path} tidak valid!")
            return None
    elif prompt_if_missing:
        print(f"\n[!] File {file_path} tidak ditemukan.")
        print("[+] Silakan PASTE (tempel) JSON Cookies dari ekstensi Chrome di bawah ini.")
        print("[+] (Setelah paste, tekan Enter lalu tekan Ctrl+D untuk selesai):")
        print("-" * 30)
        
        try:
            input_data = sys.stdin.read().strip()
            if not input_data:
                print("[!] Input kosong!")
                return None
                
            data = json.loads(input_data)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"\n[+] Cookies berhasil disimpan ke {file_path}")
            print("-" * 30)
        except Exception as e:
            print(f"\n[!] Gagal memproses input: {e}")
            return None
    else:
        return None

    if data:
        cookies_dict = {}
        if isinstance(data, list):
            for entry in data:
                if 'name' in entry and 'value' in entry:
                    cookies_dict[entry['name']] = entry['value']
        elif isinstance(data, dict):
            cookies_dict = data
        return cookies_dict
    return None


def inject_cookies(driver, url="https://www.instagram.com/"):
    """Memasukkan cookie ke dalam browser agar login otomatis."""
    print("[+] Membuka Instagram dan memasukkan Cookie login...")
    driver.get(url)
    time.sleep(3)
    
    cookies_dict = load_cookies(prompt_if_missing=True)
    if not cookies_dict:
        sys.exit(1)
        
    for name, value in cookies_dict.items():
        driver.add_cookie({'name': name, 'value': str(value), 'domain': '.instagram.com'})
        
    print("[+] Cookie berhasil dimasukkan. Merefresh halaman...")
    driver.refresh()
    time.sleep(4)


def scrape_post_links(driver, username, max_scrolls=5):
    """Membuka profil dan men-scroll untuk mengumpulkan link postingan."""
    profile_url = f"https://www.instagram.com/{username}/"
    print(f"\n[+] Membuka profil: {profile_url}")
    driver.get(profile_url)
    time.sleep(5)
    
    post_links = set()
    hrefs = driver.execute_script("return Array.from(document.querySelectorAll('a')).map(a => a.href);")
    for href in hrefs:
        if href and ('/p/' in href or '/reel/' in href):
            post_links.add(href)
            
    print(f"[+] Ditemukan {len(post_links)} link di halaman awal.")
    
    if max_scrolls and max_scrolls > 0:
        print(f"[+] Mengumpulkan link tambahan (Maksimal Scroll: {max_scrolls}x)...")
        for i in range(max_scrolls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            hrefs = driver.execute_script("return Array.from(document.querySelectorAll('a')).map(a => a.href);")
            for href in hrefs:
                if href and ('/p/' in href or '/reel/' in href):
                    post_links.add(href)
                    
            print(f"    - Scroll ke-{i+1}: Ditemukan total {len(post_links)} link sejauh ini.")
        
    return list(post_links)


def download_post_media(url, target_dir, cookies_dict):
    """Mendownload semua media dari satu link postingan menggunakan Instaloader."""
    shortcode = get_shortcode_from_url(url)
    os.makedirs(target_dir, exist_ok=True)
    
    L = instaloader.Instaloader(
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern='',
        max_connection_attempts=1
    )
    L.context._session.cookies.update(cookies_dict)
    L.context._session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        'X-CSRFToken': cookies_dict.get('csrftoken', ''),
        'X-IG-App-ID': '936619743392459',
        'X-ASBD-ID': '198387',
        'X-Instagram-AJAX': '1006509424',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Viewport-Width': '1920',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        headers = {
            'User-Agent': L.context._session.headers.get('User-Agent'),
            'Cookie': '; '.join([f"{k}={v}" for k, v in cookies_dict.items()])
        }
        
        if post.typename == 'GraphSidecar':
            carousel_dir = os.path.join(target_dir, shortcode)
            if not os.path.exists(carousel_dir):
                os.makedirs(carousel_dir, exist_ok=True)
                
            nodes = list(post.get_sidecar_nodes())
            berhasil_download = 0
            
            for idx, node in enumerate(nodes):
                is_video = node.is_video
                media_url = node.video_url if is_video else node.display_url
                ext = ".mp4" if is_video else ".jpg"
                filename = os.path.join(carousel_dir, f"slide_{idx+1}{ext}")
                
                if os.path.exists(filename):
                    berhasil_download += 1
                    continue
                    
                response = requests.get(media_url, stream=True, headers=headers)
                if response.status_code == 200:
                    with open(filename, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    berhasil_download += 1
                    
            return True, f"SUKSES -> {berhasil_download}/{len(nodes)} file di {carousel_dir}/"
            
        else:
            is_video = post.is_video
            media_url = post.video_url if is_video else post.url
            ext = ".mp4" if is_video else ".jpg"
            filename = os.path.join(target_dir, f"{shortcode}_single{ext}")
            
            if os.path.exists(filename):
                return True, f"File sudah ada: {filename} (SKIP)"
                
            response = requests.get(media_url, stream=True, headers=headers)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True, f"SUKSES -> {filename}"
            else:
                return False, f"HTTP Error {response.status_code}"
            
    except Exception as e:
        return False, f"Error: {e}"


def get_username_from_post(url, cookies_dict):
    """Mendapatkan username pemilik postingan dari link menggunakan Instaloader."""
    shortcode = get_shortcode_from_url(url)
    L = instaloader.Instaloader()
    L.context._session.cookies.update(cookies_dict)
    L.context._session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        'X-CSRFToken': cookies_dict.get('csrftoken', ''),
        'X-IG-App-ID': '936619743392459',
        'X-ASBD-ID': '198387',
        'X-Instagram-AJAX': '1006509424'
    })
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        return post.owner_username
    except Exception:
        return "Unknown_User"


def run_instagram_profile_scraper(username, max_scroll=None):
    """Menjalankan scraper profil Instagram menggunakan Chromium Selenium."""
    cookies_dict = load_cookies(prompt_if_missing=True)
    if not cookies_dict:
        print("[!] Gagal memuat cookies. Scraper profil dibatalkan.")
        return

    if max_scroll is None:
        try:
            val = input("Berapa kali scroll? (Default: 3): ").strip()
            max_scroll = int(val) if val else 3
        except ValueError:
            max_scroll = 3
            print("Input tidak valid, menggunakan default 3 kali scroll.")

    driver = setup_driver()
    if not driver:
        return

    try:
        inject_cookies(driver)
        links = scrape_post_links(driver, username, max_scrolls=max_scroll)
        
        print(f"\n[+] Total Link yang akan diproses: {len(links)}")
        if len(links) == 0:
            print("[!] Tidak ada postingan yang ditemukan.")
            return

        target_dir = safe_ensure_dir(os.path.join(BASE_DOWNLOAD_DIR, "Instagram", username))
        print(f"[+] Folder Output: '{target_dir}'")

        print(f"\n[+] Mulai Mengecek dan Mendownload Media...")
        berhasil = 0
        for i, link in enumerate(links):
            print(f"  [{i+1}/{len(links)}] Memproses {link} ...", end=" ", flush=True)
            time.sleep(2)
            sukses, pesan = download_post_media(link, target_dir, cookies_dict)
            if sukses:
                if "SUKSES" in pesan:
                    berhasil += 1
                print(pesan)
            else:
                print(f"Gagal: {pesan}")

        print("\n=== SELESAI ===")
        print(f"Total didownload : {berhasil} postingan.")
        print(f"Tersimpan di     : {target_dir}/")
    finally:
        print("\n[+] Menutup browser...")
        driver.quit()


# ==============================================================================
# 4. MAIN INTERACTIVE CLI
# ==============================================================================

if __name__ == "__main__":
    check_environment()

    while True:
        current_storage = get_base_download_dir()
        print("\n" + "="*60)
        print("  🌟 HYBRID UNIVERSAL & INSTAGRAM DOWNLOADER (TERMUX) 🌟")
        print("="*60)
        print("Mendukung: YouTube, TikTok, Instagram, Twitter/X, FB, dll.")
        print(f"📁 Lokasi Simpan: {current_storage}")
        print("\nPilih Mode:")
        print(" [1] ⚡ Universal Downloader (Tempel link apa saja)")
        print(" [2] 📸 Instagram Profile (Light - 12 Postingan Terbaru)")
        print(" [3] 🚀 Instagram Profile (Full Scrape - Custom Scroll)")
        print(" [0] Keluar")
        print("-" * 60)
        print("💡 Tips: Anda juga bisa LANGSUNG TEMPEL LINK di bawah ini!")

        try:
            pilihan = input("\nMasukkan pilihan (1/2/3/0) atau PASTE LINK: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nKeluar dari program. Sampai jumpa!")
            sys.exit(0)

        if not pilihan:
            continue

        if pilihan == '0':
            print("Keluar dari program. Sampai jumpa!")
            break

        # Shortcut: Jika pengguna langsung menempel link
        if pilihan.startswith(('http://', 'https://', 'www.')) or any(d in pilihan for d in ['.com', '.be', '.net', '.it', '.watch']):
            handle_universal_download(pilihan)
            input("\nTekan Enter untuk kembali ke menu utama...")
            continue

        if pilihan == '1':
            link = input("\nMasukkan Link (YouTube / TikTok / IG / Twitter / FB / dll): ").strip()
            if link:
                handle_universal_download(link)
            else:
                print("Link kosong, dibatalkan.")
            input("\nTekan Enter untuk kembali ke menu utama...")

        elif pilihan in ['2', '3']:
            target_input = input("\nMasukkan Username ATAU Link Profil Instagram: ").strip()
            username = get_username_from_url(target_input)
            if not username:
                print("Input kosong atau tidak valid, dibatalkan.")
                continue

            if pilihan == '2':
                print(f"[+] Mode Ringan: Mengambil postingan awal dari @{username} tanpa scroll.")
                run_instagram_profile_scraper(username, max_scroll=0)
            else:
                run_instagram_profile_scraper(username, max_scroll=None)
            input("\nTekan Enter untuk kembali ke menu utama...")

        else:
            print("[!] Pilihan tidak valid! Masukkan 1, 2, 3, 0 atau tempel link langsung.")
