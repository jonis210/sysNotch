import os
import sys
import subprocess
import re

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
    print("=" * 64)
    print("       🚀 SYNOTCH GITHUB PUSH & SYNC HELPER TOOL 🚀       ")
    print("=" * 64)
    print()

def main():
    print_banner()

    # 1. Check if git is installed
    code, out, _ = run_git(["--version"])
    if code != 0:
        print("[X] ERROR: Git belum terpasang di komputer ini.")
        print("    Silakan unduh dan pasang Git terlebih dahulu di: https://git-scm.com/download/win")
        input("\nTekan Enter untuk keluar...")
        sys.exit(1)
    print(f"[V] Terdeteksi: {out}")

    # 2. Check if .git exists, if not initialize
    if not os.path.exists(".git"):
        print("\n[*] Menginisialisasi repositori Git lokal (branch: main)...")
        run_git(["init", "-b", "main"])
        print("[V] Repositori lokal berhasil dibuat!")
    else:
        # Ensure default branch is main
        run_git(["branch", "-M", "main"])

    # 3. Check remote origin
    code, remote_url, _ = run_git(["remote", "get-url", "origin"])
    if code != 0 or not remote_url:
        print("\n[*] Belum ada URL GitHub yang terhubung.")
        print("    Contoh format: https://github.com/USERNAME/SysNotch.git")
        url_input = input(">>> Masukkan URL Repository GitHub Anda: ").strip()
        while not url_input:
            url_input = input(">>> Masukkan URL Repository GitHub Anda: ").strip()
        run_git(["remote", "add", "origin", url_input])
        remote_url = url_input
        print(f"[V] Remote origin berhasil diatur ke: {remote_url}")
    else:
        print(f"\n[i] Remote GitHub saat ini: {remote_url}")
        change = input("    Apakah ingin mengganti URL ini? (y/N): ").strip().lower()
        if change == "y":
            new_url = input(">>> Masukkan URL Repository GitHub yang baru: ").strip()
            if new_url:
                run_git(["remote", "set-url", "origin", new_url])
                remote_url = new_url
                print(f"[V] URL berhasil diperbarui ke: {remote_url}")

    # 4. Check git status
    _, status_out, _ = run_git(["status", "--porcelain"])
    if not status_out:
        print("\n[i] Tidak ada perubahan file yang perlu di-commit.")
        push_anyway = input("    Apakah Anda ingin tetap mencoba melakukan 'git push'? (Y/n): ").strip().lower()
        if push_anyway == "n":
            print("\nSelesai! Tidak ada yang di-push.")
            input("\nTekan Enter untuk keluar...")
            return

    # 5. Prompt for commit message
    default_msg = "feat: release SysNotch Dynamic Island for Windows"
    print(f"\n[?] Pesan Commit (Tekan Enter untuk default: '{default_msg}'):")
    user_msg = input(">>> Pesan: ").strip()
    commit_msg = user_msg if user_msg else default_msg

    # 6. Stage & Commit
    print("\n[*] Menyiapkan file (git add .)...")
    run_git(["add", "."])

    print(f"[*] Melakukan commit ('{commit_msg}')...")
    run_git(["commit", "-m", commit_msg])

    # 7. Push to GitHub
    print(f"\n[*] Mengunggah kode ke GitHub ({remote_url})...")
    print("    (Catatan: Jika pertama kali, browser mungkin akan membuka halaman login GitHub)")
    
    # Run interactive push so Windows Git Credential Manager can prompt if needed
    p = subprocess.run(["git", "push", "-u", "origin", "main"])
    
    if p.returncode == 0:
        print("\n" + "=" * 64)
        print("  🎉 [BERHASIL] Seluruh file proyek berhasil di-push ke GitHub!")
        print("=" * 64)
        # Convert git URL to web URL
        clean_url = re.sub(r"\.git$", "", remote_url)
        print(f"\nBuka repositori Anda di browser:")
        print(f"👉 {clean_url}")
        print(f"👉 Untuk membuat release: {clean_url}/releases/new")
    else:
        print("\n[!] Push awal ditolak atau terdapat kendala.")
        print("    Kemungkinan repositori di GitHub sudah memiliki file (misal README online).")
        rebase = input("    Apakah Anda ingin mencoba 'git pull --rebase' lalu push lagi? (Y/n): ").strip().lower()
        if rebase != "n":
            print("[*] Melakukan pull --rebase...")
            subprocess.run(["git", "pull", "--rebase", "origin", "main"])
            print("[*] Mencoba push ulang...")
            p2 = subprocess.run(["git", "push", "-u", "origin", "main"])
            if p2.returncode == 0:
                print("\n🎉 [BERHASIL] Push berhasil disinkronkan ke GitHub!")
            else:
                print("\n[X] Masih terdapat kendala sinkronisasi.")
                force = input("    Apakah Anda ingin mem-push secara paksa (force push)? PERINGATAN: ini akan menimpa isi di GitHub (y/N): ").strip().lower()
                if force == "y":
                    subprocess.run(["git", "push", "-u", "origin", "main", "--force"])

    print()
    input("Tekan Enter untuk menutup jendela...")

if __name__ == "__main__":
    main()
