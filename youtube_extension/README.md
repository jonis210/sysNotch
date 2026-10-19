# Integrasi YouTube untuk Dynamic Island

Ekstensi ini mendeteksi iklan yang sedang aktif dan tombol **Skip ad** yang sudah tersedia. Ekstensi tidak melewati iklan secara otomatis; klik **Skip iklan** di Dynamic Island untuk mengaktifkan tombol YouTube.

## Pasang di Chrome atau Edge

1. Jalankan Dynamic Island dengan `start.bat` dan biarkan tetap berjalan.
2. Buka `chrome://extensions` di Chrome atau `edge://extensions` di Edge.
3. Aktifkan **Developer mode / Mode pengembang**.
4. Pilih **Load unpacked / Muat yang belum dipaketkan**.
5. Pilih folder `youtube_extension` di proyek ini.
6. Klik ikon ekstensi dan tekan **Hubungkan ke aplikasi**.
7. Izinkan akses jaringan lokal jika browser memintanya.
8. Muat ulang tab YouTube yang sedang memutar video.

Saat iklan terdeteksi, arahkan kursor ke Dynamic Island. Tombol **Skip iklan** akan muncul setelah tombol lewati tersedia di YouTube.

Ekstensi hanya berjalan di `youtube.com` dan berkomunikasi dengan aplikasi melalui `127.0.0.1` selama aplikasi aktif.
