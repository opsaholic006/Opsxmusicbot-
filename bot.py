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

# # # # # # # # # # # # # # # # # #
# FONT SYSTEM
# # # # # # # # # # # # # # # # # #
FONT_MAPS = {
    "small": "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
    "cursive": "𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃𝓐𝓑𝓒𝓓𝓔𝓕𝓖𝓗𝓘𝓙𝓚𝓛𝓜𝓝𝓞𝓟𝓠𝓡𝓢𝓣𝓤𝓥𝓦𝓧𝓨𝓩",
    "bold": "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙",
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

# # # # # # # # # # # # # # # # # #
# ENVIRONMENT VARIABLES
# # # # # # # # # # # # # # # # # #
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

if not BOT_TOKEN or not YOUTUBE_API_KEY or not OWNER_ID:
    raise RuntimeError("Missing required environment variables")

# # # # # # # # # # # # # # # # # #
# BOT STATE
# # # # # # # # # # # # # # # # # #
BOT_ENABLED = True
CURRENT_FONT = 'small' # Default to Small Caps

# # # # # # # # # # # # # # # # # #
# CACHE
# # # # # # # # # # # # # # # # # #
CACHE = {}
CACHE_TTL = 300 # 5 minutes

# # # # # # # # # # # # # # # # # #
# LANGUAGE TEXT
# # # # # # # # # # # # # # # # # #
TEXT = {
    "en": {"now_playing": "Now playing", "by": "by"},
    "hi": {"now_playing": "अब चल रहा है", "by": "द्वारा"},
    "es": {"now_playing": "Reproduciendo", "by": "por"},
}

def t(lang, key):
    return TEXT.get(lang, TEXT["en"]).get(key, TEXT["en"][key])

# # # # # # # # # # # # # # # # # #
# INLINE SEARCH
# # # # # # # # # # # # # # # # # #
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
    try:
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
                [InlineKeyboardButton(apply_style("▶ Play on YouTube"), url=yt)],
                [InlineKeyboardButton(apply_style("🎧 YouTube Music"), url=ytm)],
            ])

try:
    results.append(
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=apply_style(f"🎼 {title}"),
            description=apply_style(f"🙍🏻‍♀️ {channel}"),
            thumbnail_url=thumb,
            input_message_content=InputTextMessageContent(
                apply_style(
                    f"🎧 {t(lang, 'now_playing')}\n"
                    f"🎼 {title}\n"
                    f"🙍🏻‍♀️ {t(lang,'by')} {channel}"
                )
            ),
            reply_markup=keyboard,
        )
    )

    CACHE[query] = (results, now)
    await update.inline_query.answer(results, cache_time=300)

except Exception as e:
    print("❌ Inline error:", e)

# # # # # # # # # # # # # # # # # #
# OWNER COMMANDS
# # # # # # # # # # # # # # # # # #
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
    help_text = (
        "♫ *OpsXMusic Bot Help*\n\n"
        "*Search music anywhere:*\n"
        "`@opsxmusicbot song name`\n\n"
        "▶ *Play* → YouTube\n"
        "🎧 *YouTube Music*\n\n"
        "⚡ Fast • Clean • Global inline search\n\n"
        "✍️ *Font Management (Owner Only):*\n"
        "Use `/setfont <name>` to change style:\n"
        "• `small` (ɴᴏᴡ ᴘʟᴀʏ)\n"
        "• `cursive` (𝓒𝓾𝓻𝓼𝓲𝓿𝓮)\n"
        "• `bold` (𝐛𝐨𝐥𝐝)\n"
        "• `normal` (Default)\n\n"
        "💡 Tip: You don't need /start to use inline search."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def set_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CURRENT_FONT
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text(f"Current font: `{CURRENT_FONT}`. Usage: `/setfont bold`")
        return
    f_choice = context.args[0].lower()
    if f_choice in FONT_MAPS:
        CURRENT_FONT = f_choice
        await update.message.reply_text(apply_style(f"✅ Font set to {f_choice}"))
    else:
        await update.message.reply_text("❌ Font not found.")

# # # # # # # # # # # # # # # # # #
# MAIN
# # # # # # # # # # # # # # # # # #
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_bot))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CommandHandler("status", status_bot))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setfont", set_font))
    app.add_handler(InlineQueryHandler(inline_search))

    print("🤖 OpsXMusic running")
    app.run_polling()

if __name__ == "__main__":
    main()
