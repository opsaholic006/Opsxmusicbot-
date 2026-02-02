import os
import uuid
import aiohttp
import time
import pyfiglet
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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

if not BOT_TOKEN or not YOUTUBE_API_KEY:
    raise RuntimeError("Missing required environment variables: BOT_TOKEN or YOUTUBE_API_KEY")

# =============================
# BOT STATE & FONT SETTINGS
# =============================
BOT_ENABLED = True
CURRENT_FONT = 'banner' 
CACHE = {}
CACHE_TTL = 300 

TEXT = {
    "en": {"now_playing": "Now playing", "by": "by"},
    "hi": {"now_playing": "अब चल रहा है", "by": "द्वारा"},
    "es": {"now_playing": "Reproduciendo", "by": "por"},
}

# =====================
# HELPERS
# =====================
def t(lang, key):
    return TEXT.get(lang, TEXT["en"]).get(key, TEXT["en"][key])

def fraktur(text: str) -> str:
    global CURRENT_FONT
    try:
        return pyfiglet.figlet_format(text, font=CURRENT_FONT)
    except Exception:
        return text  # Fallback to plain text if figlet fails (important for stability)

# =====================
# INLINE SEARCH (FIXED)
# =====================
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not BOT_ENABLED:
        return

    query = update.inline_query.query.strip()
    if not query:
        return

    lang = update.inline_query.from_user.language_code or "en"
    now = time.time()

    # ---- CACHE CHECK ----
    if query in CACHE:
        results, ts = CACHE[query]
        if now - ts < CACHE_TTL:
            await update.inline_query.answer(results, cache_time=300)
            return

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 5,
        "key": YOUTUBE_API_KEY,
    }

    results = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return # Log error here if needed
                data = await resp.json()

        for item in data.get("items", []):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            channel = item["snippet"]["channelTitle"]
            thumb = item["snippet"]["thumbnails"]["medium"]["url"]

            yt = f"https://www.youtube.com/watch?v={video_id}"
            ytm = f"https://music.youtube.com/watch?v={video_id}"

            # Formatting buttons
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("▶ Play on YouTube", url=yt)],
                [InlineKeyboardButton("🎧 YouTube Music", url=ytm)],
            ])

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=f"🎼 {title}",
                    description=f"🙍🏻‍♀️ {channel}",
                    thumbnail_url=thumb,
                    input_message_content=InputTextMessageContent(
                        f"🎧 *{t(lang, 'now_playing')}*\n\n"
                        f"🎼 *{title}*\n"
                        f"🙍🏻‍♀️ {t(lang,'by')} {channel}",
                        parse_mode="Markdown",
                    ),
                    reply_markup=keyboard,
                )
            )

        CACHE[query] = (results, now)
        await update.inline_query.answer(results, cache_time=300)
        
    except Exception as e:
        print(f"Search Error: {e}")

# =====================
# COMMAND HANDLERS
# =====================
async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED
    if update.effective_user.id == OWNER_ID:
        BOT_ENABLED = True
        await update.message.reply_text("✅ Opsxmusic started")

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED
    if update.effective_user.id == OWNER_ID:
        BOT_ENABLED = False
        await update.message.reply_text("⛔ Opsxmusic stopped")

async def status_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "Running ✅" if BOT_ENABLED else "OFFLINE 📵"
    await update.message.reply_text(f"🎚️ Opsxmusic Status: {status}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "♫ *OpsXMusic Bot Help*\n\n"
        "Search music by typing in any chat:\n"
        "`@your_bot_username song name`\n\n"
        "⚡ Fast • Clean • Global search",
        parse_mode="Markdown"
    )

async def set_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CURRENT_FONT
    if update.effective_user.id != OWNER_ID: return
    
    if not context.args:
        await update.message.reply_text(f"Current font: `{CURRENT_FONT}`")
        return

    new_font = context.args[0].lower()
    try:
        pyfiglet.figlet_format("Test", font=new_font)
        CURRENT_FONT = new_font
        await update.message.reply_text(f"Font set to: `{new_font}`")
    except Exception:
        await update.message.reply_text("Font not found.")

# =====================
# MAIN
# =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Registering handlers
    app.add_handler(CommandHandler("start", start_bot))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CommandHandler("status", status_bot))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setfont", set_font))
    app.add_handler(InlineQueryHandler(inline_search))

    print("🤖 OpsXMusic is online...")
    app.run_polling()

if __name__ == "__main__":
    main()
