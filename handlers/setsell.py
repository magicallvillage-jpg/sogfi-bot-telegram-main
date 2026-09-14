
import time
import math
import html
import logging
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import user_collection, p2p_collection, collection as characters_collection, banned_users_collection

# --- Configuration ---
RARITY_PRICE_LIMITS = {
    "🔮 Vortex": (180, 700),
    "🎐 Celestiax": (500, 850),
    "🪩 Harmony": (800, 1400),
    "🎭 Eternal": (3000, 7000),
    "🍭 Elixir": (1000, 2100)
}

CHANNEL_ID = -1003645464827
CHANNEL_USERNAME = "p2p_Takers"
ITEMS_PER_PAGE = 8

# Initialize Notification Bot
NOTIFICATION_BOT_TOKEN = "7645454186:AAE-4EjsOIadwbQXyVhsxoBJC4X65m92Xb8"
notification_bot = telegram.Bot(token=NOTIFICATION_BOT_TOKEN)

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---

async def is_user_banned(user_id: int) -> bool:
    banned_user = await banned_users_collection.find_one({"user_id": user_id})
    return bool(banned_user)

def escape_html(text: str) -> str:
    """Helper to escape HTML characters."""
    return html.escape(str(text)) if text else ""

def extract_emoji_from_rarity(rarity_text):
    rarity_str = str(rarity_text).strip()
    return rarity_str[0] if rarity_str and ord(rarity_str[0]) > 127 else ''

def determine_media_type(character):
    if not character.get('image'):
        return "image" # Fallback
    ext = character['image'].split('.')[-1].lower()
    return "image" if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "video"

# --- Command Handlers ---

