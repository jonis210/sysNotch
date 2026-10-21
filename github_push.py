import os
import sys
import subprocess
import re

# Whitelist file resmi & mentah penting proyek Dynamic Island
WHITELIST_EXACT = {
    # 1. Source Code Utama Python
    "dynamic.py",
    "drop_vault.py",
    "media_controller.py",
    "lyrics_controller.py",
    "youtube_bridge.py",
    "generate_ico.py",
    "generate_previews.py",
    "github_push.py",

    # 2. Konfigurasi, Build Specs & Dependensi
    "requirements.txt",
    "requirements-build.txt",
    "SysNotch.spec",
    "SysNotch.ico",
    ".gitignore",
    "LICENSE",
    "README.md",

    # 3. Script Batch Otomatis
    "start.bat",
    "install.bat",
    "build.bat",
    "push_to_github.bat",

    # 4. Aset Visual Resmi (Dipakai di README.md & Aplikasi)
    "assets/mascot_robot.png",
    "assets/SysNotch.ico",
    "assets/v2_clean_complete_showcase.png",
    "assets/v2_clean_compact.png",
    "assets/v2_clean_nomedia.png",
    "assets/v2_clean_media.png",
    "assets/v2_clean_lyrics.png",
    "assets/clean_preview_settings.png",
    "assets/volume_speaker_states.png",
    "assets/drop_vault_showcase.png",
    "assets/actual_live_drop_vault_final_suite.png",
}

WHITELIST_PREFIXES = (
    "youtube_extension/",
)


def is_essential_file(path: str) -> bool:
    """Periksa apakah file termasuk file mentah inti proyek."""
    norm = path.replace("\\", "/").strip()
    if norm in WHITELIST_EXACT:
        return True
    for prefix in WHITELIST_PREFIXES:
        if norm.startswith(prefix):
            return True
    return False


