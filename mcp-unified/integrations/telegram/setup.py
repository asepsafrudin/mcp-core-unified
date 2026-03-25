"""
Setup script for Telegram Bot Integration.

Usage:
    python setup.py
"""

import os
import sys
import subprocess


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")


def install_dependencies():
    """Install required packages."""
    packages = [
        "python-telegram-bot>=20.0",
        "aiohttp>=3.8.0",
    ]
    
    print("\n📦 Installing dependencies...")
    for package in packages:
        print(f"  Installing {package}...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package, "--break-system-packages"],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError:
            # Try without --break-system-packages
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                check=True
            )
    print("✅ Dependencies installed")


def setup_env_file():
    """Setup environment file."""
    env_path = ".env"
    env_example = ".env.example"
    
    if os.path.exists(env_path):
        print("\n⚠️  .env file already exists")
        return
    
    if not os.path.exists(env_example):
        print("\n❌ .env.example not found")
        return
    
    print("\n📝 Setting up .env file...")
    
    # Copy example file
    with open(env_example, "r") as f:
        content = f.read()
    
    with open(env_path, "w") as f:
        f.write(content)
    
    print("✅ .env file created from .env.example")
    print("\n⚠️  IMPORTANT: Edit .env file and add your Telegram Bot Token!")
    print("   Get your token from @BotFather on Telegram")


def print_next_steps():
    """Print next steps."""
    print("\n" + "="*50)
    print("🚀 Setup Complete!")
    print("="*50)
    print("\nNext steps:")
    print("1. Edit .env file and add your TELEGRAM_BOT_TOKEN")
    print("2. (Optional) Add TELEGRAM_ALLOWED_USERS for security")
    print("3. Run the bot server:")
    print("   ./run.sh")
    print("\nGetting Started:")
    print("1. Message @BotFather on Telegram to create a bot")
    print("2. Copy the bot token to .env file")
    print("3. Start the bot and test with /start command")
    print("\nDocumentation:")
    print("   cat README.md")


def main():
    """Main setup function."""
    print("="*50)
    print("🤖 Telegram Bot Integration Setup")
    print("="*50)
    
    check_python_version()
    install_dependencies()
    setup_env_file()
    print_next_steps()


if __name__ == "__main__":
    main()
