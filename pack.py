"""打包脚本：把本地 venv 中已安装的包一起打进压缩包，别人解压即用"""
import zipfile
import os
import sys

EXCLUDE_DIRS = {"venv", "__pycache__", ".egg-info", "dist", "build", ".eggs", "vendor"}
EXCLUDE_FILES = {"pack.py", "pack.bat"}
OUTPUT = os.path.join("..", "game-ai-workflow-dist.zip")


def find_site_packages():
    """找到当前环境的 site-packages 路径"""
    for p in sys.path:
        if "site-packages" in p and os.path.isdir(p):
            return p
    print("错误：找不到 site-packages，请在虚拟环境中运行此脚本")
    print("先执行: call venv\\Scripts\\activate.bat")
    sys.exit(1)


def make_zip():
    site_pkg = find_site_packages()
    print(f"site-packages 路径: {site_pkg}")

    count = 0
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1) 打包项目文件
        print("打包项目文件...")
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]
            for f in files:
                if f in EXCLUDE_FILES or f.endswith(".pyc"):
                    continue
                filepath = os.path.join(root, f)
                arcname = os.path.join("game-ai-workflow", filepath[2:])
                zf.write(filepath, arcname)
                count += 1

        # 2) 打包 site-packages 到 vendor/
        print("打包依赖包（来自本地 site-packages）...")
        for root, dirs, files in os.walk(site_pkg):
            # 跳过 pip/setuptools 等打包工具本身
            dirs[:] = [d for d in dirs if not d.startswith(("pip", "setuptools", "pkg_resources", "_distutils"))]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                filepath = os.path.join(root, f)
                relpath = os.path.relpath(filepath, site_pkg)
                arcname = os.path.join("game-ai-workflow", "vendor", relpath)
                zf.write(filepath, arcname)
                count += 1

    size = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"\n打包完成: {os.path.abspath(OUTPUT)}")
    print(f"  文件数: {count}, 大小: {size:.1f} MB")


if __name__ == "__main__":
    make_zip()
