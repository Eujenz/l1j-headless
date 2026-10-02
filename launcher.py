"""
launcher.py - Interactive Windows Launcher for L1J Headless Playable MVP
Invoked by start_mvp.bat to guarantee 100% UTF-8 compatibility and zero crash on Windows.
"""
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")


def safe_pause(msg: str = "\n[Enter] 返回選單..."):
    try:
        input(msg)
    except (EOFError, KeyboardInterrupt):
        pass


def main():
    # If arguments provided from CLI, forward directly to mvp.py
    if len(sys.argv) > 1:
        cmd = [sys.executable, "mvp.py"] + sys.argv[1:]
        ret = subprocess.run(cmd).returncode
        return ret

    # Interactive Menu
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("============================================================")
        print("          L1J Headless 1.82 — 遊戲啟動器")
        print("============================================================")
        print("  [1] 啟動遊戲 (GUI 啟動畫面) - [直接按 Enter 預設]")
        print("  [2] 啟動遊戲 (GUI 跳過啟動畫面, 直接進入)")
        print("  [3] 執行背景模擬 (Headless Batch, 極速瞬時 Instant)")
        print("  [4] 觀看自動演示 (S007 Demo 模式)")
        print("  [5] 執行全套回歸測試 (All Regression Tests)")
        print("  [Q] 離開")
        print("============================================================")

        try:
            choice = input("請輸入選項 [1]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n已結束。")
            break

        if choice in ("", "1"):
            print("\n[*] 正在啟動: 遊戲選擇畫面...")
            subprocess.run([sys.executable, "mvp.py"])
            safe_pause()
        elif choice == "2":
            print("\n[*] 正在啟動: 遊戲視窗 (直接進入)...")
            subprocess.run([sys.executable, "mvp.py", "--gui", "--speed", "1.0"])
            safe_pause()
        elif choice == "3":
            print("\n[*] 正在啟動: 背景模擬 (Headless Batch Instant)...")
            subprocess.run([sys.executable, "mvp.py", "--headless", "--instant"])
            safe_pause()
        elif choice == "4":
            print("\n[*] 正在啟動: 自動演示模式...")
            subprocess.run([sys.executable, "mvp.py", "--demo", "--s007"])
            safe_pause()
        elif choice == "5":
            print("\n[*] 正在執行: 全套回歸測試...")
            subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
            safe_pause()
        elif choice == "Q":
            print("\n感謝遊玩，再見！")
            break
        else:
            print("無效的選項，請重新輸入。")
            safe_pause("\n[Enter] 重新選擇...")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)
    except Exception as e:
        print(f"\n[錯誤] 執行發生異常: {e}")
        safe_pause("\n請按任意鍵離開...")
        sys.exit(1)
