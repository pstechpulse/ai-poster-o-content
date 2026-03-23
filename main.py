import os
import json
import asyncio
import requests
import time
import cv2
import numpy as np
from google import genai  # 2026 SDK
import PIL.Image
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips
import edge_tts
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# 1. PILLOW & COMPATIBILITY FIXES
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# 2. INITIALIZE CLIENT
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
    except Exception as e: print(f"Telegram Log: {e}")

def get_daily_topic():
    seed = time.time()
    prompt = f"""
    Seed: {seed}. You are a Viral Tech Content Strategist for Indian BTech students.
    Research and pick ONE unique AI tool for: Exam prep, Coding, or Placement prep.
    Return ONLY a JSON object:
    {{
      "tool_name": "Name",
      "hook": "Wait... Am I cooked? Mid-sems start tomorrow and I haven't opened the PDF.",
      "script": "40s high-energy script. Use Hinglish and BTech slang (Backlogs, 75% attendance, placements).",
      "keywords": ["coding", "office tech", "studying"],
      "title": "BTech Hack: This AI is a life saver #shorts #btech #engineering",
      "description": "Stop struggling. Tool link in bio! Follow for more hacks. #shorts"
    }}
    """
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(response.text)

async def generate_voice(text):
    communicate = edge_tts.Communicate(text, "en-US-AndrewNeural")
    await communicate.save("audio.mp3")

def blur(image):
    """ Apply Gaussian Blur for the background """
    return cv2.GaussianBlur(image, (51, 51), 0)

def build_video(data):
    print("🎬 Building Vertical 9:16 Video...")
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    clips = []
    
    for kw in data['keywords']:
        try:
            res = requests.get(f"https://api.pexels.com/videos/search?query={kw}&per_page=1", headers=headers).json()
            v_url = res['videos'][0]['video_files'][0]['link']
            fname = f"{kw}.mp4"
            with open(fname, 'wb') as f: f.write(requests.get(v_url).content)
            
            # ORIENTATION FIX LOGIC
            raw_clip = VideoFileClip(fname).subclip(0, 5)
            
            # 1. Create blurred background (scaled to 1920 height)
            bg = raw_clip.resize(height=1920)
            bg = bg.fl_image(blur)
            bg = bg.crop(x_center=bg.w/2, y_center=bg.h/2, width=1080, height=1920)
            
            # 2. Place original landscape clip in the center
            fg = raw_clip.resize(width=1080)
            fg = fg.set_position("center")
            
            combined = CompositeVideoClip([bg, fg], size=(1080, 1920))
            clips.append(combined)
        except: continue

    if not clips: raise Exception("No valid visuals found.")
    
    bg_video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip("audio.mp3")
    bg_video = bg_video.set_duration(audio.duration)
    
    # BIG BOLD CAPTIONS
    cap = TextClip(data['hook'], fontsize=70, color='yellow', font='DejaVu-Sans-Bold',
                   method='caption', size=(900, None)).set_duration(audio.duration).set_position('center')
    
    final = CompositeVideoClip([bg_video, cap])
    final.set_audio(audio).write_videofile("output.mp4", fps=24, codec="libx264", audio_codec="aac")

def upload_all(data):
    # Instagram
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=f"{data['title']}\n\n{data['description']}")
        print("✅ Instagram Success")
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
        print("✅ YouTube Success")
    except Exception as e: print(f"❌ YT Error: {e}")

async def run_pipeline():
    try:
        data = get_daily_topic()
        await generate_voice(data['script'])
        build_video(data)
        upload_all(data)
        send_telegram(message=f"✅ New Content: {data['tool_name']}", file_path="output.mp4")
    except Exception as e:
        send_telegram(message=f"💥 HEALTH CHECK: Bot Crashed!\nError: {str(e)[:150]}")
        raise e

if __name__ == "__main__":
    asyncio.run(run_pipeline())
