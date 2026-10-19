const connectButton = document.getElementById("connect");
const connectionCard = document.getElementById("connection-card");
const statusTitle = document.getElementById("status-title");
const status = document.getElementById("status");

function renderStatus(result) {
  const connected = result?.connected === true;
  const onYouTube = result?.youtubeTab === true;
  const contentReady = result?.contentScriptReady === true;
  connectionCard.dataset.state = connected ? "connected" : "disconnected";
  if (!connected) {
    statusTitle.textContent = "Aplikasi belum terhubung";
    status.textContent = result?.message || "Jalankan aplikasi Dynamic Island, lalu coba lagi.";
  } else if (onYouTube && contentReady && result?.recovered === true) {
    statusTitle.textContent = "Tab YouTube tersambung ulang";
    status.textContent = "Deteksi iklan aktif kembali. Tombol Skip muncul saat tombol Lewati tersedia.";
  } else if (onYouTube && contentReady) {
    statusTitle.textContent = "Aplikasi dan YouTube terhubung";
    status.textContent = "Deteksi iklan aktif. Tombol Skip mengikuti tombol Lewati di YouTube.";
  } else if (onYouTube) {
    statusTitle.textContent = "Tab YouTube belum tersambung";
    status.textContent = "Coba muat ulang tab YouTube, lalu periksa koneksi lagi.";
  } else {
    statusTitle.textContent = "Aplikasi terhubung";
    status.textContent = "Buka tab YouTube agar deteksi iklan bisa berjalan.";
  }
  connectButton.textContent = connected ? "Periksa lagi" : "Hubungkan ke aplikasi";
}

async function checkConnection() {
  connectButton.disabled = true;
  connectionCard.dataset.state = "checking";
  statusTitle.textContent = "Memeriksa koneksi…";
  status.textContent = "Menghubungi aplikasi Dynamic Island.";
  try {
    const result = await chrome.runtime.sendMessage({
      type: "check_dynamic_island_connection"
    });
    renderStatus(result);
  } catch (error) {
    console.error("Gagal memeriksa koneksi Dynamic Island:", error);
    renderStatus({
      connected: false,
      message: "Koneksi gagal. Pastikan aplikasi aktif dan izinkan akses lokal jika diminta."
    });
  } finally {
    connectButton.disabled = false;
  }
}

connectButton.addEventListener("click", checkConnection);
checkConnection();
