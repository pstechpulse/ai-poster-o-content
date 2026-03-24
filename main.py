import os
import json
import asyncio
import requests
import time
import random
import subprocess
import shutil
import re
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
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

# --- 2. THE FAIL-SAFE ENGINE ---
def get_viral_content(prompt):
    try:
        print("🚀 Layer 1: Gemini 3.1 Flash Lite Preview...")
        res = gemini_client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt, config={'response_mime_type': 'application/json'})
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except Exception as e: print(f"⚠️ Layer 1 Failed: {e}")

    try:
        print("🚀 Layer 2: Groq Llama 3.3 70B...")
        chat_completion = groq_client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile", response_format={"type": "json_object"})
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        raise Exception(f"❌ ALL LAYERS FAILED: {e}")

# --- 3. DIRECT DRAWTEXT RENDERER ---
def sanitize_word(w):
    # Strips all punctuation so FFmpeg command never breaks
    clean = re.sub(r'[^\w\s]', '', w)
    return clean.strip().upper()

def build_sota_video(word_timings, mode):
    print(f"🎬 FFmpeg: Building Final Video via DIRECT DRAWTEXT for mode: {mode}...")

    # 1. DOWNLOAD FONT LOCALLY (Only English font needed now)
    font_path = os.path.abspath("font_main.ttf")
    if not os.path.exists(font_path):
        print("📥 Downloading Main Font...")
        with open(font_path, "wb") as f: f.write(requests.get("https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Black.ttf").content)
        
    font_path = font_path.replace('\\', '/')

    # 2. SELECT FROM VAULT
    vault_path = "gameplays"
    if os.path.exists(vault_path) and os.listdir(vault_path):
        all_videos = [f for f in os.listdir(vault_path) if f.endswith(".mp4")]
        if all_videos:
            chosen = random.choice(all_videos)
            print(f"📦 Pulling from Vault: {chosen}")
            shutil.copy(os.path.join(vault_path, chosen), "bg.mp4")
        else:
            raise Exception("VAULT EMPTY: Upload MP4s to 'gameplays' folder!")
    else:
        print("⚠️ Vault not found! Attempting emergency download...")
        gta = requests.get("https://raw.githubusercontent.com/the-muda-project/video-assets/main/gta_ramp_loop.mp4")
        with open("bg.mp4", 'wb') as f: f.write(gta.content)
        
    # 3. Music
    with open("music.mp3", 'wb') as f: f.write(requests.get("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3").content)

    # 4. GENERATE FILTERGRAPH SCRIPT
    drawtexts = []
    for w in word_timings:
        word = sanitize_word(w['word'])
        if not word: continue
        # Dead center, Yellow, Size 130, Black Border width 8
        dt = f"drawtext=fontfile='{font_path}':text='{word}':enable='between(t,{w['start']},{w['end']})':x=(w-text_w)/2:y=(h-text_h)/2:fontsize=130:fontcolor=yellow:borderw=8:bordercolor=black"
        drawtexts.append(dt)
        
    if not drawtexts:
        drawtexts.append(f"drawtext=fontfile='{font_path}':text='':enable='between(t,0,1)':x=0:y=0")
        
    video_chain = f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{','.join(drawtexts)}[outv];\n"
    audio_chain = "[1:a]volume=2.0[v_a]; [2:a]volume=0.15[m_a]; [v_a][m_a]amix=inputs=2:duration=first[outa]"
    
    with open("filter.txt", "w", encoding="utf-8") as f:
        f.write(video_chain + audio_chain)

    # 5. EXECUTE FFMPEG
    random_start = random.randint(0, 45)
    cmd = (
        f'ffmpeg -y -ss {random_start} -stream_loop -1 -i bg.mp4 -i voice.mp3 -i music.mp3 '
        f'-filter_complex_script filter.txt '
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
        clean_tags = [tag.replace("#", "") for tag in data['tags']]
        youtube.videos().insert(
            part="snippet,status",
            body={"snippet": {"title": f"{data['title']} (Comment {data['keyword']})", "description": caption, "categoryId": "27", "tags": clean_tags}, "status": {"privacyStatus": "public"}},
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
        CRITICAL RULES FOR SCRIPT:
        - If mode is hindi, write in English but use heavy Indian college slang (bhai, jugaad, yaar).
        - ALWAYS spell Hindi slang phonetically to avoid English mispronunciation (e.g., use 'neeche' instead of 'niche', 'ussey' instead of 'use', 'kaise' instead of 'kese').
        """
        
        data = get_viral_content(prompt)
        
        # THE FIX: Indian English Voice (Understands Roman Hindi perfectly, doesn't try to force Devanagari)
        voice = "en-IN-PrabhatNeural" if mode == "hindi" else "en-US-BrianNeural"
        
        print("🎙️ Generating Voice...")
        communicate = edge_tts.Communicate(data['script'], voice, rate="+25%", pitch="+10Hz")
        await communicate.save("voice.mp3")
        
        print("🧠 Using Groq Whisper API for Foolproof Timestamps...")
        with open("voice.mp3", "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=("voice.mp3", f.read()),
                model="whisper-large-v3",
                prompt=data['script'], # THIS IS THE CHEAT CODE: Forces Whisper to use the exact spellings from the LLM
                response_format="verbose_json",
                timestamp_granularities=["word"],
                language="en" # Forces A-Z alphabet. No boxes ever again.
            )
        
        word_timings = []
        for w in transcription.words:
            word_text = w['word'] if isinstance(w, dict) else w.word
            start_time = w['start'] if isinstance(w, dict) else w.start
            end_time = w['end'] if isinstance(w, dict) else w.end
            word_timings.append({"word": word_text, "start": start_time, "end": end_time})
        
        build_sota_video(word_timings, mode)
        upload_all(data)
        send_telegram(message=f"🏁 SOTA Success: {data['name']}\nKeyword: {data['keyword']}\nMode: {mode.upper()}", file_path="output.mp4")
    except Exception as e:
        send_telegram(message=f"💥 FINAL CRASH: {str(e)}")
        print(f"CRASH: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
