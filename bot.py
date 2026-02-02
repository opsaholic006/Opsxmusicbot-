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

# =====================
# FRAKTUR FONT SYSTEM
# =====================
FRAKTUR = {
    "A":"𝔄","B":"𝔅","C":"ℭ","D":"𝔇","E":"𝔈","F":"𝔉","G":"𝔊",
    "H":"ℌ","I":"ℑ","J":"𝔍","K":"𝔎","L":"𝔏","M":"𝔐","N":"𝔑",
    "O":"𝔒","P":"𝔓","Q":"𝔔","R":"ℜ","S":"𝔖","T":"𝔗","U":"𝔘",
    "V":"𝔙","W":"𝔚","X":"𝔛","Y":"𝔜","Z":"ℨ",
    "a":"𝔞","b":"𝔟","c":"𝔠","d":"𝔡","e":"𝔢","f":"𝔣","g":"𝔤",
    "h":"𝔥","i":"𝔦","j":"𝔧","k":"𝔨","l":"𝔩","m":"𝔪","n":"𝔫",
    "o":"𝔬","p":"𝔭","q":"𝔮","r":"𝔯","s":"𝔰","t":"𝔱","u":"𝔲",
    "v":"𝔳","w":"𝔴","x":"𝔵","y":"𝔶","z":"𝔷",
    "0":"𝟘","1":"𝟙","2":"𝟚","3":"𝟛","4":"𝟜",
    "5":"𝟝","6":"𝟞","7":"𝟟","8":"𝟠","9":"𝟡"
}

def fraktur(text: str) -> str:
    return "".join(FRAKTUR.get(c, c) for c in text)

# =====================
# ENVIRONMENT VARIABLES
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

if not BOT_TOKEN or not YOUTUBE_API_KEY or not OWNER_ID:
    raise RuntimeError("Missing required environment variables")

# =====================
# BOT STATE
# =====================
BOT_ENABLED = True

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
        sp = f"https://open.spotify.com/search/{title}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(fraktur("▶Play on YouTube", url=yt)],
            [InlineKeyboardButton(fraktur("🎧 YouTube Music", url=ytm)],
            [InlineKeyboardButton("🟢 Spotify", url=sp)],
        ])

        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=fraktur"🎼 {title}",
                description=fraktur"🙍🏻‍♀️ {channel}",
                thumbnail_url=thumb,
                input_message_content=InputTextMessageContent(
                     fraktur(
                    f"🎧 *{t(lang,'now_playing')}*\n"
                    f"🎼 *{title}*\n"
                    f"🙍🏻‍♀️ {t(lang,'by')} {channel}",
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
    if update.effective_user.id == OWNER_ID:
        BOT_ENABLED = False
        await update.message.reply_text("⛔ Opsxmusic stopped")

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED
    if update.effective_user.id == OWNER_ID:
        BOT_ENABLED = True
        await update.message.reply_text("✅ Opsxmusic started")

async def status_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == OWNER_ID:
        return
    status = "Running ✅" if BOT_ENABLED else "OFFLINE 📵"
        await update.message.reply_text(f"🎚️ Opsxmusic Status: {status}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "♫*OpsXMusic Bot Help*\n\n"
        "*Search music anywhere:*\n"
        "`@opsxmusicbot song name`\n\n"
        "> *Play* opens the song on YouTube\n"
        "*YouTube Music* opens in YouTube Music\n\n"
        "⚡ Fast • Clean • Global inline search\n\n"
        "💡 Tip: You don't need to start the bot to use inline search.",
        parse_mode="Markdown"
    )

# =====================
# MAIN
# =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(InlineQueryHandler(inline_search))
    app.add_handler(CommandHandler("start", start_bot))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CommandHandler("status", status_bot))

    print("🤖 OpsXMusic running")
    app.run_polling()

if __name__ == "__main__":
    main()
