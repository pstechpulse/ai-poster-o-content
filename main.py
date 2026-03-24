import os
import json
import asyncio
import requests
import time
import random
import subprocess
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
    if not (token and chat_id):
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

# --- 2. ASSETS & TIMINGS ---
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

def format_ass_time(seconds):
    """The Mathematical Fix: Pure math to get precise centiseconds for ASS subtitles"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def create_ass_file(word_timings):
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,95,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,5,10,10,10,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    with open("subs.ass", "w", encoding='utf-8') as f:
        f.write(header)
        for item in word_timings:
            start = format_ass_time(item['start'])
            end = format_ass_time(item['end'])
            # \b1 makes it bold, &H0000FFFF makes it Neon Yellow
            f.write(f"Dialogue: 0,0:{start},0:{end},Default,,0,0,0,,{{\\b1}}{item['word'].upper()}\n")

# --- 3. VIDEO BUILDER ---
def build_sota_video(has_ss):
    print("🎬 FFmpeg: Building Final Video...")
    
    # Brainrot Gameplay Link
    gta_url = "https://raw.githubusercontent.com/the-muda-project/video-assets/main/gta_ramp_loop.mp4"
    try:
        with open("bottom.mp4", 'wb') as f:
            f.write(requests.get(gta_url).content)
    except:
        res = requests.get("https://api.pexels.com/videos/search?query=neon+abstract+fast&per_page=1", headers={"Authorization": os.getenv("PEXELS_API_KEY")}).json()
        with open("bottom.mp4", 'wb') as f:
            f.write(requests.get(res['videos'][0]['video_files'][0]['link']).content)

    r_music = requests.get("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")
    with open("music.mp3", 'wb') as f:
        f.write(r_music.content)

    top_input = "-loop 1 -i tool_ss.png" if has_ss else "-i top_fallback.mp4"
    if not has_ss:
        res_t = requests.get("https://api.pexels.com/videos/search?query=matrix+coding&per_page=1", headers={"Authorization": os.getenv("PEXELS_API_KEY")}).json()
        with open("top_fallback.mp4", 'wb') as f:
            f.write(requests.get(res_t['videos'][0]['video_files'][0]['link']).content)

    # Simplified FFmpeg string (No escaping nightmares)
    video_top = "loop=loop=-1:size=1,scale=1080:960" if has_ss else "scale=1080:960,setsar=1"
    cmd = (
        f'ffmpeg -y {top_input} -i bottom.mp4 -i voice.mp3 -i music.mp3 '
        f'-filter_complex "'
        f'[0:v]{video_top}[t]; [1:v]scale=1080:960,setsar=1[b]; [t][b]vstack=inputs=2[v_stack]; '
        f'[v_stack]ass=subs.ass[outv]; '
        f'[2:a]volume=2.0[v_a]; [3:a]volume=0.15[m_a]; [v_a][m_a]amix=inputs=2:duration=first[outa]" '
        f'-map "[outv]" -map "[outa]" -c:v libx264 -t 45 -pix_fmt yuv420p output.mp4'
    )
    subprocess.run(cmd, shell=True)

# --- 4. UPLOADER ---
def upload_all(data):
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=f"{data['title']}\n\n{data['description']}")
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
                    "description": data['description'],
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
        res = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt, config={'response_mime_type': 'application/json'})
        
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
        
        create_ass_file(word_timings)
        build_sota_video(has_ss)
        
        upload_all(data)
        send_telegram(message=f"🏁 SOTA Success: {data['name']}", file_path="output.mp4")
        
    except Exception as e:
        send_telegram(message=f"💥 Crash: {str(e)}")
        print(f"CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
        print(f"❌ IG Error: {e}")

    try:
        creds = Credentials.from_authorized_user_info(json.loads(os.getenv("YOUTUBE_TOKEN_JSON")))
        youtube = build("youtube", "v3", credentials=creds)
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": data['title'],
                    "description": data['description'],
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
        res = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt, config={'response_mime_type': 'application/json'})
        
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
        
        build_sota_video(data, has_ss, word_timings)
        upload_all(data)
        send_telegram(message=f"🏁 SOTA Success: {data['name']}", file_path="output.mp4")
        
    except Exception as e:
        send_telegram(message=f"💥 Crash: {str(e)}")
        print(f"CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
