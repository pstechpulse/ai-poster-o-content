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
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips
import edge_tts
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# 1. COMPATIBILITY & PILLOW FIX
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. HELPER: PRONUNCIATION FIXER
def fix_pronunciation(text):
    replacements = {
        "VS Code": "V S Code", "AI": "A.I.", "API": "A.P.I.", 
        "BTech": "B-Tech", "PDF": "P.D.F.", "UI": "U.I.",
        "GitHub": "Git-Hub", "Python": "Py-thon"
    }
    for word, replacement in replacements.items():
        text = text.replace(word, replacement)
    return text

# 3. HELPER: TELEGRAM NOTIFIER
def send_telegram(message=None, file_path=None):
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
    except Exception as e: print(f"TG Log: {e}")

# 4. ENGINE: CONTENT RESEARCHER
def get_viral_content(mode):
    seed = time.time()
    lang_task = (
        "Write in ROMANIZED HINDI (Hinglish) using BTech slang. Use English letters ONLY."
        if mode == "hindi" else 
        "Write in 100% High-Energy Global English. Professional and punchy."
    )
    prompt = f"""
    Seed: {seed}. Mode: {mode}. {lang_task}
    Research and pick ONE unique AI tool for students/developers. 
    Return ONLY a JSON object:
    {{
      "tool_name": "Name",
      "hook": "ONLY 3 WORDS MAX",
      "full_script": "40s high-energy script using short, punchy sentences.",
      "scenes": [
        {{"text": "First part", "query": "coding laptop"}},
        {{"text": "Second part", "query": "frustrated student"}},
        {{"text": "Third part", "query": "cyberpunk tech"}},
        {{"text": "Fourth part", "query": "fast typing"}},
        {{"text": "Fifth part", "query": "happy success"}}
      ],
      "title": "Best AI Tool #shorts #{mode}",
      "description": "Link in bio! #shorts"
    }}
    """
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(response.text)

# 5. ENGINE: VOICE & TIMINGS
async def generate_voice_data(data, mode):
    voice = "hi-IN-MadhurNeural" if mode == "hindi" else "en-US-AndrewNeural"
    clean_script = fix_pronunciation(data['full_script'])
    communicate = edge_tts.Communicate(clean_script, voice, rate="+15%", pitch="+5Hz")
    
    word_timings = []
    with open("audio.mp3", "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_timings.append({
                    "word": chunk["text"],
                    "start": chunk["offset"] / 10000000,
                    "end": (chunk["offset"] + chunk["duration"]) / 10000000
                })
    
    with open("subs.json", "w") as f: json.dump(word_timings, f)
    return word_timings

# 6. ENGINE: VIDEO BUILDER
def blur(image):
    return cv2.GaussianBlur(image, (51, 51), 0)

def build_video(data, word_timings):
    print("🎬 Building high-retention video...")
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    audio = AudioFileClip("audio.mp3")
    
    scene_clips = []
    duration_per_scene = audio.duration / len(data['scenes'])
    for i, scene in enumerate(data['scenes']):
        try:
            res = requests.get(f"https://api.pexels.com/videos/search?query={scene['query']}&per_page=1&orientation=portrait", headers=headers).json()
            v_url = res['videos'][0]['video_files'][0]['link']
            fname = f"scene_{i}.mp4"
            with open(fname, 'wb') as f: f.write(requests.get(v_url).content)
            clip = VideoFileClip(fname).subclip(0, duration_per_scene).resize(height=1920)
            clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=1080, height=1920)
            scene_clips.append(clip)
        except: continue

    bg_video = concatenate_videoclips(scene_clips, method="compose").set_duration(audio.duration)

    sub_clips = []
    for item in word_timings:
        txt = TextClip(
            item['word'].upper(), fontsize=120, color='yellow', stroke_color='black', 
            stroke_width=4, font='DejaVu-Sans-Bold', method='label'
        ).set_start(item['start']).set_duration(item['end'] - item['start']).set_position('center')
        sub_clips.append(txt)

    final = CompositeVideoClip([bg_video] + sub_clips)
    final.set_audio(audio).write_videofile("output.mp4", fps=24, codec="libx264", audio_codec="aac")

# 7. ENGINE: UPLOADER
def upload_all(data):
    # Instagram
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=f"{data['title']}\n\n{data['description']}")
        print("✅ Posted to Instagram")
    except Exception as e: print(f"❌ IG Error: {e}")

    # YouTube
    try:
        creds = Credentials.from_authorized_user_info(json.loads(os.getenv("YOUTUBE_TOKEN_JSON")))
        youtube = build("youtube", "v3", credentials=creds)
        youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {"title": data['title'], "description": data['description'], "categoryId": "27"},
                "status": {"privacyStatus": "public"}
            },
            media_body=MediaFileUpload("output.mp4")
        ).execute()
        print("✅ Posted to YouTube")
    except Exception as e: print(f"❌ YT Error: {e}")

# 8. MAIN PIPELINE
async def run_pipeline():
    try:
        mode = random.choice(["hindi", "global"])
        print(f"🚀 Running in {mode.upper()} mode...")
        
        data = get_viral_content(mode)
        timings = await generate_voice_data(data, mode)
        build_video(data, timings)
        upload_all(data)
        send_telegram(message=f"✅ {mode.upper()} Video: {data['tool_name']}", file_path="output.mp4")
        print("🏁 FULL SUCCESS!")
    except Exception as e:
        send_telegram(message=f"💥 CRASH: {str(e)[:100]}")
        print(f"💥 CRASH: {e}")
        raise e

if __name__ == "__main__":
    asyncio.run(run_pipeline())
