import aiohttp
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from config import SUDO_USERS
from db import user_collection

BOT_TOKEN = "8383842291:AAGphJkXcL9fygOyaeJrRqv59ZGHvoiVHLU"
LOG_CHAT_ID = -1003136634292
LOG_TOPIC_ID = 1808
ALLOWED_CHAT_ID = -1002655715837

async def send_log(src_id, dst_id, transferred_by, inc, src_name=None, dst_name=None):
    char_list = "\n".join([f"> `characters.{k}` += `{v}`" for k, v in inc.items()])
    src_link = f"[{src_name or src_id}](tg://user?id={src_id})"
    dst_link = f"[{dst_name or dst_id}](tg://user?id={dst_id})"
    by_link = f"[{transferred_by}](tg://user?id={transferred_by})"
    message = f"""
*✅ Transfer Complete*

*From:* {src_link}  
*To:* {dst_link}  
*Transferred by:* {by_link}

> Source harem cleared.  
> Destination incremented with merged values.
"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": LOG_CHAT_ID,
        "message_thread_id": LOG_TOPIC_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

async def transfer_character_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if user_id not in SUDO_USERS or chat_id != ALLOWED_CHAT_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command here.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /transfer_harem <source_id> <destination_id>")
        return
    try:
        src = int(context.args[0])
        dst = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid user IDs. Please enter numeric values.")
        return
    cur = user_collection.find(
        {"user_id": {"$in": [src, dst]}},
        {"_id": 0, "user_id": 1, "characters": 1}
    )
    s = None
    d = None
    async for doc in cur:
        if doc.get("user_id") == src:
            s = doc
        elif doc.get("user_id") == dst:
            d = doc
    if not s:
        await update.message.reply_text(f"⚠️ Source user {src} not found.")
        await send_log(src, dst, user_id, {}, src_name=None, dst_name=None)
        return
    chars_dst = {
        str(k): int(v)
        for k, v in (d.get("characters", {}) if d else {}).items()
        if v is not None
    }
    inc = {}
    for k, v in (s.get("characters", {}) or {}).items():
        try:
            add = int(v or 0)
        except Exception:
            add = 0
        if add != 0:
            key = str(k)
            inc[key] = inc.get(key, 0) + add
    if not inc:
        await update.message.reply_text("✅ No characters to transfer.")
        await send_log(src, dst, user_id, {}, src_name=None, dst_name=None)
        return
    await user_collection.update_one({"user_id": dst}, {"$inc": {f"characters.{k}": v for k, v in inc.items()}}, upsert=True)
    await user_collection.update_one({"user_id": src}, {"$unset": {"characters": ""}})
    await update.message.reply_text(f"✅ Transferred harem from {src} to {dst} and cleared source.")
    try:
        src_name = update.effective_chat.get_member(src).user.full_name
    except:
        src_name = None
    try:
        dst_name = update.effective_chat.get_member(dst).user.full_name
    except:
        dst_name = None
    await send_log(src, dst, user_id, inc, src_name=src_name, dst_name=dst_name)

# application.add_handler(CommandHandler("transfer_harem", transfer_harem))


transfer_handler = CommandHandler("transfer", transfer_character_collection, block=False)

def get_transfer_handler():
    return [transfer_handler]
