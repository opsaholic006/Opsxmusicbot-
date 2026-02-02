import os
import uuid
import aiohttp
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

# --- FONT CHANGE: Use pyfiglet instead of a custom dictionary ---
import pyfiglet

# =====================
# ENVIRONMENT VARIABLES
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

if not BOT_TOKEN or not YOUTUBE_API_KEY or not OWNER_ID:
    raise RuntimeError("Missing required environment variables")

# =============================
# BOT STATE & FONG SETTINGS
# =============================
BOT_ENABLED = True
CURRENT_FONT ='banner' # THE default starting font

# =====================
# CACHE
# =====================
CACHE = {}
CACHE_TTL = 300  # 5 minutes

# =====================
# LANGUAGE TEXT
# =====================
TEXT = {
    "en": {"now_playing": "Now playing", "by": "by"},
    "hi": {"now_playing": "अब चल रहा है", "by": "द्वारा"},
    "es": {"now_playing": "Reproduciendo", "by": "por"},
}

def t(lang, key):
    return TEXT.get(lang, TEXT["en"]).get(key, TEXT["en"][key])

def fraktur(text: str) -> str:
    global CURRENT_FONT
    try:
        # Use the current global font setting
        return pyfiglet.figlet_format(text, font=CURRENT_FONT)
    except pyfiglet.FontNotFound:
        # Fallback to a default font if the specified one isn't found
        return pyfiglet.figlet_format(text, font='standard')

# =====================
# INLINE SEARCH
# =====================
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not BOT_ENABLED:
        return

    query = update.inline_query.query.strip()
    if not query:
        return

    lang = update.inline_query.from_user.language_code or "en"
    now = time.time()

    # ---- CACHE ----
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

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=5) as resp:
            data = await resp.json()

        for item in data.get("items", []):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            channel = item["snippet"]["channelTitle"]
            thumb = item["snippet"]["thumbnails"]["medium"]["url"]

            yt = f"https://www.youtube.com/watch?v={video_id}"
            ytm = f"https://music.youtube.com/watch?v={video_id}"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(fraktur("▶ 𝔓𝔩𝔞𝔶 𝔬𝔫 𝔜𝔬𝔲𝔗𝔲𝔟𝔢"), url=yt)],
                [InlineKeyboardButton(fraktur("🎧 𝔜𝔬𝔘𝔗𝔲𝔅𝔢 𝔐𝔲𝔰𝔦𝔠"), url=ytm)],
            ])

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=fraktur(f"🎼 {title}"),
                    description=fraktur(f"🙍🏻‍♀️ {channel}"),
                    thumbnail_url=thumb,
                    input_message_content=InputTextMessageContent(
                        fraktur(
                            f"🎧 𝔑𝔬𝔴 𝔭𝔩𝔞𝔶\n"
                            f"🎼 {title}\n"
                            f"🙍🏻‍♀️ {t(lang,'by')} {channel}"
                        ),
                        parse_mode="Markdown",
                    ),
                    reply_markup=keyboard,
                )
            )

    CACHE[query] = (results, now)
    await update.inline_query.answer(results, cache_time=300)

# =====================
# OWNER COMMANDS
# =====================
async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED
    if update.effective_user.id != OWNER_ID:
        return
    BOT_ENABLED = False
    await update.message.reply_text("⛔ Opsxmusic stopped")

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED
    if update.effective_user.id != OWNER_ID:
        return
    BOT_ENABLED = True
    await update.message.reply_text("✅ Opsxmusic started")

async def status_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    status = "Running ✅" if BOT_ENABLED else "OFFLINE 📵"
    await update.message.reply_text(f"🎚️ Opsxmusic Status: {status}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "♫ *OpsXMusic Bot Help*\n\n"
        "*Search music anywhere:*\n"
        "`@opsxmusicbot song name`\n\n"
        "▶ *Play* → YouTube\n"
        "🎧 *YouTube Music*\n\n"
        "⚡ Fast • Clean • Global inline search\n\n"
        "💡 Tip: You don’t need /start to use inline search.",
        parse_mode="Markdown"
    )

# NEW COMMAND TO SET FONT DYNAMICALLY
async def set_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID, CURRENT_FONT

    if update.effective_user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(f"Please provide a font name. Current font: **{CURRENT_FONT}**", parse_mode="Markdown")
        return

    new_font = context.args[0].lower() # Get the font name argument
    
    try:
        # Check if the font is valid before changing
        pyfiglet.figlet_format("Test", font=new_font) 
        CURRENT_FONT = new_font
        await update.message.reply_text(f"Font successfully changed to: **{new_font}**", parse_mode="Markdown")
    except pyfiglet.FontNotFound:
        await update.message.reply_text(f"Sorry, the font '**{new_font}**' was not found.", parse_mode="Markdown")

# =====================
# MAIN
# =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(InlineQueryHandler(inline_search))
    app.add_handler(CommandHandler("start", start_bot))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CommandHandler("status", status_bot))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setfont", set_font))

    print("🤖 OpsXMusic running")
    app.run_polling()

if __name__ == "__main__":
    main()
