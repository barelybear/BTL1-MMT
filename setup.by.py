import subprocess
import sys
import os

# List of required packages
required_packages = [
    "firebase-admin",
    "bcrypt",
    "supabase",
    "opencv-python",
    "Pillow",
    "numpy",
    "sounddevice",
    "scipy",
    "requests",
]

optional_ffmpeg = True

def create_venv(venv_name="env"):
    if not os.path.exists(venv_name):
        print(f"📦 Creating virtual environment '{venv_name}'...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_name])
    else:
        print(f"✅ Virtual environment '{venv_name}' already exists.")

def install_packages(venv_name="env"):
    pip_path = os.path.join(venv_name, "Scripts", "pip.exe" if os.name == "nt" else "bin/pip")
    python_path = os.path.join(venv_name, "Scripts", "python.exe" if os.name == "nt" else "bin/python")

    print(f"📦 Using pip at: {pip_path}")

    # Try upgrading pip (optional, wrapped in try block)
    try:
        print("🔄 Upgrading pip...")
        subprocess.check_call([pip_path, "install", "--upgrade", "pip"])
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Warning: Failed to upgrade pip. Skipping. Error:\n{e}")

    # Install required packages
    print("📦 Installing required packages...")
    for pkg in required_packages:
        try:
            print(f"📥 Installing {pkg}...")
            subprocess.check_call([pip_path, "install", pkg])
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {pkg}. Skipping. Error:\n{e}")

    if optional_ffmpeg:
        try:
            print("📥 Installing ffmpeg-python...")
            subprocess.check_call([pip_path, "install", "ffmpeg-python"])
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install ffmpeg-python. Skipping. Error:\n{e}")

    print("\n✅ All dependencies attempted.")
    print(f"👉 To activate your environment:\n    {venv_name}\\Scripts\\activate.bat  (Windows)\n    source {venv_name}/bin/activate     (Mac/Linux)")
    print(f"\n👉 Then run your app using:\n    {python_path} your_script.py")

if __name__ == "__main__":
    venv_name = "env"
    try:
        create_venv(venv_name)
        install_packages(venv_name)
    except Exception as e:
        print(f"❌ Setup failed: {e}")
