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
        print("          L1J Headless - Playable MVP 啟動器")
        print("============================================================")
        print("  [1] 進入遊戲 (真實節奏 1.0x) - [直接按 Enter 預設]")
        print("  [2] 進入遊戲 (快速倍速 2.0x)")
        print("  [3] 進入遊戲 (極速瞬時 Instant)")
        print("  [4] 觀看自動演示 (Demo 模式)")
        print("  [5] 執行全套回歸測試 (13 Tests)")
        print("  [Q] 離開")
        print("============================================================")

        try:
            choice = input("請輸入選項 [1]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n已結束。")
            break

        if choice in ("", "1"):
            print("\n[*] 正在啟動: 真實節奏遊玩 (1.0x)...")
            subprocess.run([sys.executable, "mvp.py", "--speed", "1.0"])
            safe_pause()
        elif choice == "2":
            print("\n[*] 正在啟動: 快速倍速遊玩 (2.0x)...")
            subprocess.run([sys.executable, "mvp.py", "--speed", "2.0"])
            safe_pause()
        elif choice == "3":
            print("\n[*] 正在啟動: 極速瞬時遊玩 (Instant)...")
            subprocess.run([sys.executable, "mvp.py", "--instant"])
            safe_pause()
        elif choice == "4":
            print("\n[*] 正在啟動: 自動演示模式...")
            subprocess.run([sys.executable, "mvp.py", "--demo", "--s007"])
            safe_pause()
        elif choice == "5":
            print("\n[*] 正在執行: 全套回歸測試...")
            subprocess.run([sys.executable, "-m", "unittest", "tests/test_scenarios.py"])
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
