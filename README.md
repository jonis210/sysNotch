# 🏝️ SysNotch — Dynamic Island for Windows

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" />
  <img src="https://img.shields.io/badge/RAM%20Usage-%3C%2010%20MB-brightgreen?style=for-the-badge&logo=speedtest&logoColor=white" alt="RAM Usage" />
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/UI-PyQt6%20%2B%20DirectComposition-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6" />
  <img src="https://img.shields.io/badge/Executable-Single--File%20Standalone-orange?style=for-the-badge&logo=windows-terminal&logoColor=white" alt="Standalone" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License" />
</p>

<p align="center">
  <strong>A fluid, ultra-lightweight Dynamic Island experience meticulously engineered for Windows 10 & 11.</strong><br>
  Featuring native Windows Media Transport integration, real-time synchronized karaoke lyrics, interactive cyberpunk mecha mascot, browser-bridged YouTube ad skipping, and deep Win32 working-set RAM optimization.
</p>

<p align="center">
  <img src="assets/preview_lyrics.png" alt="SysNotch Dynamic Island with Synced Lyrics" width="760" />
</p>

---

## 🌟 Highlights

<table>
  <tr>
    <td width="50%">
      <h3>🏝️ Liquid Squircle Geometry</h3>
      Apple-grade curved bezier notch that smoothly transitions between a minimalist, distraction-free top camera notch and an expanded multi-panel media dashboard with physics-based spring easing.
    </td>
    <td width="50%">
      <h3>🤖 Cyberpunk Mecha Mascot</h3>
      Procedural, mathematically-rendered skull android mascot with quintic smoothstep gaze tracking, organic floating bob, raised-cosine mechanical blinks, and dual-optic neon chromatic aberration.
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>⚡ Ultra-Low RAM Footprint (< 10 MB)</h3>
      Aggressive memory optimization utilizing direct Win32 API <code>SetProcessWorkingSetSize</code> trimming, bounded LRU pixmap caching, and zero-allocation painting loops — sipping less memory than Notepad.
    </td>
    <td width="50%">
      <h3>📜 Synced Karaoke Lyrics</h3>
      Integrated lyrics drawer powered by LRCLIB API. Real-time automatic line synchronization, smooth scrolling focus, and expandable side-car drawer with zero lag.
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🎵 Deep Windows Media Control</h3>
      Direct Windows Runtime (WinRT) <code>GlobalSystemMediaTransportControls</code> bridge. Supports Spotify, Apple Music, Tidal, Chrome, Edge, Brave, YouTube, and local players.
    </td>
    <td width="50%">
      <h3>⏭️ One-Click YouTube Skip Ad</h3>
      Native lightweight local bridge connecting to Chromium browser extension for zero-delay detection and click-triggering of YouTube's Skip Ad button.
    </td>
  </tr>
</table>

---

## 📸 Visual Showcase

<div align="center">

### 1. Minimalist Camera Pill (Collapsed Mode)
*Living center clock with system network, battery, and CPU load monitors.*  
<br/>
<img src="assets/preview_compact.png" alt="SysNotch Compact Notch Mode" width="280" />
<br/><br/>

### 2. Media Dashboard (Expanded Hub)
*Full playback controls, dynamic audio visualizer, seekbar, and volume controls.*  
<br/>
<img src="assets/preview_media.png" alt="SysNotch Media Hub Mode" width="520" />
<br/><br/>

### 3. Synchronized Karaoke Lyrics (Side-Drawer)
*Zero-cut 2-line word wrapping, buttery smooth scroll, and Spotify-style typography.*  
<br/>
<img src="assets/preview_lyrics.png" alt="SysNotch 2-Line Synced Lyrics" width="760" />
<br/>

</div>

---

## 🚀 Features in Detail

### 1. 🎛️ Dynamic Multi-Tab Dashboard
- **Page 1 — Media Hub:** Track title, artist, album thumbnail with ambient back-glow, interactive seek scrubber, audio frequency equalizer, and master volume controls.
- **Page 2, 3, 4 — Extensible Modules:** Dynamic self-adjusting tab canvas height that matches content proportions seamlessly.
- **Worm-Dot Page Indicator:** Elastic pagination dot that fluidly elongates into a pill during tab transitions before snapping into the target indicator.

### 2. 🤖 Interactive Mascot Companion

<p align="center">
  <img src="assets/mascot_robot.png" alt="Cyberpunk Robot Mascot Head" width="160" /><br>
  <em>Vector-rendered Cyberpunk Mecha Skull Android with smooth gaze and mechanical blinks.</em>
</p>

- 100% Vector QPainter drawing (zero bitmap loss at any scale or DPI).
- Dual-optic cybernetic eyes: Electric Cyan (`#00F5FF`) on the left, Neon Magenta (`#FF007F`) on the right.
- High-definition ambient outer neon shield with dynamic breathing pulse.
- Multi-resolution Windows application icon (`.ico`) compiled directly into the binary.

### 3. 🎨 Visual Personalization
- Live interactive gradient appearance customizer.
- Preset cyber-palette or custom RGB hex input.
- Real-time canvas preview with silky spring reveal animations.

### 4. 🥷 Stealth & Efficiency Profile
- Runs under the stealth process name `SysNotch.exe` in Windows Task Manager.
- Clean system tray integration with instant hide/show toggles.
- Background media threads throttle down to idle sleep cycles when no media is actively playing.

---

## 📥 Quick Start

