"""
VR File Copier - Terminal script
Copies new files from a PC folder to VR headsets via ADB.
- Checks which files already exist before copying
- Beeps when done
- Waits for disconnect before accepting next headset
"""

import subprocess
import os
import sys
import time
import winsound

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

ADB = os.path.join(SCRIPT_DIR, "scrcpy-win64-v3.3.1-quest3-fix", "adb.exe")
if not os.path.exists(ADB):
    ADB = "adb"  # fallback to PATH


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def run_adb(*args, device_id=None, timeout=60):
    cmd = [ADB]
    if device_id:
        cmd += ["-s", device_id]
    cmd += list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)
        return r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    except Exception as e:
        return "", str(e), 1


def get_connected_device():
    stdout, _, rc = run_adb("devices", timeout=10)
    if rc != 0:
        return None
    for line in stdout.strip().split('\n')[1:]:
        parts = line.strip().split('\t')
        if len(parts) == 2 and parts[1] == "device":
            return parts[0].strip()
    return None


def shell_quote(path):
    """Wrap a remote path in single quotes, escaping any single quotes inside."""
    return "'" + path.replace("'", "'\\''") + "'"


def get_headset_files(device_id, remote_folder):
    stdout, _, rc = run_adb("shell", f"find {shell_quote(remote_folder)} -type f",
                            device_id=device_id, timeout=120)
    files = set()
    if rc == 0:
        prefix = remote_folder.rstrip('/') + '/'
        for line in stdout.strip().split('\n'):
            line = line.strip()
            if line.startswith(prefix):
                rel = line[len(prefix):]
                if rel:
                    files.add(rel.replace('\\', '/'))
    return files


def get_pc_files(pc_folder):
    files = []
    for root, dirs, filenames in os.walk(pc_folder):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel = os.path.relpath(full_path, pc_folder).replace('\\', '/')
            files.append((full_path, rel))
    return files


def is_quest3(device_id):
    stdout, _, _ = run_adb("shell", "getprop", "ro.product.model", device_id=device_id, timeout=10)
    return "quest 3" in stdout.strip().lower()


def media_scan(device_id, remote_path):
    """Trigger MediaStore scan — required on Quest 3 (Android 12) after adb push."""
    uri = "file://" + remote_path.replace(" ", "%20")
    run_adb("shell", "am", "broadcast",
            "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d", uri,
            device_id=device_id, timeout=15)


def beep_done():
    for freq, dur in [(880, 150), (1100, 150), (1320, 300)]:
        winsound.Beep(freq, dur)
        time.sleep(0.05)


def beep_error():
    for freq, dur in [(600, 200), (400, 200), (300, 400)]:
        winsound.Beep(freq, dur)
        time.sleep(0.05)


def log_free_space(device_id):
    stdout, _, rc = run_adb("shell", "df /sdcard/", device_id=device_id, timeout=10)
    if rc != 0:
        return
    for line in stdout.strip().split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 4:
            try:
                free_mb  = int(parts[3]) // 1024
                used_pct = 100 - int(parts[3]) * 100 // int(parts[1])
                free_str = f"{free_mb/1024:.1f} GB" if free_mb >= 1024 else f"{free_mb} MB"
                log(f"  Free space: {free_str} ({used_pct}% used)")
            except ValueError:
                pass
            break


def ts():
    return time.strftime("%H:%M:%S")


def log(msg, prefix=""):
    print(f"[{ts()}] {prefix}{msg}")


# ─────────────────────────────────────────────
# Headset folder browser
# ─────────────────────────────────────────────