def run_git(args, capture=True, check=False):
    """Run git command and return (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(
            ["git"] + args,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if check and p.returncode != 0:
            raise RuntimeError(f"Git command failed: git {' '.join(args)}\n{p.stderr}")
        return p.returncode, p.stdout.strip() if capture else "", p.stderr.strip() if capture else ""
    except Exception as e:
        return 1, "", str(e)


def print_banner():
    print("=" * 70)
    print("       🚀 SYSNOTCH GITHUB PUSH, AUDIT & CLEANER TOOL 🚀       ")
    print("      (Audit Repositori & Sinkronisasi File Mentah Inti)       ")
    print("=" * 70)
    print()


def audit_and_clean_tracked_files():
    """Deteksi file di git yang bukan file mentah inti, lalu hapus jika disetujui."""
    code, out, _ = run_git(["ls-files"])
    if code != 0 or not out:
        return

    tracked_files = [f.strip() for f in out.splitlines() if f.strip()]
    extraneous_files = [f for f in tracked_files if not is_essential_file(f)]

    if not extraneous_files:
        print("[V] Audit Repositori: 100% Bersih. Hanya file mentah inti yang terlacak di Git.")
        return

    print("=" * 70)
    print(f"[🔍] AUDIT REPOSITORI: Ditemukan {len(extraneous_files)} file yang tidak berkesinambungan:")
    print("    (Screenshot debug sementara, mockup lama, atau artefak testing)")
    print("-" * 70)
    for f in extraneous_files[:15]:
        print(f"    - {f}")
    if len(extraneous_files) > 15:
        print(f"    ... dan {len(extraneous_files) - 15} file lainnya.")
    print("-" * 70)

    confirm = input(">>> Apakah ingin menghapus file-file ini dari repositori GitHub? (Y/n): ").strip().lower()
    if confirm != "n":
        print("\n[*] Menghapus file non-esensial dari Git...")
        # Jalankan git rm
        chunk_size = 30
        for i in range(0, len(extraneous_files), chunk_size):
            chunk = extraneous_files[i:i + chunk_size]
            run_git(["rm", "-f", "--ignore-unmatch"] + chunk)

        commit_msg = "chore: purge non-essential debug screenshots and test artifacts"
        attribution = "Co-Authored-By: Claude Code <noreply@anthropic.com>"
        run_git(["commit", "-m", commit_msg, "-m", attribution])
        print(f"[V] Berhasil menghapus {len(extraneous_files)} file non-esensial dan membuat commit pembersihan!")
    else:
        print("[i] Pembersihan dilewati sesuai pilihan pengguna.")
    print()


def main():
    print_banner()

    # 1. Verifikasi instalasi Git
    code, out, _ = run_git(["--version"])
    if code != 0:
        print("[X] ERROR: Git belum terpasang di komputer ini.")
        print("    Silakan unduh Git di: https://git-scm.com/download/win")
        input("\nTekan Enter untuk keluar...")
        sys.exit(1)
    print(f"[V] Terdeteksi: {out}")

    # 2. Inisialisasi repositori jika belum ada
    if not os.path.exists(".git"):
        print("\n[*] Menginisialisasi repositori Git lokal (branch: main)...")
        run_git(["init", "-b", "main"])
        print("[V] Repositori lokal berhasil dibuat!")
    else:
        run_git(["branch", "-M", "main"])

    # 3. Konfigurasi identitas Git
    _, user_name, _ = run_git(["config", "user.name"])
    _, user_email, _ = run_git(["config", "user.email"])
    if not user_name:
        run_git(["config", "user.name", "jonis210"])
        print("[V] Mengatur git user.name ke: jonis210")
    if not user_email:
        run_git(["config", "user.email", "jonis210@users.noreply.github.com"])
        print("[V] Mengatur git user.email ke: jonis210@users.noreply.github.com")

    # 4. Verifikasi remote GitHub
    code, remote_url, _ = run_git(["remote", "get-url", "origin"])
    if code != 0 or not remote_url:
        print("\n[*] Belum ada URL GitHub yang terhubung.")
        print("    Contoh: https://github.com/jonis210/sysNotch.git")
        url_input = input(">>> Masukkan URL Repository GitHub: ").strip()
        while not url_input:
            url_input = input(">>> Masukkan URL Repository GitHub: ").strip()
        run_git(["remote", "add", "origin", url_input])
        remote_url = url_input
        print(f"[V] Remote origin diatur ke: {remote_url}")
    else:
        print(f"\n[i] Remote GitHub saat ini: {remote_url}")
        change = input("    Apakah ingin mengganti URL ini? (y/N): ").strip().lower()
        if change == "y":
            new_url = input(">>> Masukkan URL Repository GitHub yang baru: ").strip()
            if new_url:
                run_git(["remote", "set-url", "origin", new_url])
                remote_url = new_url
                print(f"[V] URL berhasil diperbarui ke: {remote_url}")

    # 5. AUDIT & CLEANUP FILE NON-ESENSIAL DARI REPOSITORI
    audit_and_clean_tracked_files()

    # 6. Cek perubahan file mentah penting yang belum di-commit
    _, status_out, _ = run_git(["status", "--porcelain"])
    changed_lines = [l.strip() for l in status_out.splitlines() if l.strip()] if status_out else []

    if changed_lines:
        print("\n[*] Menyiapkan pembaruan file mentah penting...")
        # Stage modifikasi file ter-track
        run_git(["add", "-u"])

        # Stage file whitelist yang baru jika ada
        for target in WHITELIST_EXACT:
            if os.path.exists(target):
                run_git(["add", target])

        _, staged_diff, _ = run_git(["diff", "--name-only", "--cached"])
        staged_files = [f.strip() for f in staged_diff.splitlines() if f.strip()]

        if staged_files:
            print(f"[V] {len(staged_files)} file mentah siap di-commit:")
            for f in staged_files:
                print(f"    + {f}")

            default_msg = "docs(readme): update showcase visual images, assets, and project guide"
            if any(f.endswith(".py") for f in staged_files):
                default_msg = "feat(vault): add Drop Vault shelf, LAN QR Teleport, and indicator morphing"

            print(f"\n[?] Pesan Commit (Tekan Enter untuk default: '{default_msg}'):")
            user_msg = input(">>> Pesan: ").strip()
            commit_msg = user_msg if user_msg else default_msg

            attribution = "Co-Authored-By: Claude Code <noreply@anthropic.com>"
            print(f"[*] Melakukan commit...")
            run_git(["commit", "-m", commit_msg, "-m", attribution])
            print("[V] Commit berhasil dibuat!")
        else:
            print("[i] Tidak ada perubahan baru pada file mentah inti.")
    else:
        print("\n[i] Semua file mentah inti dalam keadaan bersih.")

    # 7. Cek commit yang belum ter-push
    _, unpushed_out, _ = run_git(["log", "origin/main..HEAD", "--oneline"])
    unpushed_count = len(unpushed_out.splitlines()) if unpushed_out else 0
    if unpushed_count > 0:
        print(f"\n[i] Ditemukan {unpushed_count} commit lokal yang siap di-push ke GitHub:")
        for line in unpushed_out.splitlines()[:5]:
            print(f"    • {line}")
        if unpushed_count > 5:
            print(f"    ... dan {unpushed_count - 5} commit lainnya.")

    # 8. Push ke GitHub
    print(f"\n[*] Bersiap mengunggah (push) ke GitHub ({remote_url})...")
    p = subprocess.run(["git", "push", "-u", "origin", "main"])

    if p.returncode == 0:
        print("\n" + "=" * 70)
        print("  🎉 [BERHASIL] Repositori GitHub telah bersih dan mutakhir!")
        print("=" * 70)
        clean_url = re.sub(r"\.git$", "", remote_url)
        print(f"\nBuka repositori Anda di browser:")
        print(f"👉 {clean_url}")
    else:
        print("\n[!] Push ditolak atau remote GitHub memiliki commit baru.")
        rebase = input("    Coba 'git pull --rebase' lalu push lagi? (Y/n): ").strip().lower()
        if rebase != "n":
            print("[*] Melakukan pull --rebase...")
            subprocess.run(["git", "pull", "--rebase", "origin", "main"])
            print("[*] Mencoba push ulang...")
            p2 = subprocess.run(["git", "push", "-u", "origin", "main"])
            if p2.returncode == 0:
                print("\n🎉 [BERHASIL] Push berhasil disinkronkan ke GitHub!")
            else:
                print("\n[X] Masih terdapat kendala sinkronisasi.")
                force = input("    Lakukan force push? (PERINGATAN: menimpa remote) (y/N): ").strip().lower()
                if force == "y":
                    subprocess.run(["git", "push", "-u", "origin", "main", "--force"])

    print()
    input("Tekan Enter untuk menutup jendela...")


if __name__ == "__main__":
    main()
