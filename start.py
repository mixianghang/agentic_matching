#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import webbrowser

def main():
    print("=" * 40)
    print("   智能体需求匹配系统 - 一键启动")
    print("=" * 40)
    print()

    # 检查并创建虚拟环境
    venv_dir = "venv"
    if not os.path.exists(venv_dir):
        print("📦 创建 Python 虚拟环境...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])

    # 确定虚拟环境的 Python 和 pip 路径
    if sys.platform == "win32":
        python_path = os.path.join(venv_dir, "Scripts", "python.exe")
        pip_path = os.path.join(venv_dir, "Scripts", "pip.exe")
        uvicorn_path = os.path.join(venv_dir, "Scripts", "uvicorn.exe")
    else:
        python_path = os.path.join(venv_dir, "bin", "python")
        pip_path = os.path.join(venv_dir, "bin", "pip")
        uvicorn_path = os.path.join(venv_dir, "bin", "uvicorn")

    # 安装依赖
    print("📚 检查并安装依赖...")
    subprocess.check_call([pip_path, "install", "-q", "-r", "requirements.txt"])

    # 检查 .env 文件
    if not os.path.exists(".env"):
        print("⚙️ 创建 .env 文件...")
        import shutil
        shutil.copy(".env.example", ".env")
        print()
        print("⚠️ 请编辑 .env 文件并填入你的 OPENAI_API_KEY")
        print()

    print()
    print("🚀 启动服务器...")
    print("📱 访问地址：http://localhost:8000")
    print()
    print("按 Ctrl+C 停止服务器")
    print("=" * 40)
    print()

    # 打开浏览器
    time.sleep(2)
    webbrowser.open("http://localhost:8000")

    # 启动服务器
    subprocess.check_call([
        uvicorn_path,
        "backend.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000"
    ])

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        sys.exit(0)
