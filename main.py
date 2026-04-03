import time
import os
import sys
import requests
import json
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# --- SELENIUM IMPORTS ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

def get_username_from_url(url):
    url = url.strip()
    
    # Jika pengguna tidak sengaja menempelkan teks lain beserta link (contoh: "Memproses https://...")
    if ' ' in url:
        url = url.split(' ')[-1] # Ambil bagian terakhir yang kemungkinan besar adalah link-nya
        
    if 'instagram.com' in url:
        path = urlparse(url if url.startswith('http') else 'https://' + url).path
        parts = [p for p in path.split('/') if p]
        if parts:
            return parts[0]
    return url

def setup_driver():
    """Mengatur dan menjalankan Chromium dalam mode headless di Termux."""
    print("[+] Menyiapkan Browser (Chromium)... ini mungkin memakan waktu sebentar.")
    chrome_options = Options()
    
    # Pengaturan wajib untuk Termux/Android Headless
    chrome_options.add_argument("--headless=new") # Gunakan mode headless baru
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # User-Agent yang aman
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
    chrome_options.add_argument(f"user-agent={user_agent}")
    
    # Path binary chromium dan chromedriver di Termux
    chrome_options.binary_location = "/data/data/com.termux/files/usr/bin/chromium-browser"
    service = Service("/data/data/com.termux/files/usr/bin/chromedriver")
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except WebDriverException as e:
        print(f"\n[!] GAGAL MENJALANKAN BROWSER: {e}")
        print("Pastikan chromium-browser terinstal dengan benar (pkg install chromium).")
        return None

def load_cookies(file_path='cookies.json'):
    """Membaca cookies dari JSON atau meminta input jika file tidak ada."""
    data = None
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"[!] Error: Format JSON di {file_path} tidak valid!")
            return None
    else:
        print(f"\n[!] File {file_path} tidak ditemukan.")
        print("[+] Silakan PASTE (tempel) JSON Cookies dari ekstensi Chrome di bawah ini.")
        print("[+] (Setelah paste, tekan Enter lalu tekan Ctrl+D untuk selesai):")
        print("-" * 30)
        
        try:
            # Membaca input multi-line sampai EOF (Ctrl+D)
            input_data = sys.stdin.read().strip()
            if not input_data:
                print("[!] Input kosong!")
                return None
                
            data = json.loads(input_data)
            
            # Simpan ke file agar berikutnya tidak perlu input lagi
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"\n[+] Cookies berhasil disimpan ke {file_path}")
            print("-" * 30)
        except Exception as e:
            print(f"\n[!] Gagal memproses input: {e}")
            return None

    if data:
        cookies_dict = {}
        # Jika formatnya adalah List (biasanya hasil export ekstensi Chrome)
        if isinstance(data, list):
            for entry in data:
                if 'name' in entry and 'value' in entry:
                    cookies_dict[entry['name']] = entry['value']
        # Jika formatnya sudah Dictionary
        elif isinstance(data, dict):
            cookies_dict = data
        return cookies_dict
    return None

def inject_cookies(driver, url="https://www.instagram.com/"):
    """Memasukkan cookie ke dalam browser agar login otomatis."""
    print("[+] Membuka Instagram dan memasukkan Cookie login...")
    driver.get(url)
    time.sleep(3) # Tunggu loading halaman awal
    
    cookies_dict = load_cookies()
    if not cookies_dict:
        sys.exit(1)
        
    for name, value in cookies_dict.items():
        driver.add_cookie({'name': name, 'value': str(value), 'domain': '.instagram.com'})
        
    print("[+] Cookie berhasil dimasukkan. Merefresh halaman...")
    driver.refresh()
    time.sleep(4) # Tunggu halaman termuat ulang dalam kondisi login

def scrape_post_links(driver, username, max_scrolls=5):
    """Membuka profil dan men-scroll untuk mengumpulkan link postingan."""
    profile_url = f"https://www.instagram.com/{username}/"
    print(f"\n[+] Membuka profil: {profile_url}")
    driver.get(profile_url)
    time.sleep(5) # Tunggu loading profil
    
    post_links = set()
    
    # Ekstrak pertama kali (tanpa scroll, dapat ~12 postingan awal)
    hrefs = driver.execute_script("return Array.from(document.querySelectorAll('a')).map(a => a.href);")
    for href in hrefs:
        if href and ('/p/' in href or '/reel/' in href):
            post_links.add(href)
            
    print(f"[+] Ditemukan {len(post_links)} link di halaman awal.")
    
    if max_scrolls > 0:
        print(f"[+] Mulai mengumpulkan link tambahan (Maksimal Scroll: {max_scrolls}x)...")
        for i in range(max_scrolls):
            # Scroll ke bawah
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3) # Jeda antar scroll agar aman dari deteksi bot
            
            # Ekstrak lagi
            hrefs = driver.execute_script("return Array.from(document.querySelectorAll('a')).map(a => a.href);")
            for href in hrefs:
                if href and ('/p/' in href or '/reel/' in href):
                    post_links.add(href)
                    
            print(f"    - Scroll ke-{i+1}: Ditemukan total {len(post_links)} link sejauh ini.")
        
    return list(post_links)

