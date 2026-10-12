import time
import os
import sys
import requests
import json
import re
import shutil
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
# CONFIGURATION & STORAGE PATH
# ==============================================================================

def get_base_download_dir():
    """Mendapatkan direktori penyimpanan utama di internal storage Android atau fallback lokal."""
    android_dir = "/storage/emulated/0/Download"
    if os.path.exists(android_dir) and os.access(android_dir, os.W_OK):
        return android_dir
    try:
        os.makedirs(android_dir, exist_ok=True)
        return android_dir
    except Exception:
        local_dir = os.path.abspath("downloads")
        os.makedirs(local_dir, exist_ok=True)
        return local_dir

# Direktori utama hasil download (Folder Download di Internal Storage HP)
BASE_DOWNLOAD_DIR = get_base_download_dir()


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

def download_with_ytdlp(url, output_dir=None, platform_name="Universal"):
    """
    Mendownload media dari ribuan platform (YouTube, TikTok, FB, X, dll) menggunakan yt-dlp.
    Hasil otomatis disimpan di direktori output_dir.
    """
    clean_url = extract_clean_url(url)
    if not output_dir:
        output_dir = os.path.join(BASE_DOWNLOAD_DIR, platform_name)
    os.makedirs(output_dir, exist_ok=True)

    # Deteksi ffmpeg di PATH atau Termux binary
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path and os.path.exists('/data/data/com.termux/files/usr/bin/ffmpeg'):
        ffmpeg_path = '/data/data/com.termux/files/usr/bin/ffmpeg'

    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(title).80B [%(id)s].%(ext)s'),
        'format': 'bestvideo*+bestaudio/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
    }
    if ffmpeg_path:
        ydl_opts['ffmpeg_location'] = ffmpeg_path

    print(f"\n[+] Mengunduh via Universal Engine (yt-dlp)...")
    print(f"[+] Target Platform : {platform_name}")
    print(f"[+] Folder Output   : {output_dir}/")
    print("-" * 55)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            title = info.get('title', 'Unknown Title') if info else 'Unknown'
            print("-" * 55)
            print(f"[✓] SUKSES DIDOWNLOAD : {title}")
            print(f"[✓] Tersimpan di      : {output_dir}/")
            return True, title
    except Exception as e:
        print("-" * 55)
        print(f"[!] Gagal download: {e}")
        return False, str(e)


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
        target_dir = os.path.join(BASE_DOWNLOAD_DIR, "Instagram")
        cookies_dict = load_cookies(prompt_if_missing=False)
        if cookies_dict:
            print("[+] Menggunakan sesi login cookies.json untuk Instagram...")
            try:
                username = get_username_from_post(clean_url, cookies_dict)
            except Exception:
                username = "Instagram_Downloads"
            if not username or username == "Unknown_User":
                username = "Instagram_Downloads"

            user_dir = os.path.join(target_dir, username)
            os.makedirs(user_dir, exist_ok=True)

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

    # Kasus: Semua Platform Lain (YouTube, TikTok, X/Twitter, FB, Pinterest, Reddit, dll)
    target_dir = os.path.join(BASE_DOWNLOAD_DIR, platform)
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

        target_dir = os.path.join(BASE_DOWNLOAD_DIR, "Instagram", username)
        os.makedirs(target_dir, exist_ok=True)
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
    while True:
        print("\n" + "="*60)
        print("  🌟 HYBRID UNIVERSAL & INSTAGRAM DOWNLOADER (TERMUX) 🌟")
        print("="*60)
        print("Mendukung: YouTube, TikTok, Instagram, Twitter/X, FB, dll.")
        print(f"📁 Lokasi Simpan: {BASE_DOWNLOAD_DIR}")
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
