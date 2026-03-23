import os
import json
import asyncio
from google import genai
import PIL.Image
# Fix for MoviePy/Pillow 10+
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# Initialize the new Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_daily_topic():
    prompt = "Find a trending AI tool for students. Return JSON: {'tool_name': '...', 'hook': '...', 'script': '...', 'keywords': [], 'title': '', 'description': ''}"
    
    # New 2026 Syntax
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt,
        config={
            'response_mime_type': 'application/json',
        }
    )
    return json.loads(response.text)

# 3. HUMAN-LIKE VOICE
async def generate_voice(text):
    # Using 'Andrew' - he sounds like a real tech reviewer
    communicate = edge_tts.Communicate(text, "en-US-AndrewNeural")
    await communicate.save("audio.mp3")

# 4. CAPTION GENERATOR (Word-by-Word style)
def create_captions(text, duration):
    # This creates a big bold central caption
    # For a true 'BTech' bot, we keep it simple but bold
    return TextClip(
        text, 
        fontsize=70, 
        color='yellow', 
        font='Arial-Bold',
        method='caption', 
        size=(800, None)
    ).set_duration(duration).set_position('center')

# 5. VIDEO ASSEMBLY
def build_video(data):
    # Fetch Backgrounds
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    clips = []
    for kw in data['keywords']:
        res = requests.get(f"https://api.pexels.com/videos/search?query={kw}&per_page=1", headers=headers).json()
        v_url = res['videos'][0]['video_files'][0]['link']
        with open(f"{kw}.mp4", 'wb') as f: f.write(requests.get(v_url).content)
        clips.append(VideoFileClip(f"{kw}.mp4").subclip(0, 5).resize(height=1920))
    
    bg_video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip("audio.mp3")
    bg_video = bg_video.set_duration(audio.duration)
    
    # Overlay the hook as a big caption
    cap = create_captions(data['hook'], audio.duration)
    
    final = CompositeVideoClip([bg_video, cap])
    final.set_audio(audio).write_videofile("output.mp4", fps=24, codec="libx264")

# 6. AUTO-UPLOADING LOGIC
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
    print("🚀 Starting Pipeline...")
    data = get_daily_topic()
    await generate_voice(data['script'])
    build_video(data)
    upload_all(data)
    print("🏁 Done!")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