def pick_headset_folder(device_id):
    print()
    log("Listing folders on headset /sdcard/ ...")
    stdout, _, rc = run_adb("shell", "ls", "/sdcard/", device_id=device_id, timeout=15)
    if rc != 0:
        log("Could not list /sdcard/ — type path manually.")
    else:
        entries = [e.strip() for e in stdout.strip().split('\n') if e.strip()]
        print()
        for i, e in enumerate(entries):
            print(f"  [{i+1:2}] /sdcard/{e}/")
        print()
        choice = input("Enter number to select, or press Enter to type a custom path: ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(entries):
                return f"/sdcard/{entries[idx]}/"

    custom = input("Type headset destination path (e.g. /sdcard/Movies/): ").strip()
    if not custom.endswith('/'):
        custom += '/'
    return custom


# ─────────────────────────────────────────────
# Copy logic
# ─────────────────────────────────────────────

def copy_new_files(device_id, pc_folder, remote_folder, shutdown_on_success=False, quest3=False):
    remote_folder = remote_folder.rstrip('/')

    # 1. Scan PC
    log(f"Scanning PC: {pc_folder}")
    pc_files = get_pc_files(pc_folder)
    log(f"  {len(pc_files)} file(s) found on PC.")

    if not pc_files:
        log("  Source folder is empty — nothing to copy.")
        beep_done()
        return

    # 2. Scan headset
    log(f"Scanning headset: {remote_folder}/")
    headset_files = get_headset_files(device_id, remote_folder)
    log(f"  {len(headset_files)} file(s) already on headset.")

    # 3. New files only
    new_files = [(lp, rel) for lp, rel in pc_files if rel not in headset_files]

    if not new_files:
        log("  All files already exist on headset — nothing to copy.")
        beep_done()
        return

    # 4. List new files
    log_free_space(device_id)
    print()
    log(f"  ── {len(new_files)} new file(s) to copy ──")
    for _, rel in new_files:
        print(f"         + {rel}")
    print(f"         {'─'*40}")

    # 5. Copy
    success = 0
    failed  = 0
    for i, (local_path, rel_path) in enumerate(new_files, 1):
        # Check still connected
        if not get_connected_device():
            log("  Headset disconnected during copy!", prefix="! ")
            break

        remote_path = f"{remote_folder}/{rel_path}"
        remote_dir  = remote_path.rsplit('/', 1)[0]

        run_adb("shell", f"mkdir -p {shell_quote(remote_dir)}", device_id=device_id)

        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        push_timeout = max(120, 60 + int(size_mb))
        print(f"[{ts()}]   [{i}/{len(new_files)}] Copying: {rel_path}", end="  ", flush=True)
        stdout, stderr, rc = run_adb("push", local_path, remote_path, device_id=device_id, timeout=push_timeout)

        if rc == 0:
            print("✓")
            if quest3:
                media_scan(device_id, remote_path)
            success += 1
        else:
            err = (stderr or stdout).strip().split('\n')[0]
            print(f"✗  {err}")
            failed += 1

    # 6. Summary
    print()
    summary = f"Done — {success} copied"
    if failed:
        summary += f", {failed} failed"
    log(summary)
    log_free_space(device_id)
    if not failed:
        beep_done()
        if shutdown_on_success:
            log("  Shutting down headset...")
            run_adb("shell", "reboot -p", device_id=device_id, timeout=15)
    else:
        beep_error()


# ─────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────

UDC_MOVIES     = "/sdcard/Android/data/udc.lenovo.com.udclient/files/Movies"
UPTALE_EXPERIENCES = "/sdcard/Android/data/com.Uptale.Player/files/Experiences"

def cleanup_udc_movies(device_id):
    stdout, _, rc = run_adb("shell", f"ls {shell_quote(UDC_MOVIES)}", device_id=device_id, timeout=10)
    if rc != 0:
        return
    log("  UDC Movies folder found — clearing app data ...")
    stdout, _, rc = run_adb("shell", "pm clear udc.lenovo.com.udclient", device_id=device_id, timeout=60)
    if rc == 0 and "Success" in stdout:
        log("  Folder Lenovo UDC Deleted (old auto-downloaded videos) ✓")
    else:
        log(f"  Failed to clear UDC app data: {stdout.strip()}")


def cleanup_uptale(device_id):
    stdout, _, rc = run_adb("shell", f"ls {shell_quote(UPTALE_EXPERIENCES)}", device_id=device_id, timeout=10)
    if rc != 0:
        return
    log("  Uptale Experiences folder found — clearing app data ...")
    stdout, _, rc = run_adb("shell", "pm clear com.Uptale.Player", device_id=device_id, timeout=60)
    if rc == 0 and "Success" in stdout:
        log("  Folder Uptale Deleted (old experiences) ✓")
    else:
        log(f"  Failed to clear Uptale app data: {stdout.strip()}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def copy_single_file(device_id, local_file, remote_folder, quest3=False):
    remote_folder = remote_folder.rstrip('/')
    filename = os.path.basename(local_file)
    remote_path = f"{remote_folder}/{filename}"

    run_adb("shell", f"mkdir -p {shell_quote(remote_folder)}", device_id=device_id)

    size_mb = os.path.getsize(local_file) / (1024 * 1024)
    push_timeout = max(120, 60 + int(size_mb))
    print(f"[{ts()}]   Copying: {filename}", end="  ", flush=True)
    stdout, stderr, rc = run_adb("push", local_file, remote_path, device_id=device_id, timeout=push_timeout)

    if rc == 0:
        print("✓")
        if quest3:
            media_scan(device_id, remote_path)
        log(f"Done — {filename} copied to {remote_folder}/")
    else:
        err = (stderr or stdout).strip().split('\n')[0]
        print(f"✗  {err}")
        log("Copy failed.")
    beep_done()


def main():
    print("=" * 60)
    print("  VR File Copier")
    print(f"  ADB: {ADB}")
    print("=" * 60)
    print()

    # ── Mode selection ──
    print("  [1] Sync folder  (copy all new files from a folder)")
    print("  [2] Single file  (copy one file quickly)")
    print()
    mode = input("Select mode [1/2]: ").strip()
    print()

    single_file_mode = mode == "2"

    if single_file_mode:
        local_file = input("File to copy: ").strip().strip('"')
        if not local_file or not os.path.isfile(local_file):
            print("Invalid file path. Exiting.")
            sys.exit(1)
    else:
        pc_folder = input("PC source folder path: ").strip().strip('"')
        if not pc_folder or not os.path.isdir(pc_folder):
            print("Invalid folder. Exiting.")
            sys.exit(1)

    # ── Cleanup options ──
    delete_udc          = input("Delete Lenovo UDC auto-downloaded videos on each headset? [y/N]: ").strip().lower() == 'y'
    delete_uptale       = input("Delete Uptale experiences on each headset? [y/N]: ").strip().lower() == 'y'
    shutdown_on_success = input("Shutdown headset automatically on success? [y/N]: ").strip().lower() == 'y'
    print()

    # ── Headset destination — ask once when first headset connects ──
    print()
    print("Headset destination path will be configured when first headset connects.")
    remote_folder = None

    current_device = None

    print()
    log("Waiting for headset to connect via USB...")
    print("  (Press Ctrl+C to quit)")
    print()

    try:
        while True:
            device = get_connected_device()

            if device and current_device is None:
                # ── New headset connected ──
                print()
                quest3 = is_quest3(device)
                headset_label = f"{device} (Quest 3)" if quest3 else device
                log(f"══ Headset connected: {headset_label} ══")

                if remote_folder is None:
                    remote_folder = pick_headset_folder(device)
                    print()
                    log(f"Destination set to: {remote_folder}")

                if delete_udc:
                    if quest3:
                        log("  Skipping UDC cleanup — not applicable on Quest 3.")
                    else:
                        cleanup_udc_movies(device)
                if delete_uptale:
                    if quest3:
                        log("  Skipping Uptale cleanup — not applicable on Quest 3.")
                    else:
                        cleanup_uptale(device)

                if single_file_mode:
                    copy_single_file(device, local_file, remote_folder, quest3=quest3)
                else:
                    copy_new_files(device, pc_folder, remote_folder, shutdown_on_success, quest3=quest3)

                current_device = device
                print()
                log(f"Waiting for headset {device} to disconnect...")

            elif current_device and not device:
                # ── Headset disconnected ──
                log(f"Headset {current_device} disconnected.")
                current_device = None
                print()
                log("Waiting for next headset...")
                print("  (Press Ctrl+C to quit)")
                print()

            time.sleep(2)

    except KeyboardInterrupt:
        print()
        log("Stopped by user.")


if __name__ == "__main__":
    main()
