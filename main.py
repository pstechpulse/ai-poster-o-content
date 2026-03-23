import os
import json
import asyncio
import requests
import time
from google import genai  # 2026 SDK
import PIL.Image
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips
import edge_tts
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# 1. PILLOW & ENVIRONMENT FIXES
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
    # We add a timestamp to the prompt to force variety
    seed = time.time()
    prompt = f"""
    Seed: {seed}. You are a Viral Tech Content Strategist for Indian BTech students.
    Research and pick ONE unique AI tool for: Exam prep, Coding, or Placement prep.
    Examples: Gemini 3 Flash for circuit board analysis, Lovable for full-stack apps, Perplexity for deep research.
    
    Return ONLY a JSON object:
    {{
      "tool_name": "Name",
      "hook": "Wait... Am I cooked? Mid-sems start tomorrow and I haven't opened the PDF.",
      "script": "40s high-energy script. Use Hinglish and BTech slang (Backlogs, 75% attendance, placements).",
      "keywords": ["coding", "exam", "robotics"],
      "title": "BTech Hack: This AI is a life saver #shorts #btech #engineering",
      "description": "Stop struggling. Tool link in bio! Follow @YourHandle for more hacks."
    }}
    """
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(response.text)

async def generate_voice(text):
    # Andrew is the best 'Human-like' voice in 2026 for tech reviews
    communicate = edge_tts.Communicate(text, "en-US-AndrewNeural")
    await communicate.save("audio.mp3")

def build_video(data):
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    clips = []
    # Try to fetch variety. If a keyword fails, it skips to next.
    for kw in data['keywords']:
        try:
            res = requests.get(f"https://api.pexels.com/videos/search?query={kw}&per_page=1", headers=headers).json()
            v_url = res['videos'][0]['video_files'][0]['link']
            with open(f"{kw}.mp4", 'wb') as f: f.write(requests.get(v_url).content)
            clips.append(VideoFileClip(f"{kw}.mp4").subclip(0, 5).resize(height=1920))
        except: continue

    if not clips: raise Exception("Visual Content Fetch Failed")
    
    bg_video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip("audio.mp3")
    bg_video = bg_video.set_duration(audio.duration)
    
    # Bold Captions (DejaVu-Sans-Bold is default on GitHub runners)
    cap = TextClip(data['hook'], fontsize=65, color='yellow', font='DejaVu-Sans-Bold',
                   method='caption', size=(800, None)).set_duration(audio.duration).set_position('center')
    
    final = CompositeVideoClip([bg_video, cap])
    final.set_audio(audio).write_videofile("output.mp4", fps=24, codec="libx264")

def upload_all(data):
    # Instagram Logic
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=f"{data['title']}\n\n{data['description']}")
        print("✅ Instagram Success")
    except Exception as e: print(f"❌ IG Error: {e}")

    # YouTube Logic
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
