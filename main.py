import os, json, asyncio, requests, time, random, subprocess
from google import genai
from playwright.async_api import async_playwright
import edge_tts
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# --- 1. CONFIG & TOOLS ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def send_telegram(message=None, file_path=None):
    """Telegram Debugger: Logs the API response so we can fix it."""
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id): return
    try:
        if file_path:
            url = f"https://api.telegram.org/bot{token}/sendVideo"
            with open(file_path, 'rb') as f:
                r = requests.post(url, data={'chat_id': chat_id, 'caption': message}, files={'video': f})
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            r = requests.post(url, data={'chat_id': chat_id, 'text': message})
        print(f"📡 Telegram Debug: {r.json()}") # This will show in GH Actions logs
    except Exception as e: print(f"❌ Telegram Error: {e}")

async def get_tool_screenshot(url):
    """Captures a real UI shot of the tool."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={'width': 1080, 'height': 1080})
            await page.goto(url, timeout=60000)
            await asyncio.sleep(5)
            await page.screenshot(path="tool_ss.png")
            await browser.close()
    except: pass # Fallback if site blocks bots

# --- 2. CONTENT ENGINE ---
def get_viral_logic(mode):
    seed = time.time()
    lang = "ROMANIZED HINDI (Hinglish) with BTech Slang" if mode == "hindi" else "Global High-Energy English"
    prompt = f"""
    Seed: {seed}. Mode: {mode}. {lang}. 
    Pick a trending AI tool. Return JSON:
    {{
      "name": "Tool Name", "url": "https://tool.com", 
      "hook": "POV: YOU FOUND A GOLDMINE",
      "script": "40s hyper-active script using short sentences.",
      "title": "This tool is a cheat code #shorts #tech",
      "description": "Link in bio! #shorts"
    }}
    """
    res = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt, config={'response_mime_type': 'application/json'})
    return json.loads(res.text)

async def generate_audio(text, mode):
    voice = "hi-IN-MadhurNeural" if mode == "hindi" else "en-US-BrianNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+25%", pitch="+10Hz")
    await communicate.save("voice.mp3")

# --- 3. VIDEO ENGINE (FFMPEG) ---
def build_sota_video(data):
    print("🎬 FFmpeg: Creating Split-Screen Masterpiece...")
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    
    # Download Gameplay (Bottom)
    gp_res = requests.get("https://api.pexels.com/videos/search?query=minecraft+parkour&per_page=1", headers=headers).json()
    with open("bottom.mp4", 'wb') as f: f.write(requests.get(gp_res['videos'][0]['video_files'][0]['link']).content)
    
    # Download Background (Top)
    top_res = requests.get("https://api.pexels.com/videos/search?query=futuristic+tech&per_page=1", headers=headers).json()
    with open("top.mp4", 'wb') as f: f.write(requests.get(top_res['videos'][0]['video_files'][0]['link']).content)

    # Download No-Copyright Music (Lo-fi/Phonk)
    music_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3" # Placeholder, replace with your preferred CDN
    with open("music.mp3", 'wb') as f: f.write(requests.get(music_url).content)

    # THE NUCLEAR FFMPEG FILTER:
    # 1. Scales and stacks videos
    # 2. Burns text with a heavy background box (Stylized)
    # 3. Mixes Voice (Loud) + Music (Quiet)
    cmd = (
        f'ffmpeg -y -i top.mp4 -i bottom.mp4 -i voice.mp3 -i music.mp3 '
        f'-filter_complex "'
        f'[0:v]scale=1080:960,setsar=1[t]; '
        f'[1:v]scale=1080:960,setsar=1[b]; '
        f'[t][b]vstack=inputs=2[v]; '
        f'[v]drawtext=text=\'{data["hook"]}\':fontcolor=white:fontsize=80:x=(w-text_w)/2:y=(h-text_h)/2:'
        f'box=1:boxcolor=black@0.7:boxborderw=20:fontfile=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf[outv]; '
        f'[2:a]volume=1.5[v_a]; [3:a]volume=0.15[m_a]; [v_a][m_a]amix=inputs=2:duration=first[outa]" '
        f'-map "[outv]" -map "[outa]" -c:v libx264 -t 45 -pix_fmt yuv420p output.mp4'
    )
    subprocess.run(cmd, shell=True)

# --- 4. UPLOADER ---
def upload_all(data):
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=f"{data['title']}\n\n{data['description']}")
        print("✅ IG Success")
    except Exception as e: print(f"❌ IG Error: {e}")

    try:
        creds = Credentials.from_authorized_user_info(json.loads(os.getenv("YOUTUBE_TOKEN_JSON")))
        youtube = build("youtube", "v3", credentials=creds)
        youtube.videos().insert(part="snippet,status", body={"snippet": {"title": data['title'], "description": data['description'], "categoryId": "27"}, "status": {"privacyStatus": "public"}}, media_body=MediaFileUpload("output.mp4")).execute()
        print("✅ YT Success")
    except Exception as e: print(f"❌ YT Error: {e}")

# --- 5. RUNNER ---
async def run_pipeline():
    try:
        mode = random.choice(["hindi", "global"])
        data = get_viral_logic(mode)
        await get_tool_screenshot(data['url']) # Now actually works
        await generate_audio(data['script'], mode)
        build_sota_video(data)
        upload_all(data)
        send_telegram(message=f"✅ {mode.upper()} Video: {data['name']}", file_path="output.mp4")
    except Exception as e:
        send_telegram(message=f"💥 CRASH: {str(e)[:100]}")
        print(f"CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
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
