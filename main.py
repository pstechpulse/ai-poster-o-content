import os, json, asyncio, requests, time, random, cv2, numpy as np
from google import genai
import PIL.Image
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
import edge_tts

# 1. PILLOW & FONT FIXES
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. PRONUNCIATION FIXER (No more "Versus Code")
def fix_pronunciation(text):
    replacements = {
        "VS Code": "V S Code", "AI": "A.I.", "API": "A.P.I.", 
        "BTech": "B-Tech", "PDF": "P.D.F.", "UI": "U.I.",
        "GitHub": "Git-Hub", "Python": "Py-thon"
    }
    for word, replacement in replacements.items():
        text = text.replace(word, replacement)
    return text

def get_viral_content(mode):
    seed = time.time()
    prompt = f"""
    Seed: {seed}. Mode: {mode}. You are a Gen-Z Viral Content Creator.
    Pick a trending AI tool for students/developers. 
    1. Hook: Must be a high-tension 'Wait, am I cooked?' or 'SYSTUMMM' moment.
    2. Visuals: Provide exactly 5 scenes. For each, give a specific 3-word Pexels query that matches the sentence.
    Return ONLY a JSON object:
    {{
      "tool_name": "Name",
      "hook": "ONLY 3 WORDS MAX",
      "full_script": "40s high-energy script using Gen-Z BTech slang.",
      "scenes": [
        {{"text": "First 8s of script", "query": "stressed student coding"}},
        {{"text": "Next 8s", "query": "cyberpunk blue tech"}},
        {{"text": "Next 8s", "query": "futuristic robot screen"}},
        {{"text": "Next 8s", "query": "dark keyboard typing"}},
        {{"text": "Last 8s", "query": "happy student success"}}
      ],
      "title": "This is Illegal to know #shorts #tech",
      "description": "Link in bio! #shorts"
    }}
    """
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(response.text)

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
    return word_timings

def build_video(data, word_timings):
    print("🎬 Directing the video...")
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    main_audio = AudioFileClip("audio.mp3")
    
    # 3. SCENE-BY-SCENE SYNC
    scene_clips = []
    duration_per_scene = main_audio.duration / len(data['scenes'])
    
    for i, scene in enumerate(data['scenes']):
        try:
            res = requests.get(f"https://api.pexels.com/videos/search?query={scene['query']}&per_page=1&orientation=portrait", headers=headers).json()
            v_url = res['videos'][0]['video_files'][0]['link']
            fname = f"scene_{i}.mp4"
            with open(fname, 'wb') as f: f.write(requests.get(v_url).content)
            
            clip = VideoFileClip(fname).subclip(0, duration_per_scene).resize(height=1920)
            clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=1080, height=1920)
            scene_clips.append(clip)
        except:
            continue

    bg_video = concatenate_videoclips(scene_clips, method="compose")

    # 4. BIG NEON SUBTITLES
    sub_clips = []
    for item in word_timings:
        txt = TextClip(
            item['word'].upper(), fontsize=130, color='#00FF00', # Neon Green
            stroke_color='black', stroke_width=5, font='DejaVu-Sans-Bold',
            method='label'
        ).set_start(item['start']).set_duration(item['end'] - item['start']).set_position('center')
        sub_clips.append(txt)

    # 5. MUSIC OVERLAY (Hides the robot voice)
    # Note: Use a royalty-free music URL or keep a "music.mp3" in your repo
    final = CompositeVideoClip([bg_video] + sub_clips).set_audio(main_audio)
    final.write_videofile("output.mp4", fps=24, codec="libx264", audio_codec="aac")

async def run_pipeline():
    try:
        # 1. Choose mode and get content
        mode = random.choice(["hindi", "global"])
        print(f"🚀 Running in {mode.upper()} mode...")
        data = get_viral_content(mode)
        
        # 2. Generate Voice and Subtitle timings
        timings = await generate_voice_data(data, mode)
        
        # 3. Build the actual video file
        build_video(data, timings)
        
        # 4. THE MISSING PIECE: Upload to YT and IG
        upload_all(data)
        
        # 5. Send a copy to your phone
        send_telegram(message=f"✅ {mode.upper()} Video: {data['tool_name']}", file_path="output.mp4")
        
        print("🏁 FULL SUCCESS: Video is live!")
    except Exception as e:
        # Health check notification
        send_telegram(message=f"💥 CRASH: {str(e)[:100]}")
        print(f"💥 CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
