# =========================
# IMPORTS
# =========================
import os
import uuid
import asyncio
import requests
from time import time

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

# =========================
# ENVIRONMENT VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OWNER_ID_RAW = os.getenv("OWNER_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not YOUTUBE_API_KEY:
    raise RuntimeError("YOUTUBE_API_KEY is missing")

if not OWNER_ID_RAW:
    raise RuntimeError("OWNER_ID is missing")

OWNER_ID = int(OWNER_ID_RAW)

# =========================
# BOT STATE
# =========================
BOT_ENABLED = True

# =========================
# CACHE
# =========================
CACHE = {}
CACHE_TTL = 300  # seconds

# =========================
# LANGUAGE TEXT
# =========================
TEXT = {
    "en": {
        "now_playing": "Now playing",
        "by": "by",
        "downloading": "⬇ Downloading… please wait",
    },
    "hi": {
        "now_playing": "अब चल रहा है",
        "by": "द्वारा",
        "downloading": "⬇ डाउनलोड हो रहा है… कृपया प्रतीक्षा करें",
    },
    "es": {
        "now_playing": "Reproduciendo",
        "by": "por",
        "downloading": "⬇ Descargando… espera",
    },
}

def t(lang, key):
    return TEXT.get(lang, TEXT["en"]).get(key, TEXT["en"][key])

# =========================
# AUDIO DOWNLOAD
# =========================
def download_song(url: str):
    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        base, _ = os.path.splitext(filename)
        return base + ".mp3", info

# =========================
# INLINE SEARCH HANDLER
# =========================
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED

    if not BOT_ENABLED:
        return

    query = update.inline_query.query.strip()
    if not query:
        return

    lang = update.inline_query.from_user.language_code or "en"
    now = time()

    # ---- CACHE CHECK ----
    if query in CACHE:
        cached_results, ts = CACHE[query]
        if now - ts < CACHE_TTL:
            await update.inline_query.answer(cached_results, cache_time=300)
            return

    # ---- YOUTUBE SEARCH ----
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 5,
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(url, params=params).json()
    results = []

    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        thumb = item["snippet"]["thumbnails"]["medium"]["url"]

        yt_url = f"https://www.youtube.com/watch?v={video_id}"

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬇ Download & Play", callback_data=f"dl|{video_id}")]
            ]
        )

        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"🎵 {title}",
                description=f"👤 {channel}",
                thumbnail_url=thumb,
                input_message_content=InputTextMessageContent(
                    f"🎧 *{t(lang,'now_playing')}*\n"
                    f"🎵 *{title}*\n"
                    f"👤 {t(lang,'by')} {channel}",
                    parse_mode="Markdown",
                ),
                reply_markup=keyboard,
            )
        )

    CACHE[query] = (results, now)
    await update.inline_query.answer(results, cache_time=300)

# =========================
# DOWNLOAD CALLBACK
# =========================
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, video_id = query.data.split("|")
    yt_url = f"https://www.youtube.com/watch?v={video_id}"

    lang = query.from_user.language_code or "en"
    await query.edit_message_text(t(lang, "downloading"))

    loop = asyncio.get_running_loop()
    file_path, info = await loop.run_in_executor(None, download_song, yt_url)

    with open(file_path, "rb") as audio:
        await query.message.reply_audio(
            audio=audio,
            title=info.get("title"),
            performer=info.get("uploader"),
            duration=info.get("duration"),
        )

    os.remove(file_path)

# =========================
# OWNER COMMANDS
# =========================
async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED
    if update.effective_user.id != OWNER_ID:
        return
    BOT_ENABLED = False
    await update.message.reply_text("⛔ OpsXMusic stopped.")

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED
    if update.effective_user.id != OWNER_ID:
        return
    BOT_ENABLED = True
    await update.message.reply_text("✅ OpsXMusic started.")

async def status_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    status = "ON ✅" if BOT_ENABLED else "OFF ⛔"
    await update.message.reply_text(f"🤖 Bot status: {status}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *OpsXMusic Bot Help*\n\n"
        "🔍 *Inline search anywhere:*\n"
        "`@Opsxmusicbot song name`\n\n"
        "⬇ Download & play audio directly in Telegram\n\n"
        "⚡ Fast • Cached • Multilingual",
        parse_mode="Markdown",
    )

# =========================
# MAIN
# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(InlineQueryHandler(inline_search))
    app.add_handler(CallbackQueryHandler(download_callback))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", start_bot))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CommandHandler("status", status_bot))

    print("🤖 OpsXMusic bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
