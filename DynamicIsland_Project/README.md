# Dynamic Island for Windows

Aplikasi desktop kecil yang menampilkan pulau di tepi atas layar dan terhubung ke sesi media Windows yang aktif.

## Yang berfungsi

- Menampilkan judul, artis, status putar/jeda, dan posisi lagu/video dari sesi media Windows.
- Mencari lirik tersinkron berdasarkan metadata lagu dan menampilkan baris sebelumnya, sedang dinyanyikan, serta berikutnya.
- Tombol putar/jeda, sebelumnya, dan berikutnya mengirim perintah ke pemutar media yang aktif.
- Ikon volume naik/turun mengatur volume Windows.
- Integrasi ekstensi browser dapat menampilkan dan menekan tombol Skip ad YouTube setelah tombol itu tersedia.
- Bentuk pulau mengembang saat kursor diarahkan ke atasnya.
- Ikon system tray menyediakan tindakan untuk menampilkan/menyembunyikan pulau dan keluar.
- Jika tidak ada sesi media, aplikasi menjelaskan cara memulainya.

Aplikasi membaca Windows System Media Transport Controls. Pemutar yang dipakai harus menerbitkan sesi media ke Windows; dukungan ini berbeda antar aplikasi.

Pencarian lirik memakai [API publik LRCLIB](https://lrclib.net/docs). Nama lagu, artis, album, dan durasi dikirim untuk mencocokkan lirik tersinkron; audio dan kredensial Spotify tidak dikirim. Lirik hanya tampil jika penyedia memiliki versi bertanda waktu dan komputer terhubung ke internet.

Windows mensyaratkan capability `globalMediaControl` untuk membaca sesi sistem. Build PyInstaller `.exe` biasa tidak memiliki package identity atau manifest capability tersebut, sehingga Windows dapat menolak akses. Dalam kondisi itu, pulau akan menampilkan status izin yang ditolak alih-alih macet. Dibutuhkan paket MSIX atau package identity yang mendeklarasikan capability itu agar integrasi media dapat diaktifkan.

## Menjalankan

1. Pasang Python 3.11 atau lebih baru.
2. Klik dua kali `install.bat` untuk membuat lingkungan Python dan memasang dependensi.
3. Klik dua kali `start.bat` untuk menjalankan aplikasi. Ikonnya muncul di system tray.
4. Putar media di aplikasi yang mendukung kontrol media Windows, lalu arahkan kursor ke pulau untuk membuka kontrol.

Jika pulau menampilkan **Perlu izin media Windows**, itu bukan masalah dependensi: Windows menolak akses untuk proses Python/EXE yang belum memiliki package identity.

## Integrasi Skip iklan YouTube

Deteksi iklan YouTube memerlukan ekstensi browser karena sesi media Windows tidak menyebutkan apakah video yang sedang diputar adalah iklan. Untuk mengaktifkannya:

1. Jalankan aplikasi dengan `start.bat`.
2. Klik kanan ikon tray Dynamic Island, lalu pilih **Cara pasang integrasi YouTube**.
3. Di Chrome buka `chrome://extensions`; di Edge buka `edge://extensions`.
4. Aktifkan **Developer mode / Mode pengembang**, pilih **Load unpacked / Muat yang belum dipaketkan**, lalu pilih folder `youtube_extension`.
5. Klik ikon ekstensi dan tekan **Hubungkan ke aplikasi**.
6. Izinkan akses jaringan lokal jika browser memintanya.
7. Muat ulang tab YouTube.

Pulau menampilkan tombol **Skip iklan** hanya saat YouTube mendeteksi iklan dan tombol **Skip ad** aktif. Tombol di pulau menekan tombol skip YouTube saat diklik; iklan tidak dilewati otomatis. Ekstensi hanya berjalan di YouTube dan terhubung ke aplikasi melalui `127.0.0.1`.

Untuk menutup aplikasi, klik kanan ikon Dynamic Island di system tray lalu pilih **Keluar**.

## Membuat aplikasi `.exe`

Jalankan `build.bat`. Hasil build PyInstaller tersedia di `dist\DynamicIsland\DynamicIsland.exe` beserta file pendukungnya.

## Platform

Windows 10 versi 1809 atau lebih baru. Integrasi media menggunakan Windows Media Control dan PyWinRT.
