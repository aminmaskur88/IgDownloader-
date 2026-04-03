# 📸 Instagram Scraper & Auto Downloader (Termux Edition)

![Python](https://img.shields.io/badge/Python-3.x-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-WebDriver-43B02A.svg?style=for-the-badge&logo=selenium&logoColor=white)
![Termux](https://img.shields.io/badge/Platform-Termux-black.svg?style=for-the-badge&logo=android&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg?style=for-the-badge)

> [!WARNING]
> ### ⚠️ Peringatan Hukum & Penggunaan
> **Gunakan dengan Bijak!** Mengunduh dan mendistribusikan ulang konten tanpa izin dari pemilik hak cipta dapat melanggar hukum serta kebijakan privasi Instagram.
> 
> Repositori ini dibuat **MURNI UNTUK TUJUAN EDUKASI DAN UJI COBA KECERDASAN BUATAN (AI)**. Pengembang tidak bertanggung jawab atas segala bentuk penyalahgunaan skrip ini atau tindakan hukum yang mungkin timbul akibat penggunaannya. Risiko ditanggung sepenuhnya oleh pengguna.

Sebuah *tool* otomasi kelas profesional berbasis Python yang dirancang khusus untuk berjalan lancar di lingkungan **Termux (Android)**. Skrip ini memadukan kekuatan **Selenium (Headless Chromium)** untuk *scraping* profil dinamis dan **Instaloader** untuk mengekstrak media kualitas tinggi, dilengkapi dengan sistem *Anti-Bot Bypass*.

---

## ✨ Fitur Utama

- **🛡️ Advanced Anti-Bot**: Menginjeksi HTTP Headers khusus (`X-IG-App-ID`, `X-ASBD-ID`, dll) untuk meniru sesi browser Chrome asli, secara efektif melewati blokir `403 Forbidden` dari server Instagram.
- **🍪 Persistent Smart Session**: Tidak perlu login berulang kali. Cukup masukkan file `cookies.json` dari ekstensi browser Anda, dan sesi akan terus tersimpan dengan aman.
- **🗂️ Auto-Directory Organizer**: Hasil unduhan tidak akan berantakan! Skrip otomatis membuat folder berdasarkan **Username**. Untuk postingan *Carousel*, skrip akan membuat sub-folder tambahan berdasarkan *shortcode* postingan.
- **🤖 Termux Optimized**: Dikonfigurasi khusus dengan argumen Chromium *headless* (seperti `--disable-dev-shm-usage`, `--no-sandbox`) agar sangat ringan dan stabil di RAM perangkat Android Anda.
- **🔄 Full Carousel Download**: Mampu mengunduh **SELURUH** *slide* foto dan video dalam satu postingan *carousel* tanpa ada yang terlewat.

---

## 🚀 3 Mode Operasi Cerdas

Skrip ini sangat interaktif dan fleksibel. Saat dijalankan, Anda bisa memilih mode berikut:

| Mode | Nama | Deskripsi | Penggunaan Selenium |
| :--- | :--- | :--- | :---: |
| **1** | **Single Download** | Unduh cepat dari 1 link URL (*Reels/Post*). Skrip mendeteksi pemilik otomatis. | ❌ Tidak |
| **2** | **Light Mode** | Mengambil ~12 postingan terbaru dari profil. Cepat, hemat RAM, tanpa proses *scroll*. | ✅ Ya (Singkat) |
| **3** | **Full Scrape** | Mode mendalam. *Scroll* profil secara kustom untuk mengambil ratusan postingan lama. | ✅ Ya (Penuh) |

---

## 🛠️ Persiapan Lingkungan (Termux)

### 1. Update & Install Dependencies Sistem
Pastikan paket dasar Termux dan *binary* Chromium sudah terinstal:

```bash
pkg update && pkg upgrade -y
pkg install python chromium
```

### 2. Instalasi Pustaka Python
Arahkan terminal ke folder proyek ini, lalu instal dependensi Python:

```bash
cd IgDownloader
pip install -r requirements.txt
```

---

## 🔑 Konfigurasi Wajib: Sesi Cookie

Agar dapat mengakses Instagram (terutama profil privat dan menghindari blokir API), Anda wajib menyiapkan sesi Cookie.

1. Buka Instagram melalui *browser* **Chrome/Kiwi** di HP atau PC Anda.
2. Login ke akun Anda (Sangat disarankan menggunakan akun cadangan/tumbal).
3. Gunakan ekstensi seperti **[EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)**.
4. Klik *Export* untuk menyalin cookie dalam format **JSON** ke *clipboard*.

---

## 💻 Cara Penggunaan

Jalankan skrip utama menggunakan Python:

```bash
python main.py
```

### Inisialisasi Pertama Kali:
Jika file `cookies.json` belum ada, terminal akan meminta Anda untuk menempelkan teks JSON yang sudah disalin:
1. *Paste* JSON Cookie di terminal Termux.
2. Tekan **Enter**.
3. Tekan **Ctrl + D** (Gunakan tombol `Ctrl` di atas *keyboard* Termux, lalu sentuh huruf `D`).
4. Cookie berhasil disimpan! Skrip akan melanjutkan prosesnya.

---

## 📂 Struktur Output Direktori

Tidak perlu merapikan manual, skrip akan menyusun file Anda secara otomatis seperti ini:

```text
IgDownloader/
├── main.py
├── cookies.json                  <-- File rahasia sesi Anda (Diabaikan oleh Git)
├── 📁 username_target_1/
│   ├── ABC123xyz_single.jpg      <-- Postingan 1 foto
│   ├── DEF456abc_single.mp4      <-- Reels / Video
│   └── 📁 DONr_iYie6m/           <-- Folder khusus Postingan Carousel
│       ├── slide_1.jpg
│       ├── slide_2.mp4
│       └── slide_3.jpg
└── 📁 username_target_2/
    └── ...
```

---

## 💡 Troubleshooting & Tips

*   **Error `429 / 403 Forbidden`**: Ini menandakan Instagram membatasi (*rate-limit*) akun/IP Anda karena terlalu banyak *request*. Solusi: Beri jeda waktu, ganti jaringan internet, atau gunakan akun tumbal yang lain.
*   **Aman dari Git Push**: File `cookies.json` sudah didaftarkan ke dalam `.gitignore`. Jangan pernah secara sengaja mengunggah kredensial cookie Anda ke repositori publik!
*   **Browser Crash/Gagal Membuka Profil**: Pastikan penyimpanan internal HP Anda masih lega dan tutup aplikasi latar belakang lain saat menjalankan **Mode 3** untuk menghindari kehabisan RAM.

---

## 🤝 Kontribusi & Kredit

Proyek otomasi ini dikembangkan untuk tujuan eksperimen *Web Scraping* dan pengelolaan data.

**🤖 Special Thanks:**
Dikembangkan dan disempurnakan dengan kolaborasi kecerdasan buatan:
*   **Gemini AI (Google)** - Membantu menangani logika integrasi Selenium-Instaloader, optimasi ekstraksi elemen DOM, penulisan *bypass header*, dan penyusunan dokumentasi profesional ini.

*License: MIT | Author: Amin Maskur*