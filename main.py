import os
import json
import asyncio
import requests
import time
import random
import subprocess
import yt_dlp
from google import genai
from playwright.async_api import async_playwright
import edge_tts
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# --- 1. SETUP ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def send_telegram(message=None, file_path=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/"
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                requests.post(url + "sendVideo", data={'chat_id': chat_id, 'caption': message}, files={'video': f})
        else:
            requests.post(url + "sendMessage", data={'chat_id': chat_id, 'text': message})
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

# --- 2. ASSETS ---
async def get_stealth_screenshot(url):
    print(f"📸 Screenshotting {url}...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(8)
            await page.screenshot(path="tool_ss.png")
            await browser.close()
            return True
    except:
        return False

def download_youtube_gameplay():
    print("🎮 Fetching random gameplay from YouTube...")
    # Removed the dead video and added active ones
    channel_videos = [
        "https://www.youtube.com/watch?v=n_Dv4JMiwK8",
        "https://www.youtube.com/watch?v=2XoH2R-kHpk",
        "https://www.youtube.com/watch?v=3V-1AAYC8bY",
        "https://www.youtube.com/watch?v=8mG8L0U4wS0"
    ]
    random.shuffle(channel_videos)
    
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/mp4',
        'outtmpl': 'bottom.mp4',
        'quiet': True,
        'no_warnings': True
    }
    
    success = False
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for url in channel_videos:
            try:
                print(f"Trying video: {url}")
                ydl.download([url])
                success = True
                break # If it works, break out of the loop
            except Exception as e:
                print(f"⚠️ Failed to download {url}: {e}")

    # The Ultimate Fallback: High-speed neon video from Pexels (No dead links)
    if not success:
        print("⚠️ All YT links failed! Using Pexels fallback...")
        res = requests.get("https://api.pexels.com/videos/search?query=neon+abstract+fast&per_page=1", headers={"Authorization": os.getenv("PEXELS_API_KEY")}).json()
        r_fallback = requests.get(res['videos'][0]['video_files'][0]['link'])
        r_fallback.raise_for_status()
        with open("bottom.mp4", 'wb') as f:
            f.write(r_fallback.content)

# --- 3. VIDEO BUILDER ---
def build_sota_video(has_ss, word_timings):
    print("🎬 FFmpeg: Building Final Video...")
    
    # 1. Download Exact Font (Fixes invisible text on Ubuntu completely)
    font_url = "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Black.ttf"
    with open("font.ttf", "wb") as f:
        f.write(requests.get(font_url).content)

    # 2. Download Gameplay
    download_youtube_gameplay()

    # 3. Download Music
    r_music = requests.get("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")
    with open("music.mp3", 'wb') as f:
        f.write(r_music.content)

    # 4. Top Visual
    top_input = "-loop 1 -i tool_ss.png" if has_ss else "-i top_fallback.mp4"
    if not has_ss:
        res_t = requests.get("https://api.pexels.com/videos/search?query=matrix+coding&per_page=1", headers={"Authorization": os.getenv("PEXELS_API_KEY")}).json()
        with open("top_fallback.mp4", 'wb') as f:
            f.write(requests.get(res_t['videos'][0]['video_files'][0]['link']).content)

    # 5. Generate Text Filters (Bulletproof drawtext engine)
    text_filters = []
    for item in word_timings:
        word = item['word'].replace("'", "").replace('"', '').upper()
        s, e = item['start'], item['end']
        text_filters.append(
            f"drawtext=fontfile=font.ttf:text='{word}':fontcolor=yellow:fontsize=120:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:borderw=6:bordercolor=black:enable='between(t,{s},{e})'"
        )
    full_text_chain = ",".join(text_filters)

    # 6. Final FFmpeg Command
    video_top = "loop=loop=-1:size=1,scale=1080:960" if has_ss else "scale=1080:960,setsar=1"
    cmd = (
        f'ffmpeg -y {top_input} -i bottom.mp4 -i voice.mp3 -i music.mp3 '
        f'-filter_complex "'
        f'[0:v]{video_top}[t]; [1:v]scale=1080:960,setsar=1[b]; [t][b]vstack=inputs=2[v_stack]; '
        f'[v_stack]{full_text_chain}[outv]; '
        f'[2:a]volume=2.0[v_a]; [3:a]volume=0.15[m_a]; [v_a][m_a]amix=inputs=2:duration=first[outa]" '
        f'-map "[outv]" -map "[outa]" -c:v libx264 -t 45 -pix_fmt yuv420p output.mp4'
    )
    subprocess.run(cmd, shell=True)

# --- 4. UPLOADER ---
def upload_all(data):
    final_caption = f"{data['title']}\n\n{data['description']}\n\nGameplay - yt nocopyrightgameplays"
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=final_caption)
        print("✅ IG Success")
    except Exception as e:
        print(f"❌ IG Error: {e}")

    try:
        creds = Credentials.from_authorized_user_info(json.loads(os.getenv("YOUTUBE_TOKEN_JSON")))
        youtube = build("youtube", "v3", credentials=creds)
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": data['title'],
                    "description": final_caption,
                    "categoryId": "27"
                },
                "status": {"privacyStatus": "public"}
            },
            media_body=MediaFileUpload("output.mp4")
        )
        request.execute()
        print("✅ YT Success")
    except Exception as e:
        print(f"❌ YT Error: {e}")

# --- 5. PIPELINE ---
async def run_pipeline():
    try:
        mode = random.choice(["hindi", "global"])
        prompt = f"Mode: {mode}. Pick a unique AI tool. Return ONLY ONE JSON OBJECT (not a list): {{\n  \"name\": \"...\",\n  \"url\": \"...\",\n  \"script\": \"40s script...\",\n  \"title\": \"...\",\n  \"description\": \"...\"\n}}"
        
        res = None
        for attempt in range(3):
            try:
                res = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt, config={'response_mime_type': 'application/json'})
                break
            except Exception as api_e:
                if "503" in str(api_e) and attempt < 2:
                    print(f"⚠️ API busy. Retrying... ({attempt+1}/3)")
                    time.sleep(10)
                else:
                    raise api_e

        raw_json = res.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_json)
        
        if isinstance(data, list):
            data = data[0]
            
        has_ss = await get_stealth_screenshot(data['url'])
        
        voice = "hi-IN-MadhurNeural" if mode == "hindi" else "en-US-BrianNeural"
        communicate = edge_tts.Communicate(data['script'], voice, rate="+25%", pitch="+10Hz")
        
        word_timings = []
        with open("voice.mp3", "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    word_timings.append({
                        "word": chunk["text"],
                        "start": chunk["offset"] / 10000000,
                        "end": (chunk["offset"] + chunk["duration"]) / 10000000
                    })
        
        build_sota_video(has_ss, word_timings)
        upload_all(data)
        send_telegram(message=f"🏁 SOTA Success: {data['name']}", file_path="output.mp4")
        
    except Exception as e:
        send_telegram(message=f"💥 Crash: {str(e)}")
        print(f"CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())