### Option 1: Standalone Single Executable (No Python Required)
1. Download the latest **[`SysNotch.exe`](SysNotch.exe)** or **[`SysNotch_Standalone.zip`](SysNotch_Standalone.zip)** from the repository.
2. Double-click `SysNotch.exe`.
3. Play music on Spotify, YouTube, or your favorite media player — the island will immediately wake up and track your playback!

> [!TIP]
> `SysNotch.exe` is completely portable. You can move it to your Desktop, USB drive, or startup folder (`shell:startup`) without any extra dependencies.

---

### Option 2: Running from Source

#### Prerequisites
- Windows 10 (Version 1809 or higher) / Windows 11
- Python 3.11 or newer

#### Installation & Launch
```bash
# Clone the repository
git clone https://github.com/your-username/sysnotch-dynamic-island.git
cd sysnotch-dynamic-island

# Install virtual environment and dependencies
install.bat

# Launch the application
start.bat
```

Or run manually via Python:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python dynamic.py
```

---

## 🧩 YouTube Skip Ad Integration (Optional)

To enable the hardware-accelerated **Skip Ad** button for YouTube videos:

1. Launch `SysNotch.exe`.
2. Open your Chromium browser (Google Chrome, Microsoft Edge, Brave, Opera).
3. Navigate to `chrome://extensions` (or `edge://extensions`).
4. Enable **Developer Mode** (toggle in top-right corner).
5. Click **Load unpacked** and select the [`youtube_extension`](youtube_extension) folder.
6. Click the extension icon and hit **Hubungkan ke aplikasi**.
7. Reload your YouTube tab — whenever an ad appears with an active skip button, the island will display an interactive skip button!

---

## 🛠️ Compiling Single-File Binary

To build your own standalone `.exe` with embedded icon and resources:

```bash
# Run automated build script
build.bat
```

The script will:
1. Procedurally generate high-definition multi-resolution `SysNotch.ico` (16px to 256px).
2. Invoke PyInstaller in `--onefile --windowed` mode with embedded WinRT hooks and extension assets.
3. Output the finalized standalone binary to both `SysNotch.exe` and `dist\SysNotch.exe`.

---

## 📊 Performance Benchmarks

| Metric | Standard Qt/Electron App | SysNotch |
| :--- | :--- | :--- |
| **Active RAM Working Set** | 80 MB – 250 MB | **~8 MB – 13 MB** |
| **Idle RAM (Trimmed)** | ~60 MB | **~1.5 MB – 5.9 MB** |
| **CPU Usage (Idle)** | 1.0% – 3.0% | **< 0.1%** |
| **Startup Time** | ~2.5s | **< 0.8s** |
| **External Dependencies** | Node, Chromium, DLLs | **Zero (Single .exe)** |

---

## ⌨️ Controls & Shortcuts

| Action | Control |
| :--- | :--- |
| **Expand Notch** | Hover cursor over top notch |
| **Collapse Notch** | Move cursor out of notch area |
| **Play / Pause** | Center media button or Spacebar |
| **Next / Previous Track** | Media arrow buttons |
| **Toggle Lyrics Panel** | Click Lyrics button (`♫`) |
| **Switch Tabs** | Click page dots or side chevrons (`‹` / `›`) |
| **Volume Control** | Click `+` or `-` buttons |
| **Toggle Island Visibility** | Click tray icon or choose from tray menu |
| **Exit Application** | Right-click tray icon ➔ **Keluar** |

---

## 🏗️ Architecture & Tech Stack

```text
┌──────────────────────────────────┐   ┌──────────────────────────────┐   ┌───────────────────────────┐
│ Windows Media Transport (WinRT)  │   │  YouTube Browser Extension   │   │     LRCLIB Public API     │
└────────────────┬─────────────────┘   └──────────────┬───────────────┘   └─────────────┬─────────────┘
                 │ (SMTC Metadata)                    │ (Localhost:47863)               │ (Synced Lyrics)
                 ▼                                    ▼                                 ▼
       [ media_controller.py ]              [ youtube_bridge.py ]             [ lyrics_controller.py ]
                 │                                    │                                 │
                 └────────────────────────────┬───────┴─────────────────────────────────┘
                                              ▼
                        ┌──────────────────────────────────────────┐
                        │     DesktopDynamicIsland Core Engine     │
                        └─────────────────────┬────────────────────┘
                                              │
             ┌────────────────────────┬───────┴────────────────────────┬────────────────────────┐
             ▼                        ▼                                ▼                        ▼
   ┌────────────────────┐   ┌────────────────────┐           ┌────────────────────┐   ┌────────────────────┐
   │  Liquid Squircle   │   │  Cyberpunk Robot   │           │  Audio Visualizer  │   │   Win32 Kernel32   │
   │   Physics Engine   │   │  Mascot Animator   │           │   and Equalizer    │   │   Memory Trimmer   │
   └────────────────────┘   └────────────────────┘           └────────────────────┘   └────────────────────┘
```

- **GUI Framework:** PyQt6 (Direct Composition, native frameless layered window)
- **Windows Media Core:** `winrt-Windows.Media.Control`, `winrt-Windows.Storage.Streams`
- **Process Memory Management:** `ctypes.windll.kernel32.SetProcessWorkingSetSize`
- **Lyrics Provider:** [LRCLIB](https://lrclib.net/)

---

## 🤝 Contributing

Contributions, feature ideas, and pull requests are warmly welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

<p align="center">
  Crafted with ❤️ for a cleaner, more fluid Windows desktop experience.
</p>
