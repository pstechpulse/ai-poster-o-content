import os
import json
import asyncio
import requests  # Added: Critical for Pexels
from google import genai  # Modern 2026 SDK
import PIL.Image
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips
import edge_tts
from instagrapi import Client  # Added: Critical for Instagram
from googleapiclient.discovery import build  # Added: Critical for YouTube
from googleapiclient.http import MediaFileUpload  # Added: Critical for YouTube
from google.oauth2.credentials import Credentials  # Added: Critical for YouTube

# 1. THE "BTECH HACK" FOR PILLOW
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# 2. INITIALIZE CLIENT
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_daily_topic():
    print("🤖 Researching today's AI tool...")
    prompt = """
    Find a trending AI tool for students. 
    Return ONLY a JSON object:
    {
      "tool_name": "Name",
      "hook": "POV: You have a mid-sem tomorrow and haven't opened the PDF...",
      "script": "Full 40s script...",
      "keywords": ["coding", "exam", "laptop"],
      "title": "Best AI for BTech #shorts #btech",
      "description": "Check the link in bio!"
    }
    """
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(response.text)

async def generate_voice(text):
    print("🎙️ Generating human voice...")
    communicate = edge_tts.Communicate(text, "en-US-AndrewNeural")
    await communicate.save("audio.mp3")

def create_captions(text, duration):
    # 'DejaVu-Sans-Bold' is more reliable on GitHub's Linux runners than Arial
    return TextClip(
        text, 
        fontsize=60, 
        color='yellow', 
        font='DejaVu-Sans-Bold',
        method='caption', 
        size=(800, None)
    ).set_duration(duration).set_position('center')

def build_video(data):
    print("🎬 Assembling video...")
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    clips = []
    
    for kw in data['keywords']:
        try:
            res = requests.get(f"https://api.pexels.com/videos/search?query={kw}&per_page=1", headers=headers).json()
            v_url = res['videos'][0]['video_files'][0]['link']
            with open(f"{kw}.mp4", 'wb') as f: f.write(requests.get(v_url).content)
            clips.append(VideoFileClip(f"{kw}.mp4").subclip(0, 5).resize(height=1920))
        except Exception as e:
            print(f"⚠️ Failed to get clip for {kw}: {e}")

    if not clips:
        raise Exception("No video clips found!")

    bg_video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip("audio.mp3")
    bg_video = bg_video.set_duration(audio.duration)
    
    cap = create_captions(data['hook'], audio.duration)
    final = CompositeVideoClip([bg_video, cap])
    final.set_audio(audio).write_videofile("output.mp4", fps=24, codec="libx264")

def upload_all(data):
    print("📤 Starting uploads...")
    # Instagram
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=f"{data['title']}\n\n{data['description']}")
        print("✅ Posted to Instagram")
    except Exception as e: print(f"❌ IG Error: {e}")

    # YouTube
    try:
        token_data = json.loads(os.getenv("YOUTUBE_TOKEN_JSON"))
        creds = Credentials.from_authorized_user_info(token_data)
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
        print("✅ Posted to YouTube")
    except Exception as e: print(f"❌ YT Error: {e}")

async def run_pipeline():
    try:
        print("🚀 Pipeline Started!")
        data = get_daily_topic()
        await generate_voice(data['script'])
        build_video(data)
        upload_all(data)
        print("🏁 Pipeline Finished Successfully!")
    except Exception as e:
        print(f"💥 CRITICAL PIPELINE ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
