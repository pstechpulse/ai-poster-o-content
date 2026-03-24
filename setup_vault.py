import os
import subprocess
import yt_dlp

def automate_vault():
    print("🚀 Initiating Vault Setup Protocol (Shorts Edition)...")
    
    if not os.path.exists("gameplays"):
        os.makedirs("gameplays")
        print("📁 Created 'gameplays' directory.")

    # These are specific YouTube Shorts. They are already < 60 seconds.
    # No FFmpeg slicing required!
    videos = [
        "https://www.youtube.com/shorts/j2Or_YQYHQ0", # Minecraft Parkour
        "https://www.youtube.com/shorts/tMpQPKlrvMM", # Minecraft Parkour 2
        "https://www.youtube.com/shorts/V2rPYLtY75k", # Minecraft Parkour 3
        "https://www.youtube.com/shorts/OF8tsiH2b-M", # Minecraft Build Fast
        "https://www.youtube.com/shorts/ZVHy0Ifl1DU"  # Minecraft Run
    ]
    
    # Simple, rock-solid download settings. No ranges, no slicing.
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/mp4', 
        'outtmpl': 'gameplays/brainrot_%(autonumber)s.mp4',
        'quiet': False,
        'no_warnings': True
    }
    
    print("\n⬇️ Downloading pre-sized YouTube Shorts (Lightning Fast)...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(videos)
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return

    print("\n⬆️ Uploading the vault to GitHub...")
    try:
        subprocess.run(["git", "add", "gameplays/"], check=True)
        subprocess.run(["git", "commit", "-m", "Auto-populated local gameplay vault with Shorts"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ STEP 1 COMPLETE. Your GitHub repository is fully loaded.")
    except Exception as e:
        print("⚠️ Git push failed. You might need to push manually using 'git push'.")

if __name__ == "__main__":
    automate_vault()