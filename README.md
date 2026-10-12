# 🌟 Universal & Instagram Hybrid Downloader (Termux Edition)

![Python](https://img.shields.io/badge/Python-3.x-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![yt-dlp](https://img.shields.io/badge/Engine-yt--dlp-red.svg?style=for-the-badge&logo=youtube&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-WebDriver-43B02A.svg?style=for-the-badge&logo=selenium&logoColor=white)
![Termux](https://img.shields.io/badge/Platform-Termux-black.svg?style=for-the-badge&logo=android&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg?style=for-the-badge)

> [!WARNING]
> ### ⚠️ Peringatan Hukum & Penggunaan
> **Gunakan dengan Bijak!** Mengunduh dan mendistribusikan ulang konten tanpa izin dari pemilik hak cipta dapat melanggar hukum serta kebijakan privasi masing-masing platform.
> 
> Repositori ini dibuat **MURNI UNTUK TUJUAN EDUKASI DAN UJI COBA KECERDASAN BUATAN (AI)**. Pengembang tidak bertanggung jawab atas segala bentuk penyalahgunaan skrip ini atau tindakan hukum yang mungkin timbul akibat penggunaannya. Risiko ditanggung sepenuhnya oleh pengguna.

Tool otomasi *all-in-one* berbasis Python yang dirancang khusus untuk berjalan super lancar di lingkungan **Termux (Android)**. Kini hadir dengan arsitektur **Hybrid**: memadukan mesin **yt-dlp** (untuk unduh kilat dari 1.000+ situs web seperti YouTube, TikTok tanpa watermark, Facebook, Twitter/X, Pinterest, Reddit, dll) dan **Selenium + Instaloader** untuk *mass scrape* profil & carousel Instagram!

---

## ✨ Fitur Utama

- **⚡ Universal Auto-Detection**: Tempel link apa saja (YouTube, TikTok, Twitter/X, Facebook, Reddit, Pinterest, Threads, dll), sistem otomatis mendeteksi platform dan langsung mengunduh dengan kualitas terbaik.
- **🎬 Selector Kualitas YouTube (1080p FHD)**: Khusus unduhan YouTube (Video & Shorts), tersedia menu pilihan resolusi: **1080p (Full HD)**, **720p (HD)**, **480p**, **360p**, **Kualitas Maksimal**, hingga **Ekstrak Audio MP3**.
- **📱 100% Siap Post Sosmed (H.264 + AAC MP4)**: Mengutamakan dan otomatis mengonversi video ke codec **H.264 (AVC)** dan audio **AAC** dengan flag `+faststart` agar dijamin **bisa diposting di Instagram (Reel/Story/Feed), dikirim di WhatsApp status/chat, TikTok, FB, dll tanpa error!**
- **🚀 Fast & Light (Tanpa Browser)**: Unduhan media tunggal menggunakan engine `yt-dlp` tanpa perlu menyalakan Chromium Selenium, sehingga sangat cepat, hemat kuota RAM, dan anti-lag di Android.
- **🎥 High Quality + FFmpeg Support**: Otomatis menggabungkan video & audio resolusi tinggi (1080p, 2K, 4K) ke format `.mp4` kompatibel galeri Android.
- **📸 Instagram Deep Scraper**: Tetap mendukung *scraping* feed massal Instagram dengan Selenium Headless Chromium dan download seluruh slide foto/video (*Carousel*) via Instaloader.
- **🍪 Smart Cookie Session**: Cookie hanya diminta jika Anda menggunakan fitur Instagram yang membutuhkannya (misal scrape profil atau post privat). Untuk unduh YouTube, TikTok, dll, bisa langsung jalan tanpa login!
- **🗂️ Auto-Directory Organizer**: Output unduhan otomatis dikelompokkan rapi ke dalam folder masing-masing platform (misal `/storage/emulated/0/Download/YouTube/`, `TikTok/`, `Instagram/`).

---

## 🚀 Pilihan Mode Interaktif

Saat dijalankan, Anda bisa memilih mode atau **bisa langsung menempelkan tautan (paste link)** di menu awal:

| Pilihan | Nama | Keterangan | Kebutuhan Selenium / Cookie |
| :---: | :--- | :--- | :---: |
| **Direct Paste** | **Smart Auto-Detect** | Langsung tempel URL apa saja di prompt menu utama. | Otomatis sesuai platform |
| **1** | **Universal Downloader** | Unduh video/audio dari YouTube, TikTok, FB, X, IG, dll. | ❌ Tidak perlu |
| **2** | **IG Profile (Light)** | Mengambil ~12 postingan terbaru dari profil Instagram. | ✅ Ya (Headless Chromium) |
| **3** | **IG Profile (Full)** | Scrape mendalam dengan custom scroll halaman profil Instagram. | ✅ Ya (Headless Chromium) |

---

## 🛠️ Persiapan Lingkungan (Termux)

### 1. Update & Install Dependencies Sistem
Pastikan paket dasar Termux, FFmpeg, dan Chromium sudah terpasang:

```bash
pkg update && pkg upgrade -y
pkg install python ffmpeg chromium -y
```

### 2. Instalasi Pustaka Python
Arahkan terminal ke folder proyek ini, lalu instal dependensi Python:

```bash
pip install -r requirements.txt
```

---

## 💻 Cara Penggunaan

Jalankan skrip utama:

```bash
python main.py
```

### Contoh Penggunaan:
1. **Unduh Video TikTok / YouTube / Twitter**: Cukup jalankan `python main.py`, lalu tempel link video. File akan otomatis tersimpan di folder `downloads/TikTok/` atau `downloads/YouTube/`.
2. **Unduh Profil Instagram**: Masukkan pilihan `2` atau `3`, lalu ketik username target. Skrip akan memproses postingan target.

---

## 📂 Struktur Output Direktori

File unduhan tersimpan langsung di folder **Download** memori internal HP Anda (`/storage/emulated/0/Download`) sehingga langsung muncul di Galeri / File Manager Android:

```text
/storage/emulated/0/Download/
├── YouTube/                  <-- Unduhan video YouTube / Shorts
├── TikTok/                   <-- Unduhan video TikTok tanpa watermark
├── Twitter_X/                <-- Unduhan media Twitter/X
├── Facebook/                 <-- Unduhan Facebook video/reels
└── Instagram/                <-- Unduhan Instagram
    ├── username_target_1/    <-- Hasil scrape postingan & carousel per akun
    │   └── shortcode_carousel/
    └── username_target_2/
```

---

## 💡 Troubleshooting & Tips

*   **Error `Permission denied` (`/storage/emulated/0/...`)**:
    Termux di HP tersebut belum diberi izin mengakses memori penyimpanan Android.
    👉 **Solusi**: Jalankan perintah `termux-setup-storage` di terminal Termux, lalu pilih **Izinkan** (*Allow*) pada kotak dialog Android. Skrip juga otomatis mengalihkan penyimpanan ke folder lokal `downloads/` jika izin belum aktif agar tidak *crash*.
*   **Error `ffmpeg is not installed` (Gagal Download YouTube / 1080p)**:
    Untuk menggabungkan video dan audio resolusi tinggi (1080p Full HD) serta mengekstrak MP3, paket FFmpeg wajib terpasang di Termux.
    👉 **Solusi**: Jalankan perintah `pkg install ffmpeg -y`.
*   **Error `429 / 403 Forbidden` di Instagram**:
    Gunakan sesi login dengan menyiapkan file `cookies.json` dari browser Chrome/Kiwi (ekstensi EditThisCookie).
*   **Keluar dari Program**:
    Ketik `0` di menu utama atau tekan tombol `Ctrl + C`.

---

*License: MIT | Author: Amin Maskur*