import os
import json
import asyncio
import requests
import time
import random
import cv2
import numpy as np
from google import genai
import PIL.Image
# MoviePy imports
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips
# Upload & TTS imports
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import edge_tts

# --- 1. COMPATIBILITY FIX ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# Initialize Google GenAI
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- 2. HELPERS ---
def fix_pronunciation(text):
    """Ensures the AI doesn't sound like a 2012 robot."""
    replacements = {
        "VS Code": "V S Code", "AI": "A.I.", "API": "A.P.I.", 
        "BTech": "B-Tech", "PDF": "P.D.F.", "UI": "U.I.",
        "GitHub": "Git-Hub", "Python": "Py-thon"
    }
    for word, replacement in replacements.items():
        text = text.replace(word, replacement)
    return text

def send_telegram(message=None, file_path=None):
    """The Health Check: Reports success or crashes to your phone."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id): return
    try:
        if file_path:
            url = f"https://api.telegram.org/bot{token}/sendVideo?chat_id={chat_id}"
            with open(file_path, 'rb') as f:
                requests.post(url, files={'video': f}, data={'caption': message})
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}"
            requests.get(url)
    except Exception as e:
        print(f"Telegram Error: {e}")

# --- 3. THE ENGINE ---
def get_viral_content(mode):
    """Researches tools and generates a scene-by-scene script."""
    seed_val = str(time.time())
    lang_val = "ROMANIZED HINDI (Hinglish)" if mode == "hindi" else "High-Energy Global English"
    
    # Using standard string to avoid the 'Blue Comment' syntax glitch
    prompt_template = """
    Seed: {SEED}. Mode: {MODE}. You are a Viral Tech Content Creator. 
    Pick a 100% REAL trending AI tool for students. 
    Return ONLY a JSON object:
    {
      "tool_name": "Name",
      "hook": "3 WORD HOOK",
      "full_script": "{LANG} script (40s). Fast paced.",
      "scenes": [
        {"text": "Part 1", "query": "coding student"},
        {"text": "Part 2", "query": "cyberpunk blue tech"},
        {"text": "Part 3", "query": "ai robot"},
        {"text": "Part 4", "query": "typing fast"},
        {"text": "Part 5", "query": "student success"}
      ],
      "title": "This AI is illegal #shorts #tech",
      "description": "Link in bio! #shorts"
    }
    """
    prompt = prompt_template.replace("{SEED}", seed_val).replace("{MODE}", mode).replace("{LANG}", lang_val)
    
    res = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview', 
        contents=prompt, 
        config={'response_mime_type': 'application/json'}
    )
    
    # Clean possible markdown backticks
    clean_json = res.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

async def generate_voice_data(data, mode):
    """Generates audio and word-level timestamps for neon subs."""
    voice = "hi-IN-MadhurNeural" if mode == "hindi" else "en-US-AndrewNeural"
    clean_script = fix_pronunciation(data['full_script'])
    communicate = edge_tts.Communicate(clean_script, voice, rate="+15%", pitch="+5Hz")
    
    word_timings = []
    with open("audio.mp3", "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_timings.append({
                    "word": chunk["text"],
                    "start": chunk["offset"] / 10000000,
                    "end": (chunk["offset"] + chunk["duration"]) / 10000000
                })
    return word_timings

def build_video(data, word_timings):
    """Assembles scene-matched clips and renders neon green subtitles."""
    print("🎬 Constructing Video...")
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    audio = AudioFileClip("audio.mp3")
    
    final_clips = []
    duration_per = audio.duration / len(data['scenes'])
    
    for i, scene in enumerate(data['scenes']):
        try:
            # Orientation=portrait ensures 9:16 content
            res = requests.get(
                f"https://api.pexels.com/videos/search?query={scene['query']}&per_page=1&orientation=portrait", 
                headers=headers
            ).json()
            
            v_url = res['videos'][0]['video_files'][0]['link']
            fname = f"scene_{i}.mp4"
            with open(fname, 'wb') as f:
                f.write(requests.get(v_url).content)
            
            clip = VideoFileClip(fname).subclip(0, duration_per).resize(height=1920)
            clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=1080, height=1920)
            final_clips.append(clip)
        except Exception as e:
            print(f"⚠️ Clip Download Error: {e}")
            continue

    if not final_clips:
        raise Exception("Zero visual clips found.")

    bg_video = concatenate_videoclips(final_clips, method="compose").set_duration(audio.duration)

    # Neon Green Word-by-Word Subtitles
    sub_clips = []
    for item in word_timings:
        txt = TextClip(
            item['word'].upper(), 
            fontsize=120, 
            color='#00FF00', 
            stroke_color='black', 
            stroke_width=5, 
            font='DejaVu-Sans-Bold',
            method='label'
        ).set_start(item['start']).set_duration(item['end'] - item['start']).set_position('center')
        sub_clips.append(txt)

    final = CompositeVideoClip([bg_video] + sub_clips)
    final.set_audio(audio).write_videofile("output.mp4", fps=24, codec="libx264", audio_codec="aac")

def upload_all(data):
    """The Delivery: Sends the content to the algorithms."""
    # IG Upload
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=data['title'] + "\n\n" + data['description'])
        print("✅ Instagram Success")
    except Exception as e: print(f"❌ IG Error: {e}")

    # YT Upload
    try:
        creds_json = json.loads(os.getenv("YOUTUBE_TOKEN_JSON"))
        creds = Credentials.from_authorized_user_info(creds_json)
        youtube = build("youtube", "v3", credentials=creds)
        
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {"title": data['title'], "description": data['description'], "categoryId": "27"},
                "status": {"privacyStatus": "public"}
            },
            media_body=MediaFileUpload("output.mp4")
        )
        request.execute()
        print("✅ YouTube Success")
    except Exception as e: print(f"❌ YT Error: {e}")

# --- 4. RUNNER ---
async def run_pipeline():
    try:
        mode = random.choice(["hindi", "global"])
        print(f"🚀 Running {mode.upper()} mode...")
        
        data = get_viral_content(mode)
        timings = await generate_voice_data(data, mode)
        build_video(data, timings)
        upload_all(data)
        
        # Notify phone
        send_telegram(message=f"✅ {mode.upper()} Done: {data['tool_name']}", file_path="output.mp4")
        print("🏁 PIPELINE FINISHED!")
        
    except Exception as e:
        error_msg = f"💥 CRASH: {str(e)}"
        print(error_msg)
        send_telegram(message=error_msg[:200])
        raise e

if __name__ == "__main__":
    asyncio.run(run_pipeline())
