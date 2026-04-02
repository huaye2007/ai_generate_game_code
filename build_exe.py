"""打包脚本 - 使用 PyInstaller 将 Streamlit 应用打包为 exe"""
import subprocess
import sys

subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

subprocess.run([
    sys.executable, "-m", "PyInstaller",
    "--name", "GameAIWorkflow",
    "--onedir",
    "--noconsole",
    "--add-data", "app;app",
    "--hidden-import", "streamlit",
    "--hidden-import", "langchain_openai",
    "--hidden-import", "langchain_core",
    "--collect-all", "streamlit",
    "run_app.py",
], check=True)

print("\n✅ 打包完成！输出在 dist/GameAIWorkflow/ 目录")
