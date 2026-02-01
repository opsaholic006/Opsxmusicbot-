import os
import uuid
import asyncio
import urllib.parse
import requests
import yt_dlp
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.ext import (
    Application,
    CommandHandler,
    InlineQueryHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Enable Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================
# ENVIRONMENT
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not BOT_TOKEN or not YOUTUBE_API_KEY:
    raise RuntimeError("Missing BOT_TOKEN or YOUTUBE_API_KEY in Environment Variables")

# Local cache for the session (Note: Clears on restart)
AUDIO_CACHE: dict[str, str] = {}

# =====================
# YT-DLP CONFIG
# =====================
YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "outtmpl": "downloads/%(id)s.%(ext)s",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
}

# =====================
# HELPER FUNCTIONS
# =====================
def download_song(video_id: str):
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        # yt-dlp might change extension to .mp3 due to postprocessor
        expected_file = os.path.join("downloads", f"{video_id}.mp3")
        return expected_file, info

def yt_search(query: str):
    api_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 6,
        "key": YOUTUBE_API_KEY,
    }
    response = requests.get(api_url, params=params, timeout=10)
    return response.json()

# =====================
# HANDLERS
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎧 *OpsXMusic Bot*\n\nSearch for music directly in any chat!\n"
        "Type `@your_bot_username song name`",
        parse_mode="Markdown",
    )

async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return

    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, yt_search, query)
        results = []

        for item in data.get("items", []):
            if "id" not in item or "videoId" not in item["id"]:
                continue
                
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            channel = item["snippet"]["channelTitle"]
            thumb = item["snippet"]["thumbnails"]["medium"]["url"]

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬇️ Download & Play", callback_data=f"play|{video_id}")]
            ])

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=channel,
                    thumb_url=thumb,
                    input_message_content=InputTextMessageContent(
                        f"🎵 *{title}*\n👤 {channel}",
                        parse_mode="Markdown",
                    ),
                    reply_markup=keyboard,
                )
            )
        await update.inline_query.answer(results, cache_time=15)
    except Exception as e:
        logger.error(f"Inline Search Error: {e}")

async def play_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    video_id = query.data.split("|", 1)[1]
    yt_link = f"https://www.youtube.com/watch?v={video_id}"
    
    # 1. Check Cache
    if video_id in AUDIO_CACHE:
        try:
            await query.message.reply_audio(
                audio=AUDIO_CACHE[video_id],
                caption=f"✅ Resent from cache\n▶️ [Watch on YouTube]({yt_link})",
                parse_mode="Markdown"
            )
            return
        except Exception:
            # If cache fails (e.g. file_id expired), proceed to re-download
            pass

    status_msg = await query.edit_message_text("📥 Downloading and converting... please wait.")

    # 2. Download
    file_path = None
    try:
        loop = asyncio.get_running_loop()
        file_path, info = await loop.run_in_executor(None, download_song, video_id)
        
        title = info.get("title", "Unknown Track")
        performer = info.get("uploader", "Unknown Artist")

        # 3. Upload to Telegram
        with open(file_path, "rb") as audio_file:
            sent = await query.message.reply_audio(
                audio=audio_file,
                title=title,
                performer=performer,
                caption=f"🎵 *{title}*\n👤 {performer}\n\n▶️ [YouTube]({yt_link})",
                parse_mode="Markdown"
            )
            
        # 4. Save to Cache and Delete File
        AUDIO_CACHE[video_id] = sent.audio.file_id
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Playback Error: {e}")
        await query.edit_message_text(f"❌ Failed to process audio.\nError: `{str(e)}`", parse_mode="Markdown")
    
    finally:
        # 5. Cleanup local storage
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

# =====================
# MAIN
# =====================
def main():
    # Create the app
    application = Application.builder().token(BOT_TOKEN).build()

    # Add Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inline_search))
    application.add_handler(CallbackQueryHandler(play_callback))

    # Start the Bot
    print("🤖 Bot is live on Railway!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
