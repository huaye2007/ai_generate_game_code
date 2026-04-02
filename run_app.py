"""exe 入口 - 启动 Streamlit 服务并打开浏览器"""
import sys
import os
import subprocess
import webbrowser
import time
import socket

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def main():
    # 确定 app/main.py 的路径
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后的路径
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    app_path = os.path.join(base_dir, "app", "main.py")
    port = find_free_port()

    # 启动 streamlit
    env = os.environ.copy()
    env["STREAMLIT_SERVER_PORT"] = str(port)
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", app_path,
         "--server.port", str(port),
         "--server.headless", "true",
         "--browser.gatherUsageStats", "false"],
        env=env,
    )

    # 等待服务启动后打开浏览器
    time.sleep(3)
    webbrowser.open(f"http://localhost:{port}")

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()

if __name__ == "__main__":
    main()
