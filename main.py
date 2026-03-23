import os
import random
import requests
import json
import google.generativeai as genai
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips
import edge_tts
import asyncio

# Setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-3.1-flash-lite')

async def make_human_voice(text):
    # 'en-US-AndrewNeural' or 'en-IN-PrabhatNeural' are great human-like choices
    communicate = edge_tts.Communicate(text, "en-US-AndrewNeural")
    await communicate.save("audio.mp3")

def get_visuals(keywords):
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    clips = []
    for kw in keywords[:3]: # Get 3 different clips for variety
        res = requests.get(f"https://api.pexels.com/videos/search?query={kw}&per_page=1", headers=headers)
        url = res.json()['videos'][0]['video_files'][0]['link']
        r = requests.get(url)
        with open(f"{kw}.mp4", 'wb') as f: f.write(r.content)
        clips.append(VideoFileClip(f"{kw}.mp4").subclip(0, 5).resize(height=1920))
    return clips

def assemble_video(script_data):
    # Logic to overlay Big Bold Captions
    audio = AudioFileClip("audio.mp3")
    backgrounds = get_visuals(script_data['keywords'])
    final_bg = concatenate_videoclips(backgrounds).set_duration(audio.duration)
    
    # Generate pop-in captions
    # (Simplified for briefness: usually uses 'TextClip' with a yellow/white font)
    caption = TextClip(script_data['hook'], fontsize=70, color='yellow', font='Arial-Bold', 
                       method='caption', size=(800, None)).set_duration(3).set_position('center')
    
    final = CompositeVideoClip([final_bg, caption])
    final.set_audio(audio).write_videofile("final_short.mp4", fps=24)

async def main():
    # 1. Gemini writes script + picks search keywords for Pexels
    prompt = "Review Sider AI. Return JSON: {'script': '...', 'hook': 'Short catchy hook', 'keywords': ['coding', 'robot', 'laptop']}"
    raw = model.generate_content(prompt).text
    data = json.loads(raw)
    
    # 2. Generate Human Voice
    await make_human_voice(data['script'])
    
    # 3. Build & Upload
    assemble_video(data)
    # [Upload logic for YT/IG goes here]

if __name__ == "__main__":
    asyncio.run(main())