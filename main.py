import os
import json
import asyncio
import requests
import time
import random
import subprocess
import shutil
from google import genai
from groq import Groq
import edge_tts
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# --- 1. SETUP CLIENTS ---
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def send_telegram(message=None, file_path=None):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    try:
        url = f"https://api.telegram.org/bot{token}/"
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                requests.post(url + "sendVideo", data={'chat_id': chat_id, 'caption': message}, files={'video': f})
        else:
            requests.post(url + "sendMessage", data={'chat_id': chat_id, 'text': message})
    except Exception as e: print(f"❌ Telegram Error: {e}")

# --- 2. THE FAIL-SAFE ENGINE ---
def get_viral_content(prompt):
    """Triple-Layer Fallback: Gemini Preview -> Gemini Stable -> Groq Llama"""
    
    # LAYER 1: Gemini 3.1 Flash Preview (High Logic, Low Stability)
    try:
        print("🚀 Layer 1: Trying Gemini 3.1 Flash Preview...")
        res = gemini_client.models.generate_content(
            model='gemini-3.1-flash-lite-preview', 
            contents=prompt, 
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        print(f"⚠️ Layer 1 Failed: {e}")

    # LAYER 2: Gemini 2.0 Flash (Production Stable)
    try:
        print("🚀 Layer 2: Trying Gemini 2.0 Flash Stable...")
        res = gemini_client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt, 
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        print(f"⚠️ Layer 2 Failed: {e}")

    # LAYER 3: Groq Llama 3.3 70B (Max Speed, High Reliability)
    try:
        print("🚀 Layer 3: Trying Groq Llama 3.3 70B...")
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        raise Exception(f"❌ ALL LAYERS FAILED. Final Error: {e}")

# --- 3. ASSET HELPERS ---
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
            start, end = format_ass_time(item['start']), format_ass_time(item['end'])
            f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{item['word'].strip().upper()}\n")

def build_sota_video(word_timings):
    os.makedirs("fonts", exist_ok=True)
    if not os.path.exists("fonts/Montserrat-Black.ttf"):
        with open("fonts/Montserrat-Black.ttf", "wb") as f:
            f.write(requests.get("https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Black.ttf").content)
    create_ass_file(word_timings)
    
    # Gameplay Check
    if os.path.exists("gameplay.mp4"): shutil.copy("gameplay.mp4", "bottom.mp4")
    else:
        gta = requests.get("https://raw.githubusercontent.com/the-muda-project/video-assets/main/gta_ramp_loop.mp4")
        with open("bottom.mp4", 'wb') as f: f.write(gta.content)
        
    # Top B-Roll
    q = random.choice(["cyberpunk typing", "matrix coding", "dark academic study"])
    res_t = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=1", headers={"Authorization": os.getenv("PEXELS_API_KEY")}).json()
    with open("top.mp4", 'wb') as f: f.write(requests.get(res_t['videos'][0]['video_files'][0]['link']).content)
    
    # Music
    with open("music.mp3", 'wb') as f: f.write(requests.get("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3").content)

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
    caption = f"{data['title']}\n\n👇 Comment '{data['keyword']}' for the link!\n\n{data['description']}\n\n{' '.join(data['tags'])}"
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=caption)
        print("✅ IG Success")
    except Exception as e: print(f"❌ IG Error: {e}")

    try:
        creds = Credentials.from_authorized_user_info(json.loads(os.getenv("YOUTUBE_TOKEN_JSON")))
        youtube = build("youtube", "v3", credentials=creds)
        youtube.videos().insert(
            part="snippet,status",
            body={"snippet": {"title": f"{data['title']} (Comment {data['keyword']})", "description": caption, "categoryId": "27", "tags": data['tags']}, "status": {"privacyStatus": "public"}},
            media_body=MediaFileUpload("output.mp4")
        ).execute()
        print("✅ YT Success")
    except Exception as e: print(f"❌ YT Error: {e}")

# --- 5. MAIN ---
async def run_pipeline():
    try:
        mode = random.choice(["hindi", "global"])
        prompt = f"""
        Mode: {mode}. Viral tech creator. Pick niche AI tool for BTech students.
        Framework: Hook(0-3s), Agitation(3-10s), Reveal(10-15s), Application(15-30s), CTA: "Comment [SECRET_WORD]".
        JSON Format: {{"name":"", "url":"", "keyword":"", "script":"", "title":"", "description":"", "tags":[]}}
        No corporate jargon. Slang allowed.
        """
        
        data = get_viral_content(prompt)
        voice = "hi-IN-MadhurNeural" if mode == "hindi" else "en-US-BrianNeural"
        communicate = edge_tts.Communicate(data['script'], voice, rate="+25%", pitch="+10Hz")
        
        word_timings = []
        with open("voice.mp3", "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio": f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    word_timings.append({"word": chunk["text"], "start": chunk["offset"]/10000000, "end": (chunk["offset"]+chunk["duration"])/10000000})
        
        build_sota_video(word_timings)
        upload_all(data)
        send_telegram(message=f"🏁 SOTA Success: {data['name']}\nKeyword: {data['keyword']}", file_path="output.mp4")
    except Exception as e:
        send_telegram(message=f"💥 FINAL CRASH: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
