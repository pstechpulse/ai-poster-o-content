import os, json, asyncio, requests, time, random, subprocess
from google import genai
from playwright.async_api import async_playwright
import edge_tts
from instagrapi import Client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def send_telegram(message=None, file_path=None):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id): return
    try:
        url = f"https://api.telegram.org/bot{token}/"
        if file_path:
            with open(file_path, 'rb') as f:
                requests.post(url + "sendVideo", data={'chat_id': chat_id, 'caption': message}, files={'video': f})
        else:
            requests.post(url + "sendMessage", data={'chat_id': chat_id, 'text': message})
    except Exception as e: print(f"❌ Telegram Error: {e}")

async def get_stealth_screenshot(url):
    print(f"📸 Stealth-grabbing {url}...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(8) # Bypass initial verification
            await page.screenshot(path="tool_ss.png")
            await browser.close()
            return True
    except: return False

def build_sota_video(data, has_ss, word_timings):
    print("🎬 FFmpeg: Creating the Ultimate Retention Reel...")
    
    # 1. DOWNLOAD ASSETS
    # BOTTOM: Verified Minecraft Parkour Loop (Direct Raw Link)
    gp_url = "https://raw.githubusercontent.com/the-muda-project/video-assets/main/minecraft_parkour.mp4"
    r = requests.get(gp_url)
    with open("bottom.mp4", 'wb') as f: f.write(r.content)
    
    # MUSIC: Lo-fi Background
    r_music = requests.get("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")
    with open("music.mp3", 'wb') as f: f.write(r_music.content)

    # TOP: Tool or Fallback
    top_input = "-loop 1 -i tool_ss.png" if has_ss else "-i top_fallback.mp4"
    if not has_ss:
        res = requests.get(f"https://api.pexels.com/videos/search?query=coding&per_page=1", headers={"Authorization": os.getenv("PEXELS_API_KEY")}).json()
        with open("top_fallback.mp4", 'wb') as f: f.write(requests.get(res['videos'][0]['video_files'][0]['link']).content)

    # 2. GENERATE DYNAMIC SUBTITLE FILTER
    # This creates a chain of drawtext commands for EVERY word
    text_filters = []
    for item in word_timings:
        word = item['word'].replace("'", "").upper() # Escape quotes
        start, end = item['start'], item['end']
        # Styling: Neon Yellow, centered, heavy black border
        filter_str = f"drawtext=text='{word}':fontcolor=yellow:fontsize=110:x=(w-text_w)/2:y=(h-text_h)/2:borderw=6:bordercolor=black:enable='between(t,{start},{end})'"
        text_filters.append(filter_str)
    
    full_text_chain = ",".join(text_filters)

    # 3. FINAL FFmpeg EXECUTION
    video_top = "loop=loop=-1:size=1,scale=1080:960" if has_ss else "scale=1080:960,setsar=1"
    
    cmd = (
        f'ffmpeg -y {top_input} -i bottom.mp4 -i voice.mp3 -i music.mp3 '
        f'-filter_complex "'
        f'[0:v]{video_top}[t]; [1:v]scale=1080:960,setsar=1[b]; [t][b]vstack=inputs=2[v_all]; '
        f'[v_all]{full_text_chain}[outv]; '
        f'[2:a]volume=2.0[v_a]; [3:a]volume=0.15[m_a]; [v_a][m_a]amix=inputs=2:duration=first[outa]" '
        f'-map "[outv]" -map "[outa]" -c:v libx264 -t 45 -pix_fmt yuv420p output.mp4'
    )
    
    subprocess.run(cmd, shell=True)

async def run_pipeline():
    try:
        mode = random.choice(["hindi", "global"])
        print(f"🚀 MODE: {mode.upper()}")
        
        prompt = f"Mode: {mode}. Pick a unique AI tool. Return JSON: 'name', 'url', 'script' (40s), 'title', 'description'."
        res = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt, config={'response_mime_type': 'application/json'})
        data = json.loads(res.text.replace("```json", "").replace("```", "").strip())
        
        # 1. Assets
        has_ss = await get_stealth_screenshot(data['url'])
        
        # 2. Voice + Word Timings
        voice = "hi-IN-MadhurNeural" if mode == "hindi" else "en-US-BrianNeural"
        communicate = edge_tts.Communicate(data['script'], voice, rate="+25%", pitch="+10Hz")
        word_timings = []
        with open("voice.mp3", "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio": f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    word_timings.append({"word": chunk["text"], "start": chunk["offset"]/10000000, "end": (chunk["offset"]+chunk["duration"])/10000000})
        
        # 3. Build & Upload
        build_sota_video(data, has_ss, word_timings)
        
        try:
            cl = Client()
            cl.set_settings(json.loads(os.getenv("INSTA_SESSION_JSON")))
            cl.clip_upload("output.mp4", caption=f"{data['title']}\n\n{data['description']}")
            print("✅ IG Success")
        except: pass

        send_telegram(message=f"🏁 SOTA Success: {data['name']}", file_path="output.mp4")
    except Exception as e:
        send_telegram(message=f"💥 Crash: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
            media_body=MediaFileUpload("output.mp4")
        ).execute()
        print("✅ Posted to YouTube")
    except Exception as e: print(f"❌ YT Error: {e}")

# --- 5. MAIN RUNNER ---
async def run_pipeline():
    try:
        mode = random.choice(["hindi", "global"])
        print(f"🚀 Running in {mode.upper()} mode...")
        
        prompt = f"Mode: {mode}. Pick a unique AI tool for BTech students. Return JSON ONLY: 'name', 'url', 'script' (40s), 'title', 'description'."
        res = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt, config={'response_mime_type': 'application/json'})
        data = json.loads(res.text.replace("```json", "").replace("```", "").strip())
        
        # Asset Generation
        has_ss = await get_stealth_screenshot(data['url'])
        
        voice = "hi-IN-MadhurNeural" if mode == "hindi" else "en-US-BrianNeural"
        communicate = edge_tts.Communicate(data['script'], voice, rate="+25%", pitch="+10Hz")
        word_timings = []
        with open("voice.mp3", "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio": f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    word_timings.append({"word": chunk["text"], "start": chunk["offset"]/10000000, "end": (chunk["offset"]+chunk["duration"])/10000000})
        
        create_ass_subs(word_timings)
        build_sota_video(data, has_ss)
        
        # UPLOAD
        upload_all(data)
        send_telegram(message=f"🏁 SOTA SUCCESS: {data['name']} ({mode.upper()})", file_path="output.mp4")
        
    except Exception as e:
        send_telegram(message=f"💥 CRASH REPORT: {str(e)}")
        print(f"CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
