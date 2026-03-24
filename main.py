import os
import json
import asyncio
import requests
import time
import random
import subprocess
import shutil
from google import genai
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

# --- 2. ASSETS & TIMINGS ---
def format_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def create_ass_file(word_timings):
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Montserrat Black,110,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,5,10,10,10,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    with open("subs.ass", "w", encoding='utf-8') as f:
        f.write(header)
        for item in word_timings:
            start = format_ass_time(item['start'])
            end = format_ass_time(item['end'])
            word = item['word'].strip().upper()
            f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{word}\n")

# --- 3. VIDEO BUILDER ---
def build_sota_video(word_timings):
    print("🎬 FFmpeg: Building Final Video (Information Gap Mode)...")
    
    # 1. Download Font locally
    os.makedirs("fonts", exist_ok=True)
    if not os.path.exists("fonts/Montserrat-Black.ttf"):
        print("📥 Downloading Custom Font...")
        r_font = requests.get("https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Black.ttf")
        with open("fonts/Montserrat-Black.ttf", "wb") as f:
            f.write(r_font.content)

    create_ass_file(word_timings)

    # 2. Bottom Gameplay (Check for local file first)
    if not os.path.exists("gameplay.mp4"):
        print("📥 Downloading GTA Gameplay Loop...")
        gta_url = "https://raw.githubusercontent.com/the-muda-project/video-assets/main/gta_ramp_loop.mp4"
        try:
            r = requests.get(gta_url)
            r.raise_for_status()
            with open("bottom.mp4", 'wb') as f:
                f.write(r.content)
        except:
            res = requests.get("https://api.pexels.com/videos/search?query=neon+abstract+fast&per_page=1", headers={"Authorization": os.getenv("PEXELS_API_KEY")}).json()
            with open("bottom.mp4", 'wb') as f:
                f.write(requests.get(res['videos'][0]['video_files'][0]['link']).content)
    else:
        shutil.copy("gameplay.mp4", "bottom.mp4")

    # 3. Top Aesthetic B-Roll (Information Gap)
    print("📥 Fetching Aesthetic B-Roll for Top Half...")
    queries = ["cyberpunk typing", "matrix coding", "hacker aesthetic", "late night studying dark"]
    q = random.choice(queries)
    try:
        res_t = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=1", headers={"Authorization": os.getenv("PEXELS_API_KEY")}).json()
        with open("top.mp4", 'wb') as f:
            f.write(requests.get(res_t['videos'][0]['video_files'][0]['link']).content)
    except:
        # Emergency absolute fallback
        res_t = requests.get("https://api.pexels.com/videos/search?query=technology&per_page=1", headers={"Authorization": os.getenv("PEXELS_API_KEY")}).json()
        with open("top.mp4", 'wb') as f:
            f.write(requests.get(res_t['videos'][0]['video_files'][0]['link']).content)

    # 4. Music
    r_music = requests.get("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")
    with open("music.mp3", 'wb') as f:
        f.write(r_music.content)

    # 5. FFmpeg Command
    cmd = (
        f'ffmpeg -y -i top.mp4 -i bottom.mp4 -i voice.mp3 -i music.mp3 '
        f'-filter_complex "'
        f'[0:v]scale=1080:960,setsar=1[t]; [1:v]scale=1080:960,setsar=1[b]; [t][b]vstack=inputs=2[v_stack]; '
        f'[v_stack]ass=subs.ass:fontsdir=fonts[outv]; '
        f'[2:a]volume=2.0[v_a]; [3:a]volume=0.15[m_a]; [v_a][m_a]amix=inputs=2:duration=first[outa]" '
        f'-map "[outv]" -map "[outa]" -c:v libx264 -t 45 -pix_fmt yuv420p output.mp4'
    )
    subprocess.run(cmd, shell=True)

# --- 4. UPLOADER ---
def upload_all(data):
    tags_string = " ".join(data.get('tags', ["#tech", "#ai"]))
    caption = f"{data['title']}\n\n👇 Comment '{data['keyword']}' and I'll send you the link!\n\n{data['description']}\n\n{tags_string}"

    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=caption)
        print("✅ IG Success")
    except Exception as e:
        print(f"❌ IG Error: {e}")

    try:
        creds = Credentials.from_authorized_user_info(json.loads(os.getenv("YOUTUBE_TOKEN_JSON")))
        youtube = build("youtube", "v3", credentials=creds)
        
        clean_tags = [tag.replace("#", "") for tag in data.get('tags', ["tech", "ai"])]
        
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": f"{data['title']} (Comment {data['keyword']})",
                    "description": caption,
                    "categoryId": "27",
                    "tags": clean_tags
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
        
        prompt = f"""
        Mode: {mode}. You are a ruthless, viral tech creator. Pick a highly useful, niche AI tool for BTech/College students.
        
        Write a 40-second script following this framework:
        1. Hook (0-3s): Controversial take or severe pain-point (e.g., "Your professors are praying you don't find this").
        2. Agitation (3-10s): Validate the struggle (e.g., "Reading 50-page PDFs is soul-crushing").
        3. Reveal (10-15s): Drop the AI tool name like a cheat code.
        4. Application (15-30s): Explain the exact transformation and time saved.
        5. The Comment Bait CTA (30-40s): NEVER say "link in bio". Say exactly: "Comment the word [SECRET_WORD] and I'll send you the direct link, and drop a follow."
        
        CRITICAL RULES:
        - NO corporate jargon.
        - Speak casually. If mode is 'hindi', use heavy Hinglish college slang (bhai, jugaad, etc.).
        
        Return ONLY ONE JSON OBJECT:
        {{
          "name": "Tool Name",
          "url": "Website URL",
          "keyword": "ONE uppercase word for them to comment (e.g., HACK, CHEAT, PASS)",
          "script": "Raw script text...",
          "title": "Viral Clickbait Title #shorts",
          "description": "A 2-sentence SEO description.",
          "tags": ["#techhacks", "#btech", "#studenthacks", "#ai", "#productivity"]
        }}
        """
        
        res = None
        for attempt in range(3):
            try:
                res = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt, config={'response_mime_type': 'application/json'})
                break
            except Exception as api_e:
                if "503" in str(api_e) and attempt < 2:
                    print(f"⚠️ API busy. Retrying... ({attempt+1}/3)")
                    time.sleep(10)
                else: raise api_e

        raw_json = res.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_json)
        if isinstance(data, list): data = data[0]
        
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
        
        build_sota_video(word_timings)
        upload_all(data)
        send_telegram(message=f"🏁 SOTA Success: {data['name']}\nMode: {mode.upper()}", file_path="output.mp4")
        
    except Exception as e:
        send_telegram(message=f"💥 Crash: {str(e)}")
        print(f"CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
