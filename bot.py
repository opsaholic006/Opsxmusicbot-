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
# CONFIGURATION
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# State
BOT_ENABLED = True
CURRENT_FONT = 'small'  # Default to "Small Caps" (ɴᴏᴡ ᴘʟᴀʏ)
CACHE = {}
CACHE_TTL = 300 

# =====================
# FONT MAPPING (Unicode)
# =====================
FONT_MAPS = {
    # ɴᴏᴡ ᴘʟᴀʏ Style (Small Caps)
    "small": "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
    
    # 𝓒𝓾𝓻𝓼𝓲𝓿𝓮 Style (Bold Cursive)
    "cursive": "𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃𝓐𝓑𝓒𝓓𝓔𝓕𝓖𝓗𝓘𝓙𝓚𝓛𝓜𝓝𝓞𝓟𝓠𝓡𝓢𝓣𝓤𝓥𝓦𝓧𝓨𝓩",
    
    # 𝐛𝐨𝐥𝐝 Style (Sans-Serif Bold)
    "bold": "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙",
    
    # Standard mapping
    "normal": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
}

def apply_style(text: str) -> str:
    global CURRENT_FONT
    if CURRENT_FONT not in FONT_MAPS or CURRENT_FONT == "normal":
        return text
    
    normal_chars = FONT_MAPS["normal"]
    styled_chars = FONT_MAPS[CURRENT_FONT]
    trans_table = str.maketrans(normal_chars, styled_chars)
    return text.translate(trans_table)

# =====================
# INLINE SEARCH
# =====================
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not BOT_ENABLED: return

    query = update.inline_query.query.strip()
    if not query: return

    now = time.time()
    if query in CACHE:
        results, ts = CACHE[query]
        if now - ts < CACHE_TTL:
            await update.inline_query.answer(results, cache_time=300)
            return

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet", "q": query, "type": "video",
        "maxResults": 5, "key": YOUTUBE_API_KEY,
    }

    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                data = await resp.json()

        for item in data.get("items", []):
            vid = item["id"]["videoId"]
            title = item["snippet"]["title"]
            chan = item["snippet"]["channelTitle"]
            thumb = item["snippet"]["thumbnails"]["medium"]["url"]

            yt = f"https://www.youtube.com/watch?v={vid}"
            ytm = f"https://music.youtube.com/watch?v={vid}"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("▶ Play on YouTube", url=yt)],
                [InlineKeyboardButton("🎧 YouTube Music", url=ytm)],
            ])

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=apply_style(f"🎼 {title}"),
                    description=apply_style(f"🙍🏻‍♀️ {chan}"),
                    thumbnail_url=thumb,
                    input_message_content=InputTextMessageContent(
                        apply_style(f"🎧 Now playing\n🎼 {title}\n🙍🏻‍♀️ by {chan}"),
                        parse_mode="Markdown",
                    ),
                    reply_markup=keyboard,
                )
            )
        CACHE[query] = (results, now)
        await update.inline_query.answer(results, cache_time=300)
    except Exception as e:
        print(f"Error: {e}")

# =====================
# COMMANDS
# =====================
async def set_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CURRENT_FONT
    if update.effective_user.id != OWNER_ID: return
    
    if not context.args:
        fonts = ", ".join([f"`{f}`" for f in FONT_MAPS.keys()])
        await update.message.reply_text(f"Current: `{CURRENT_FONT}`\nAvailable: {fonts}")
        return

    f_choice = context.args[0].lower()
    if f_choice in FONT_MAPS:
        CURRENT_FONT = f_choice
        await update.message.reply_text(apply_style(f"✅ Font set to {f_choice}"))
    else:
        await update.message.reply_text("❌ Font not found.")

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == OWNER_ID:
        global BOT_ENABLED
        BOT_ENABLED = True
        await update.message.reply_text("✅ Bot Started")

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == OWNER_ID:
        global BOT_ENABLED
        BOT_ENABLED = False
        await update.message.reply_text("⛔ Bot Stopped")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_bot))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CommandHandler("setfont", set_font))
    app.add_handler(InlineQueryHandler(inline_search))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
