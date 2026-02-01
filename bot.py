import os
import uuid
import requests
import time

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update
)
from telegram.ext import (
    Application,
    CommandHandler,
    InlineQueryHandler,
    ContextTypes
)

# =====================
# ENVIRONMENT VARIABLES
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
OWNER_ID_RAW = os.environ.get("OWNER_ID")

# ---- VALIDATION ----
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing or empty")

BOT_TOKEN = BOT_TOKEN.strip()

if not OWNER_ID_RAW:
    raise RuntimeError("OWNER_ID is missing")

OWNER_ID = int(OWNER_ID_RAW)

# ============================
# OWNER SETTINGS
# ============================
BOT_ENABLED = True

# =========================
# CACHE (FAST RESPONSES)
# =========================
CACHE = {}
CACHE_TTL = 300  # seconds (5 minutes)

# =========================
# LANGUAGE TEXT
# =========================
TEXT = {
    "en": {
        "now_playing": "Now playing",
        "by": "by"
    },
    "hi": {
        "now_playing": "अब चल रहा है",
        "by": "द्वारा"
    },
    "es": {
        "now_playing": "Reproduciendo",
        "by": "por"
    }
}

def t(lang, key):
    return TEXT.get(lang, TEXT["en"]).get(key, TEXT["en"][key])

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
        "key": YOUTUBE_API_KEY
    }

    response = requests.get(url, params=params).json()
    results = []

    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        thumb = item["snippet"]["thumbnails"]["medium"]["url"]

        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        yt_music_url = f"https://music.youtube.com/watch?v={video_id}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶ Play", url=youtube_url)],
            [InlineKeyboardButton("🎧 YouTube Music", url=yt_music_url)]
        ])

        # This was indented too far; it is now aligned with 'keyboard'
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
                    parse_mode="Markdown"
                ),
                reply_markup=keyboard
            )
        )

    # These must be outside the 'for' loop to send all results at once
    CACHE[query] = (results, now)
    await update.inline_query.answer(results, cache_time=300)

# ====================
# OWNER COMMANDS
# ====================
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
        "🔍 *Search music anywhere:*\n"
        "`@opsxmusicbot song name` \n\n"
        "▶ *Play* - opens the song on YouTube\n"
        "🎧 *YouTube Music* - opens in YouTube Music\n\n"
        "⚡ Fast • Clean • Global inline search\n\n"
        "ℹ️ Tip: You don't need to start the bot to use inline search.",
        parse_mode="Markdown"
    )

# =====================
# MAIN
# =====================
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing or empty")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(InlineQueryHandler(inline_search))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CommandHandler("start", start_bot))
    app.add_handler(CommandHandler("status", status_bot))

    print("🤖 OpsXMusic bot running (Railway-ready)")
    app.run_polling()

if __name__ == "__main__":
    main()
