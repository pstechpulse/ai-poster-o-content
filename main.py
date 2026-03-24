import os, json, asyncio, requests, time, random, subprocess
from google import genai
from playwright.async_api import async_playwright
import edge_tts
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# --- 1. CONFIG & TELEGRAM ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def send_telegram(message=None, file_path=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id): return
    try:
        if file_path:
            url = f"https://api.telegram.org/bot{token}/sendVideo"
            with open(file_path, 'rb') as f:
                r = requests.post(url, data={'chat_id': chat_id, 'caption': message}, files={'video': f})
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            r = requests.post(url, data={'chat_id': chat_id, 'text': message})
        print(f"📡 Telegram Debug: {r.json()}")
    except Exception as e: print(f"❌ Telegram Error: {e}")

# --- 2. THE SOTA VISUAL ENGINE ---
async def get_tool_screenshot(url):
    print(f"📸 Taking screenshot of {url}...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={'width': 1080, 'height': 1080})
            await page.goto(url, timeout=60000)
            await asyncio.sleep(5)
            await page.screenshot(path="tool_ss.png")
            await browser.close()
            return True
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")
        return False

def get_viral_logic(mode):
    seed = time.time()
    lang = "ROMANIZED HINDI (Hinglish) with BTech Slang" if mode == "hindi" else "High-Energy Global English"
    prompt = f"Seed: {seed}. Mode: {mode}. {lang}. Pick a 100% real trending AI tool for students. Return JSON ONLY with: 'name', 'url', 'hook' (3 words), 'script' (40s), 'title', 'description'."
    res = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt, config={'response_mime_type': 'application/json'})
    # Clean possible markdown backticks
    clean_json = res.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

async def generate_audio(text, mode):
    voice = "hi-IN-MadhurNeural" if mode == "hindi" else "en-US-BrianNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+22%", pitch="+8Hz")
    await communicate.save("voice.mp3")

# --- 3. THE FFmpeg MASTER ---
def build_sota_video(data, has_ss):
    print("🎬 FFmpeg: Building Split-Screen Machine...")
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    
    # Download Bottom Gameplay
    res_b = requests.get("https://api.pexels.com/videos/search?query=minecraft+parkour&per_page=1", headers=headers).json()
    with open("bottom.mp4", 'wb') as f: f.write(requests.get(res_b['videos'][0]['video_files'][0]['link']).content)
    
    # Download Music
    music_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
    with open("music.mp3", 'wb') as f: f.write(requests.get(music_url).content)

    # Determine Top Visual
    input_top = f"-loop 1 -i tool_ss.png" if has_ss else f"-i top_fallback.mp4"
    video_top = f"loop=loop=-1:size=1,scale=1080:960" if has_ss else "scale=1080:960,setsar=1"
    if not has_ss:
        res_t = requests.get("https://api.pexels.com/videos/search?query=tech+coding&per_page=1", headers=headers).json()
        with open("top_fallback.mp4", 'wb') as f: f.write(requests.get(res_t['videos'][0]['video_files'][0]['link']).content)

    # FFmpeg command: Stacks, mixes audio, and draws the hook box
    cmd = (
        f'ffmpeg -y {input_top} -i bottom.mp4 -i voice.mp3 -i music.mp3 '
        f'-filter_complex "'
        f'[0:v]{video_top}[t]; [1:v]scale=1080:960,setsar=1[b]; [t][b]vstack=inputs=2[v]; '
        f'[v]drawtext=text=\'{data["hook"]}\':fontcolor=white:fontsize=90:x=(w-text_w)/2:y=(h-text_h)/2:'
        f'box=1:boxcolor=black@0.8:boxborderw=30:fontfile=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf[outv]; '
        f'[2:a]volume=1.8[v_a]; [3:a]volume=0.15[m_a]; [v_a][m_a]amix=inputs=2:duration=first[outa]" '
        f'-map "[outv]" -map "[outa]" -c:v libx264 -t 45 -pix_fmt yuv420p output.mp4'
    )
    subprocess.run(cmd, shell=True)

# --- 4. UPLOADER ---
def upload_all(data):
    try:
        cl = Client()
        cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
        cl.clip_upload("output.mp4", caption=f"{data['title']}\n\n{data['description']}")
        print("✅ Posted to Instagram")
    except Exception as e: print(f"❌ IG Error: {e}")

    try:
        creds = Credentials.from_authorized_user_info(json.loads(os.getenv("YOUTUBE_TOKEN_JSON")))
        youtube = build("youtube", "v3", credentials=creds)
        youtube.videos().insert(part="snippet,status", body={"snippet": {"title": data['title'], "description": data['description'], "categoryId": "27"}, "status": {"privacyStatus": "public"}}, media_body=MediaFileUpload("output.mp4")).execute()
        print("✅ Posted to YouTube")
    except Exception as e: print(f"❌ YT Error: {e}")

# --- 5. RUNNER ---
async def run_pipeline():
    try:
        mode = random.choice(["hindi", "global"])
        print(f"🚀 Launching {mode.upper()} mode...")
        data = get_viral_logic(mode)
        has_ss = await get_tool_screenshot(data['url'])
        await generate_audio(data['script'], mode)
        build_sota_video(data, has_ss)
        upload_all(data)
        send_telegram(message=f"🏁 SOTA SUCCESS: {data['name']} ({mode.upper()})", file_path="output.mp4")
    except Exception as e:
        send_telegram(message=f"💥 CRASH: {str(e)[:100]}")
        print(f"CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