import instaloader

def download_post_media(url, username, cookies_dict):
    """Mendownload semua media dari satu link postingan menggunakan Instaloader."""
    shortcode = get_shortcode_from_url(url)
    
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
            # Ini adalah carousel, buat folder khusus
            carousel_dir = os.path.join(username, shortcode)
            if not os.path.exists(carousel_dir):
                os.makedirs(carousel_dir)
                
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
            # Ini adalah postingan tunggal
            is_video = post.is_video
            media_url = post.video_url if is_video else post.url
            ext = ".mp4" if is_video else ".jpg"
            filename = os.path.join(username, f"{shortcode}_single{ext}")
            
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

def get_shortcode_from_url(url):
    try:
        path = urlparse(url).path
        parts = [p for p in path.strip('/').split('/') if p]
        if 'p' in parts:
            return parts[parts.index('p') + 1]
        elif 'reel' in parts:
            return parts[parts.index('reel') + 1]
        return url
    except Exception:
        return url

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

if __name__ == "__main__":
    print("="*50)
    print("  INSTAGRAM SCRAPER + DOWNLOADER (SELENIUM)  ")
    print("="*50)
    
    print("\nPilih Mode Download:")
    print("1. Download 1 Link Postingan (Manual)")
    print("2. Download 12 Postingan Pertama (Mode Ringan - Tanpa Scroll)")
    print("3. Download Full Profil (Scroll Kustom)")
    
    mode = input("\nMasukkan pilihan (1/2/3): ").strip()
    
    if mode not in ['1', '2', '3']:
        print("Pilihan tidak valid, dibatalkan.")
        sys.exit(0)
        
    # Pastikan cookie tersedia di awal sebelum membuka Selenium atau Instaloader
    cookies_dict = load_cookies()
    if not cookies_dict:
        sys.exit(1)

    if mode == '1':
        # --- MODE 1: DOWNLOAD SINGLE LINK (TIDAK PERLU SELENIUM) ---
        link = input("\nMasukkan Link Postingan (Reel/Post): ").strip()
        if not link:
            print("Link kosong, dibatalkan.")
            sys.exit(0)
            
        print(f"\n[+] Memproses {link} ...")
        # Deteksi username dari link
        username = get_username_from_post(link, cookies_dict)
        print(f"[+] Deteksi Pemilik: @{username}")

        if not os.path.exists(username):
            os.makedirs(username)
            print(f"[+] Folder '{username}' dibuat.")
            
        sukses, pesan = download_post_media(link, username, cookies_dict)
        if sukses:
            print(f"[+] {pesan}")
        else:
            print(f"[-] Gagal: {pesan}")
        print("\n=== SELESAI ===")
        sys.exit(0)

    # --- MODE 2 & 3: DOWNLOAD PROFIL (MENGGUNAKAN SELENIUM) ---
    target_input = input("\nMasukkan Username ATAU Link Profil Target: ")
    username = get_username_from_url(target_input)
    
    if not username:
        print("Input kosong atau tidak valid, dibatalkan.")
        sys.exit(0)
        
    if mode == '2':
        max_scroll = 0
        print(f"[+] Mode Ringan: Mengambil postingan awal dari @{username} tanpa scroll tambahan.")
    else: # mode == '3'
        try:
            max_scroll = int(input("Berapa kali scroll? (Makin banyak makin lama, misal 3 atau 5): ") or "3")
        except ValueError:
            max_scroll = 3
            print("Input tidak valid, menggunakan default: 3 kali scroll.")

    # 1. Buka Browser Headless
    driver = setup_driver()
    if not driver:
        sys.exit(1)
        
    try:
        # 2. Login menggunakan Cookie (menggunakan driver)
        inject_cookies(driver)
        
        # 3. Buka Profil & Scroll kumpulkan Link
        links = scrape_post_links(driver, username, max_scrolls=max_scroll)
        
        print(f"\n[+] Total Link yang akan diproses: {len(links)}")
        if len(links) == 0:
            print("[!] Tidak ada postingan yang ditemukan.")
            sys.exit(0)
            
        # 4. Buat Folder
        if not os.path.exists(username):
            os.makedirs(username)
            print(f"[+] Folder '{username}' dibuat.")
            
        # 5. Download Carousel Terakhir per Link
        print(f"\n[+] Mulai Mengecek dan Mendownload Slide Terakhir...")
        berhasil = 0
        for i, link in enumerate(links):
            print(f"  [{i+1}/{len(links)}] Memproses {link} ...", end=" ", flush=True)
            # Beri jeda agar tidak di-spam
            time.sleep(2)
            
            sukses, pesan = download_post_media(link, username, cookies_dict)
            if sukses:
                if "SUKSES" in pesan:
                    berhasil += 1
                print(pesan)
            else:
                print(f"Gagal: {pesan}")
                
        print("\n=== SELESAI ===")
        print(f"Total didownload: {berhasil} file.")
        print(f"Tersimpan di folder: {username}/")
        
    finally:
        print("\n[+] Menutup browser...")
        driver.quit()
