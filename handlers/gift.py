
from db import user_collection, get_character_by_id, banned_users_collection, p2p_collection
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import html
import logging
from config import SUDO_USERS
import telegram
from pymongo import ReturnDocument

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def send_log_to_group(context: ContextTypes.DEFAULT_TYPE, message: str):
    try:
        await context.bot.send_message(
            chat_id=-1002594558957,
            message_thread_id=2,
            text=message,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to send log to group: {e}")

async def is_user_banned(user_id: int) -> bool:
    banned_user = await banned_users_collection.find_one({"user_id": user_id})
    return bool(banned_user)

def escape_html(text: str) -> str:
    return html.escape(str(text)) if text else ""

async def handle_p2p_removal(user_id: int, character_id: int, remaining_count: int):
    try:
        listing = await p2p_collection.find_one({
            "seller_id": user_id,
            "character_id": character_id
        })
        
        if listing:
            if remaining_count <= 0:
                await p2p_collection.delete_one({
                    "seller_id": user_id,
                    "character_id": character_id
                })
                logger.info(f"Removed character {character_id} from P2P marketplace for user {user_id}")
                return True
            else:
                logger.info(f"User {user_id} still has {remaining_count} of character {character_id}, keeping P2P listing")
                return False
        
        return False
    except Exception as e:
        logger.error(f"Error handling P2P removal: {e}")
        return False

async def gift_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if await is_user_banned(sender_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    sender_name = update.effective_user.first_name
    
    if not update.message.reply_to_message:
        return await update.message.reply_text("Please reply to a user's message to gift a character.")
    
    receiver_id = update.message.reply_to_message.from_user.id
    receiver_name = update.message.reply_to_message.from_user.first_name

    if await is_user_banned(receiver_id):
        await update.message.reply_text("🚫 The recipient is banned and cannot receive gifts.")
        return

    if not context.args:
        return await update.message.reply_text("Please provide the character ID you want to gift.")
    
    try:
        character_id = int(context.args[0].strip())
    except ValueError:
        return await update.message.reply_text("Character ID must be a number.")

    if sender_id == receiver_id:
        return await update.message.reply_text("You cannot gift characters to yourself.")

    char = await get_character_by_id(character_id)
    if not char:
        return await update.message.reply_text("Invalid character ID or character not found.")
    
    character_name = char['name']
    character_image = char['image']
    user_mention_receiver = f'<a href="tg://user?id={receiver_id}">{escape_html(receiver_name)}</a>'

    sender_data = await user_collection.find_one({
        "user_id": sender_id,
        f"characters.{character_id}": {"$gt": 0}
    })
    
    if not sender_data:
        return await update.message.reply_text("You don't own this character or have enough copies to gift.")

    sender_character_count = sender_data.get("characters", {}).get(str(character_id), 0)
    if sender_character_count <= 0:
        return await update.message.reply_text("You don't have enough copies of this character to gift.")

    receiver_data = await user_collection.find_one({"user_id": receiver_id})
    if not receiver_data:
        receiver_data = {
            "user_id": receiver_id,
            "characters": {},
            "first_name": receiver_name,
            "username": update.message.reply_to_message.from_user.username
        }
        await user_collection.insert_one(receiver_data)

    keyboard = [
        [InlineKeyboardButton("✅ Confirm Gift", callback_data=f"confirm_gift:{character_id}:{receiver_id}:{sender_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_gift")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    return await update.message.reply_photo(
        photo=character_image,
        caption=(
            f"🎁 <b>Gift Confirmation</b>\n\n"
            f"<blockquote>• Character: <b>{escape_html(character_name)}</b> (ID: {character_id})\n"
            f"• To: {user_mention_receiver}</blockquote>\n\n"
            f"<i>You have {sender_character_count} copy/copies of this character.</i>"
        ),
        parse_mode='HTML',
        reply_markup=reply_markup,
    )

async def confirm_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "cancel_gift":
        await query.answer(text="❌ Gift transaction cancelled.", show_alert=True)
        await query.edit_message_caption("❌ Gift transaction cancelled.", parse_mode='HTML')
        return
    
    parts = query.data.split(":")
    if len(parts) != 4 or parts[0] != "confirm_gift":
        await query.answer(text="Invalid action.", show_alert=True)
        return
    
    _, character_id_str, receiver_id_str, sender_id_str = parts
    
    try:
        character_id = int(character_id_str)
        receiver_id = int(receiver_id_str)
        sender_id = int(sender_id_str)
    except ValueError:
        await query.answer(text="Invalid ID format.", show_alert=True)
        return

    if query.from_user.id != sender_id:
        await query.answer(text="🚫 You are not authorized to confirm this gift.", show_alert=True)
        return

    if await is_user_banned(user_id):
        await query.answer(text="🚫 You are banned from using this bot.", show_alert=True)
        return
    
    if await is_user_banned(receiver_id):
        await query.answer(text="🚫 The recipient is banned.", show_alert=True)
        return

    await query.answer()
    await query.edit_message_caption("🔄 Processing gift transfer...", parse_mode='HTML')

    char = await get_character_by_id(character_id)
    if not char:
        await query.edit_message_caption("Character not found.", parse_mode='HTML')
        return
    character_name = char['name']

    try:
        updated_sender = await user_collection.find_one_and_update(
            {
                "user_id": sender_id,
                f"characters.{character_id}": {"$gt": 0}
            },
            {
                "$inc": {f"characters.{character_id}": -1}
            },
            return_document=ReturnDocument.AFTER
        )

        if not updated_sender:
            await query.edit_message_caption(
                "❌ <b>Gift Failed:</b> You do not have enough copies of this character anymore.",
                parse_mode='HTML'
            )
            return

        remaining_count = updated_sender.get("characters", {}).get(str(character_id), 0)

        receiver_display_name = str(receiver_id)
        existing_receiver = await user_collection.find_one({"user_id": receiver_id}, {"first_name": 1})
        if existing_receiver:
            receiver_display_name = existing_receiver.get("first_name", str(receiver_id))
        
        await user_collection.update_one(
            {"user_id": receiver_id},
            {
                "$inc": {f"characters.{character_id}": 1},
                "$setOnInsert": {
                    "first_name": receiver_display_name,
                    "username": query.from_user.username
                }
            },
            upsert=True
        )

        if remaining_count == 0:
            await user_collection.update_one(
                {"user_id": sender_id},
                {"$unset": {f"characters.{character_id}": ""}}
            )

        p2p_removals = []
        sender_p2p_removed = await handle_p2p_removal(sender_id, character_id, remaining_count)
        
        sender_name_log = updated_sender.get('first_name', 'Unknown')
        if sender_p2p_removed:
            p2p_removals.append(f"Removed {character_name} from {sender_name_log}'s P2P listing")

        user_mention_receiver = f'<a href="tg://user?id={receiver_id}">{escape_html(receiver_display_name)}</a>'
        user_mention_sender = f'<a href="tg://user?id={sender_id}">{escape_html(sender_name_log)}</a>'
        
        success_message = (
            f"✅ <b>Gift Successful!</b>\n\n"
            f"<blockquote>• Character: <b>{escape_html(character_name)}</b> (ID: {character_id})\n"
            f"• Sent to: {user_mention_receiver}</blockquote>\n\n"
            f"<i>Thank you for using the gifting system!</i>"
        )
        
        if p2p_removals:
            success_message += f"\n\n<b>P2P Updates:</b>\n" + "\n".join(f"• {removal}" for removal in p2p_removals)
        
        await query.edit_message_caption(success_message, parse_mode='HTML')
        
        log_message = (
            f"🎁 <b>Gift Log</b>\n\n"
            f"<b>Character:</b> {escape_html(character_name)} (ID: {character_id})\n"
            f"<b>From:</b> {user_mention_sender} (ID: {sender_id})\n"
            f"<b>To:</b> {user_mention_receiver} (ID: {receiver_id})\n"
            f"<b>Date:</b> {escape_html(update.effective_message.date.strftime('%Y-%m-%d %H:%M:%S'))}"
        )
        
        if p2p_removals:
            log_message += f"\n\n<b>P2P Updates:</b>\n" + "\n".join(f"• {removal}" for removal in p2p_removals)
        
        await send_log_to_group(context, log_message)

    except Exception as e:
        logger.error(f"Gift failed: {e}", exc_info=True)
        await query.edit_message_caption(
            f"⚠️ An error occurred during the gift transfer.\nCode: <code>{escape_html(str(e))}</code>",
            parse_mode='HTML'
        )
        
        log_message = (
            f"❌ <b>Gift Failed</b>\n\n"
            f"<b>Error:</b> {escape_html(str(e))}\n"
            f"<b>From:</b> {sender_id}\n"
            f"<b>To:</b> {receiver_id}\n"
            f"<b>Character:</b> {character_id}"
        )
        await send_log_to_group(context, log_message)

async def give_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if await is_user_banned(sender_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    group_id = -1002655715837

    if update.effective_chat.id != group_id:
        await update.message.reply_text("❌ This command can only be used in the authorized group.")
        return

    if sender_id not in SUDO_USERS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text(
            "Usage:\n"
            "• Reply to a user: <code>/give [character_id]</code>\n"
            "• Or specify both: <code>/give [user_id] [character_id]</code>",
            parse_mode='HTML'
        )
        return

    try:
        if context.args and len(context.args) >= 2:
            receiver_id = int(context.args[0].strip())
            character_id = int(context.args[1].strip())
        else:
            if not update.message.reply_to_message:
                await update.message.reply_text("Please reply to a user or provide both IDs.")
                return
            
            receiver_id = update.message.reply_to_message.from_user.id
            character_id = int(context.args[0].strip()) if context.args else None

        if character_id is None:
            await update.message.reply_text("Please provide a character ID.")
            return

    except ValueError:
        await update.message.reply_text("Invalid ID format. Both user ID and character ID must be numbers.")
        return

    if await is_user_banned(receiver_id):
        await update.message.reply_text("🚫 The recipient is banned and cannot receive gifts.")
        return

    char = await get_character_by_id(character_id)
    if not char:
        await update.message.reply_text("Invalid character ID or character not found.")
        return

    character_name = char['name']
    character_image = char['image']

    receiver_data = await user_collection.find_one({"user_id": receiver_id})
    receiver_name = None
    
    if receiver_data:
        receiver_name = receiver_data.get("first_name", str(receiver_id))
    else:
        if update.message.reply_to_message:
            receiver_name = update.message.reply_to_message.from_user.first_name
        else:
            receiver_name = str(receiver_id)

    try:
        await user_collection.update_one(
            {"user_id": receiver_id},
            {
                "$inc": {f"characters.{character_id}": 1},
                "$setOnInsert": {
                    "first_name": receiver_name,
                    "username": update.message.reply_to_message.from_user.username if update.message.reply_to_message else None
                }
            },
            upsert=True
        )

        user_mention_receiver = f'<a href="tg://user?id={receiver_id}">{escape_html(receiver_name)}</a>'
        user_mention_sender = f'<a href="tg://user?id={sender_id}">{escape_html(update.effective_user.first_name)}</a>'
        
        log_message = (
            f"🎁 <b>Admin Gift Log</b>\n\n"
            f"<b>Character:</b> {escape_html(character_name)} (ID: {character_id})\n"
            f"<b>Given to:</b> {user_mention_receiver} (ID: {receiver_id})\n"
            f"<b>Added by:</b> {user_mention_sender} (ID: {sender_id})\n"
            f"<b>Date:</b> {escape_html(update.effective_message.date.strftime('%Y-%m-%d %H:%M:%S'))}"
        )
        await send_log_to_group(context, log_message)

        await update.message.reply_photo(
            photo=character_image,
            caption=(
                f"🎁 <b>Admin Gift Successful</b>\n\n"
                f"• Character: <b>{escape_html(character_name)}</b> (ID: {character_id})\n"
                f"• Given to: {user_mention_receiver}\n"
                f"• Added by: {user_mention_sender}"
            ),
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Admin gift failed: {e}", exc_info=True)
        await update.message.reply_text(
            f"Failed to gift character: {e}\n\n"
            "Please check the IDs and try again.",
            parse_mode='HTML'
        )
        
        log_message = (
            f"❌ <b>Admin Gift Failed</b>\n\n"
            f"<b>Error:</b> {escape_html(str(e))}\n"
            f"<b>Admin:</b> {sender_id}\n"
            f"<b>Target:</b> {receiver_id}\n"
            f"<b>Character:</b> {character_id}\n"
            f"<b>Date:</b> {escape_html(update.effective_message.date.strftime('%Y-%m-%d %H:%M:%S'))}"
        )
        await send_log_to_group(context, log_message)
