import os
import json
import asyncio
import requests
import time
import random
import cv2
import webvtt
import numpy as np
from google import genai
import PIL.Image
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips
import edge_tts
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# 1. PILLOW & MOVIEPY FIXES
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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
    except Exception as e: print(f"TG Error: {e}")

def get_daily_topic(mode):
    seed = time.time()
    # Instruction for Hinglish vs Global English
    lang_task = (
        "Write in ROMANIZED HINDI (Hinglish) using BTech slang. Do NOT use Devanagari script."
        if mode == "hindi" else 
        "Write in 100% High-Energy Global English. Professional and punchy."
    )
    
    prompt = f"""
    Seed: {seed}. Mode: {mode}. {lang_task}
    Research and pick ONE unique AI tool. Focus on variety (e.g., Video AI, Coding Agents, Research Tools).
    DO NOT repeat common tools like ChatGPT. Pick something fresh.
    
    Return ONLY a JSON object:
    {{
      "tool_name": "Name",
      "hook": "POV: YOUR HOOK HERE",
      "script": "40s high-energy script with short, punchy sentences.",
      "keywords": ["tech", "coding", "productivity"],
      "title": "Best AI for Students #shorts #{mode}",
      "description": "Check link in bio! #shorts #tech"
    }}
    """
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(response.text)

async def generate_voice_and_subs(text, mode):
    voice = "hi-IN-MadhurNeural" if mode == "hindi" else "en-US-BrianNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    submaker = edge_tts.SubMaker()
    
    with open("audio.mp3", "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
                
    # FIX: Generate SRT and convert to VTT for webvtt-py
    with open("subs.srt", "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())
    
    # Convert SRT to VTT
    webvtt.from_srt('subs.srt').save('subs.vtt')

def blur(image):
    return cv2.GaussianBlur(image, (51, 51), 0)

def build_video(data):
    print("🎬 Building high-retention vertical video...")
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    clips = []
    
    for kw in data['keywords']:
        try:
            res = requests.get(f"https://api.pexels.com/videos/search?query={kw}&per_page=1", headers=headers).json()
            v_url = res['videos'][0]['video_files'][0]['link']
            fname = f"{kw}.mp4"
            with open(fname, 'wb') as f: f.write(requests.get(v_url).content)
            
            raw_clip = VideoFileClip(fname).subclip(0, 5)
            # Create 9:16 Portrait from 16:9 Landscape
            bg = raw_clip.resize(height=1920).fl_image(blur).crop(x_center=960, y_center=540, width=1080, height=1920)
            fg = raw_clip.resize(width=1080).set_position("center")
            clips.append(CompositeVideoClip([bg, fg], size=(1080, 1920)))
        except: continue

    bg_video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip("audio.mp3")
    bg_video = bg_video.set_duration(audio.duration)

    # DYNAMIC WORD-BY-WORD SUBTITLES
    sub_clips = []
    vtt = webvtt.read('subs.vtt')
    for entry in vtt:
        start = entry.start_in_seconds
        end = entry.end_in_seconds
        
        # Word-by-word pop-in
        txt = TextClip(entry.text.upper(), fontsize=100, color='yellow', stroke_color='black', 
                       stroke_width=2, font='DejaVu-Sans-Bold', method='caption', size=(1000, None))
        txt = txt.set_start(start).set_duration(end - start).set_position('center')
        sub_clips.append(txt)

    final = CompositeVideoClip([bg_video] + sub_clips)
    final.set_audio(audio).write_videofile("output.mp4", fps=24, codec="libx264")

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

async def run_pipeline():
    try:
        # RANDOM STRATEGY SELECTION
        mode = random.choice(["hindi", "global"])
        print(f"🚀 Running in {mode.upper()} mode...")
        
        data = get_daily_topic(mode)
        await generate_voice_and_subs(data['script'], mode)
        build_video(data)
        upload_all(data)
        send_telegram(message=f"✅ {mode.upper()} Content: {data['tool_name']}", file_path="output.mp4")
    except Exception as e:
        send_telegram(message=f"💥 HEALTH CHECK: Bot Crashed!\nError: {str(e)[:150]}")
        raise e

if __name__ == "__main__":
    asyncio.run(run_pipeline())
