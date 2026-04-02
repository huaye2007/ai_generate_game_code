"""启动脚本"""
import subprocess
import sys

if __name__ == "__main__":
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "app/main.py",
        "--server.port", "8501",
        "--server.headless", "true",
    ])
