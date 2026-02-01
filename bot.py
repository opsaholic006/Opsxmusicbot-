import os
import uuid
import asyncio
import urllib.parse
import requests
import yt_dlp

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

# =====================
# ENVIRONMENT
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not BOT_TOKEN or not YOUTUBE_API_KEY:
    raise RuntimeError("Missing BOT_TOKEN or YOUTUBE_API_KEY")

# =====================
# CACHE (video_id -> telegram file_id)
# =====================
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
# DOWNLOAD FUNCTION (SYNC)
# =====================
def download_song(video_id: str):
    os.makedirs("downloads", exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"

    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        base, _ = os.path.splitext(filename)
        return base + ".mp3", info

# =====================
# YOUTUBE SEARCH (SYNC)
# =====================
def yt_search(query: str):
    api_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 6,
        "key": YOUTUBE_API_KEY,
    }
    return requests.get(api_url, params=params, timeout=10).json()

# =====================
# INLINE SEARCH
# =====================
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, yt_search, query)

    results = []

    for item in data.get("items", []):
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        thumb = item["snippet"]["thumbnails"]["medium"]["url"]

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Play", callback_data=f"play|{video_id}")]
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

# =====================
# PLAY CALLBACK
# =====================
async def play_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    video_id = query.data.split("|", 1)[1]

    yt_link = f"https://www.youtube.com/watch?v={video_id}"
    ytm_link = f"https://music.youtube.com/watch?v={video_id}"

    # 🔁 Cached → instant play
    if video_id in AUDIO_CACHE:
        await query.message.reply_audio(
            audio=AUDIO_CACHE[video_id],
            caption=(
                f"▶️ [YouTube]({yt_link})\n"
                f"🎶 [YouTube Music]({ytm_link})\n"
                f"💚 [Spotify](https://open.spotify.com)"
            ),
            parse_mode="Markdown",
        )
        return

    await query.edit_message_text("🎧 Downloading audio…")

    loop = asyncio.get_running_loop()
    try:
        file_path, info = await loop.run_in_executor(
            None, download_song, video_id
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Failed: `{e}`")
        return

    title = info.get("title", "Unknown")
    artist = info.get("uploader", "Unknown")

    spotify_q = urllib.parse.quote(f"{title} {artist}")
    spotify_link = f"https://open.spotify.com/search/{spotify_q}"

    caption = (
        f"🎵 *{title}*\n"
        f"👤 {artist}\n\n"
        f"▶️ [YouTube]({yt_link})\n"
        f"🎶 [YouTube Music]({ytm_link})\n"
        f"💚 [Spotify]({spotify_link})"
    )

    with open(file_path, "rb") as audio:
        sent = await query.message.reply_audio(
            audio=audio,
            title=title,
            performer=artist,
            caption=caption,
            parse_mode="Markdown",
        )

    AUDIO_CACHE[video_id] = sent.audio.file_id
    os.remove(file_path)

# =====================
# COMMANDS
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎧 *OpsXMusic*\n\n"
        "Use inline mode:\n"
        "`@Opsxmusicbot song name`",
        parse_mode="Markdown",
    )

# =====================
# MAIN
# =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(InlineQueryHandler(inline_search))
    app.add_handler(CallbackQueryHandler(play_callback))

    print("🤖 OpsXMusic running")
    app.run_polling()

if __name__ == "__main__":
    main()