async def setsell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    if await is_user_banned(user_id):
        return

    # Check arguments
    if not context.args or len(context.args) != 2:
        help_text = (
            "📖 <b>How to Sell a Character</b>\n\n"
            "<b>Usage:</b>\n"
            "• <code>/setsell &lt;character_id&gt; &lt;price&gt;</code>\n\n"
            "<b>Currency:</b>\n"
            "• All trades use <b>ASTRITES</b>.\n"
            "• Set the price in ASTRITES, within the allowed rarity range.\n\n"
            "<b>Rarity Price Limits:</b>\n"
            "• 🔮 Vortex: Æ 180 - Æ 700\n"
            "• 🎐 Celestiax: Æ 500 - Æ 850\n"
            "• 🪩 Harmony: Æ 800 - Æ 1400\n"
            "• 🎭 Eternal: Æ 3000 - Æ 7000\n"
            "• 🍭 Elixir: Æ 1000 - Æ 2100\n\n"
            "<b>Where it appears:</b>\n"
            "• Listed in the P2P market and the market channel.\n"
            "• Buyers use the <b>Buy Now</b> button or link.\n"
        )
        return await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

    try:
        character_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        return await update.message.reply_text("❌ <b>Error:</b> Use numeric IDs and amounts!", parse_mode=ParseMode.HTML)

    if amount <= 0:
        return await update.message.reply_text("❌ <b>Error:</b> Amount must be positive!", parse_mode=ParseMode.HTML)

    # Validate Ownership (Must have count > 0)
    user = await user_collection.find_one({
        "user_id": user_id, 
        f"characters.{character_id}": {"$gt": 0}
    })
    
    if not user:
        return await update.message.reply_text(
            f"❌ <b>Error:</b> You don't own ID <code>{character_id}</code> or have no copies left!",
            parse_mode=ParseMode.HTML
        )

    # Fetch Character Data
    character = await characters_collection.find_one({"character_id": character_id})
    if not character:
        return await update.message.reply_text("❌ <b>Error:</b> Character data not found.", parse_mode=ParseMode.HTML)

    # Check Price Limits
    char_rarity = character.get("rarity", "")
    if char_rarity in RARITY_PRICE_LIMITS:
        min_p, max_p = RARITY_PRICE_LIMITS[char_rarity]
        if amount < min_p or amount > max_p:
            return await update.message.reply_text(
                f"❌ <b>Price Limit Violation</b>\n\n"
                f"<blockquote>For <b>{escape_html(char_rarity)}</b>, price must be between:\n"
                f"📉 Min: <b>Æ {min_p}</b>\n"
                f"📈 Max: <b>Æ {max_p}</b></blockquote>",
                parse_mode=ParseMode.HTML
            )

    # Check for existing listing
    existing = await p2p_collection.find_one({"seller_id": user_id, "character_id": character_id})
    
    # Clean up old channel message if exists
    if existing and "chan_msg_id" in existing:
        try:
            async with notification_bot:
                await notification_bot.delete_message(chat_id=CHANNEL_ID, message_id=existing["chan_msg_id"])
        except Exception as e:
            logger.warning(f"Failed to delete old channel message: {e}")

    # Update or Insert DB Listing
    current_time = int(time.time())
    
    if existing:
        listing_id = existing['_id']
        await p2p_collection.update_one(
            {"_id": listing_id},
            {"$set": {"price": amount, "timestamp": current_time}}
        )
        status_text = "Listing Updated"
    else:
        result = await p2p_collection.insert_one({
            "seller_id": user_id,
            "character_id": character_id,
            "price": amount,
            "timestamp": current_time
        })
        listing_id = result.inserted_id
        status_text = "Listed Successfully"

    # Prepare Success Message
    webapp_url = f"https://t.me/Takers_AstriSwap_bot/Market?startapp={str(listing_id)}"
    rarity_emoji = extract_emoji_from_rarity(char_rarity)
    
    anime_title = escape_html(character.get('anime', 'Unknown'))
    char_name = escape_html(character['name'])

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 View Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("🛒 Buy Now", url=webapp_url)]
    ])

    success_caption = (
        f"✅ <b>{status_text}</b>\n\n"
        f"<blockquote>"
        f"<b>Anime:</b> {anime_title}\n"
        f"<b>Name:</b> {rarity_emoji} {char_name}\n"
        f"<b>ID:</b> <code>{character_id}</code> | <b>Price:</b> Æ {amount}"
        f"</blockquote>\n"
        f"🔗 <b>Buy:</b> <a href='{webapp_url}'>Click to Purchase</a>\n\n"
        f"<i>Use /p2p or the P2P WebApp to browse trades.</i>"
    )

    media_type = determine_media_type(character)
    
    try:
        if media_type == "image":
            await update.message.reply_photo(
                photo=character['image'],
                caption=success_caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await update.message.reply_video(
                video=character['image'],
                caption=success_caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Error sending success message: {e}")
        await update.message.reply_text(success_caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # Post to Channel
    try:
        chan_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Buy Now", url=webapp_url)]])
        chan_caption = (
            f"🚀 <b>New Market Listing</b>\n\n"
            f"<blockquote>"
            f"<b>Anime:</b> {anime_title}\n"
            f"<b>Character:</b> {rarity_emoji} {char_name}\n"
            f"<b>Price:</b> Æ {amount} (ASTRITES)\n"
            f"<b>Seller:</b> {escape_html(first_name)} (<code>{user_id}</code>)"
            f"</blockquote>"
        )
        
        async with notification_bot:
            if media_type == "image":
                chan_msg = await notification_bot.send_photo(
                    CHANNEL_ID,
                    photo=character['image'],
                    caption=chan_caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=chan_kb
                )
            else:
                chan_msg = await notification_bot.send_video(
                    CHANNEL_ID,
                    video=character['image'],
                    caption=chan_caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=chan_kb
                )
            
            # Update DB with channel message ID for future deletion
            await p2p_collection.update_one(
                {"_id": listing_id},
                {"$set": {"chan_msg_id": chan_msg.message_id}}
            )
    except Exception as e:
        logger.error(f"Failed to post to channel: {e}")


async def removesell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await is_user_banned(user_id):
        return

    if not context.args:
        guide = (
            "🗑 <b>Remove a Listing</b>\n\n"
            "<b>Usage:</b>\n"
            "• <code>/removesell &lt;character_id&gt;</code>\n\n"
            "<b>Details:</b>\n"
            "• Removes your sale listing for that character.\n"
            "• Also deletes the listing message from the market channel.\n"
            "• Character stays in your inventory.\n"
        )
        return await update.message.reply_text(guide, parse_mode=ParseMode.HTML)

    try:
        char_id = int(context.args[0])
        listing = await p2p_collection.find_one({"seller_id": user_id, "character_id": char_id})
        
        if listing:
            # Try to delete channel message
            if "chan_msg_id" in listing:
                try:
                    async with notification_bot:
                        await notification_bot.delete_message(
                            chat_id=CHANNEL_ID,
                            message_id=listing["chan_msg_id"]
                        )
                except Exception as e:
                    logger.warning(f"Failed to delete channel msg for remove: {e}")
            
            # Delete from DB
            await p2p_collection.delete_one({"_id": listing["_id"]})
            
            await update.message.reply_text(
                f"✅ Removed listing for ID <code>{char_id}</code> from P2P market!",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("❌ <b>Error:</b> Listing not found.", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ <b>Error:</b> Invalid ID format.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error in removesell: {e}")
        await update.message.reply_text("❌ An error occurred.", parse_mode=ParseMode.HTML)


async def mysell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await is_user_banned(user_id):
        return

    # Determine page number
    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])

    total = await p2p_collection.count_documents({"seller_id": user_id})
    
    if total == 0:
        guide = (
            "📦 <b>Your Listings</b>\n\n"
            "<b>Usage:</b>\n"
            "• <code>/mysell</code> – Show page 1 of your listings.\n"
            "• <code>/mysell &lt;page&gt;</code> – Jump to a specific page.\n\n"
            "<i>You have no active listings yet.</i>"
        )
        return await update.message.reply_text(guide, parse_mode=ParseMode.HTML)

    total_pages = math.ceil(total / ITEMS_PER_PAGE)
    
    # Validate page range
    if page < 1: page = 1
    if page > total_pages: page = total_pages

    listings = await p2p_collection.find({"seller_id": user_id}) \
        .sort("timestamp", -1) \
        .skip((page - 1) * ITEMS_PER_PAGE) \
        .limit(ITEMS_PER_PAGE) \
        .to_list(length=ITEMS_PER_PAGE)

    msg = f"📦 <b>Your Active Listings ({page}/{total_pages})</b>\n\n"
    
    for item in listings:
        char = await characters_collection.find_one({"character_id": item['character_id']})
        if char:
            emoji = extract_emoji_from_rarity(char.get('rarity', ''))
            anime_safe = escape_html(char.get('anime', 'Unknown'))
            name_safe = escape_html(char.get('name', 'Unknown'))
            
            msg += (
                f"<blockquote><b>{anime_safe}</b>\n"
                f"{emoji} {name_safe} | 🆔 <code>{item['character_id']}</code> | "
                f"Æ {item['price']}</blockquote>\n"
            )

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"mysell_{page-1}_{user_id}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ▶", callback_data=f"mysell_{page+1}_{user_id}"))

    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([nav]) if nav else None
    )


async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    try:
        data_parts = query.data.split("_")
        if len(data_parts) != 3:
            await query.answer("Invalid data", show_alert=True)
            return

        page, owner_id = int(data_parts[1]), int(data_parts[2])

        if query.from_user.id != owner_id:
            return await query.answer("❌ This is not your listing!", show_alert=True)

        total = await p2p_collection.count_documents({"seller_id": owner_id})
        total_pages = math.ceil(total / ITEMS_PER_PAGE)
        
        # Safety check if pages changed
        if page < 1: page = 1
        if page > total_pages: page = total_pages

        listings = await p2p_collection.find({"seller_id": owner_id}) \
            .sort("timestamp", -1) \
            .skip((page - 1) * ITEMS_PER_PAGE) \
            .limit(ITEMS_PER_PAGE) \
            .to_list(length=ITEMS_PER_PAGE)

        msg = f"📦 <b>Your Active Listings ({page}/{total_pages})</b>\n\n"
        for item in listings:
            char = await characters_collection.find_one({"character_id": item['character_id']})
            if char:
                emoji = extract_emoji_from_rarity(char.get('rarity', ''))
                anime_safe = escape_html(char.get('anime', 'Unknown'))
                name_safe = escape_html(char.get('name', 'Unknown'))
                
                msg += (
                    f"<blockquote><b>{anime_safe}</b>\n"
                    f"{emoji} {name_safe} | 🆔 <code>{item['character_id']}</code> | "
                    f"Æ {item['price']}</blockquote>\n"
                )

        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"mysell_{page-1}_{owner_id}"))
        if page < total_pages:
            nav.append(InlineKeyboardButton("Next ▶", callback_data=f"mysell_{page+1}_{owner_id}"))

        await query.message.edit_text(
            msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([nav]) if nav else None
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Pagination error: {e}")
        await query.answer("Error handling pagination", show_alert=True)


async def p2p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await is_user_banned(user_id):
        return

    help_text = (
        "🌐 <b>ASTRITES P2P Market</b>\n\n"
        "<b>What is this?</b>\n"
        "• A peer‑to‑peer market where players trade characters using <b>ASTRITES</b>.\n\n"
        "<b>How to use:</b>\n"
        "• Open the P2P WebApp:\n"
        "  <a href='https://t.me/Takers_AstriSwap_bot/P2P'>https://t.me/Takers_AstriSwap_bot/P2P</a>\n"
        "• Browse buy and complete trades directly in the WebApp.\n\n"
        "<b>Related commands:</b>\n"
        "• <code>/setsell &lt;id&gt; &lt;price&gt;</code> – List your character for sale.\n"
        "• <code>/mysell</code> – View your active listings.\n"
        "• <code>/removesell &lt;id&gt;</code> – Remove one of your listings."
    )

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🌐 Open P2P Market", url="https://t.me/Takers_AstriSwap_bot/P2P")]]
    )

    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML, reply_markup=kb)
