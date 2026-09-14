
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from db import collection as character_collection, user_collection, banned_users_collection, p2p_collection
from pymongo import ReturnDocument
import html
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

LOG_GROUP_ID = -1002594558957
LOG_TOPIC_ID = 5

async def is_user_banned(user_id: int) -> bool:
    return bool(await banned_users_collection.find_one({"user_id": user_id}))

def escape_html(text: str) -> str:
    return html.escape(str(text)) if text else ""

async def send_trade_log(context: ContextTypes.DEFAULT_TYPE, message: str):
    try:
        await context.bot.send_message(
            chat_id=LOG_GROUP_ID,
            text=message,
            parse_mode='HTML',
            message_thread_id=LOG_TOPIC_ID
        )
    except Exception as e:
        logger.error(f"Failed to send trade log: {e}")

async def handle_p2p_removal(user_id: int, character_id: int, remaining_count: int):
    try:
        listing = await p2p_collection.find_one({"seller_id": user_id, "character_id": character_id})
        if listing and remaining_count <= 0:
            await p2p_collection.delete_one({"seller_id": user_id, "character_id": character_id})
            logger.info(f"Removed {character_id} from P2P for user {user_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"P2P removal error: {e}")
        return False

async def initiate_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    sender_id = update.effective_user.id
    if await is_user_banned(sender_id):
        return await update.message.reply_text("🚫 You are banned from using this bot.")
    sender_name = update.effective_user.first_name

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        return await update.message.reply_text("Please reply to a user's message to initiate the trade.")

    receiver = update.message.reply_to_message.from_user
    receiver_id = receiver.id
    if await is_user_banned(receiver_id):
        return await update.message.reply_text("🚫 The recipient is banned and cannot receive trades.")
    receiver_name = receiver.first_name

    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /trade <your_character_id> <their_character_id>")

    try:
        sender_character_id = int(context.args[0].strip())
        receiver_character_id = int(context.args[1].strip())
    except ValueError:
        return await update.message.reply_text("Character IDs must be numbers.")

    if sender_character_id == receiver_character_id:
        return await update.message.reply_text("❌ You cannot trade the same character for itself.")

    if sender_id == receiver_id:
        return await update.message.reply_text("You cannot trade with yourself.")

    sender_character = await character_collection.find_one({"character_id": sender_character_id})
    receiver_character = await character_collection.find_one({"character_id": receiver_character_id})
    if not sender_character or not receiver_character:
        return await update.message.reply_text("One or both character IDs are invalid or not found.")

    sender_data = await user_collection.find_one({"user_id": sender_id, f"characters.{sender_character_id}": {"$gt": 0}})
    if not sender_data:
        return await update.message.reply_text("You don't own the character you want to trade.")

    receiver_data = await user_collection.find_one({"user_id": receiver_id, f"characters.{receiver_character_id}": {"$gt": 0}})
    if not receiver_data:
        return await update.message.reply_text("The other user doesn't own the character you want to receive.")

    keyboard = [[
        InlineKeyboardButton("✅ Confirm Trade",
            callback_data=f"confirm_trade:{sender_character_id}:{receiver_character_id}:{sender_id}:{receiver_id}"),
        InlineKeyboardButton("❌ Cancel Trade",
            callback_data=f"cancel_trade:{sender_character_id}:{receiver_character_id}:{sender_id}:{receiver_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    user_mention_sender = f'<a href="tg://user?id={sender_id}">{escape_html(sender_name)}</a>'
    user_mention_receiver = f'<a href="tg://user?id={receiver_id}">{escape_html(receiver_name)}</a>'

    message = await update.message.reply_to_message.reply_photo(
        photo=sender_character.get('image'),
        caption=(
            f"🔄 <b>Trade Proposal</b>\n\n"
            f"<b>{escape_html(sender_character.get('name', 'Unknown'))}</b> (ID: {sender_character_id})\n"
            f"From: {user_mention_sender}\n\n"
            f"⇅\n\n"
            f"<b>{escape_html(receiver_character.get('name', 'Unknown'))}</b> (ID: {receiver_character_id})\n"
            f"From: {user_mention_receiver}\n\n"
            f"{user_mention_receiver}, please confirm or cancel this trade!"
        ),
        parse_mode='HTML',
        reply_markup=reply_markup
    )

    log_message = (
        f"🔄 <b>Trade Initiated</b>\n\n"
        f"<b>From:</b> {user_mention_sender} (ID: {sender_id})\n"
        f"<b>Character:</b> {escape_html(sender_character['name'])} (ID: {sender_character_id})\n\n"
        f"<b>To:</b> {user_mention_receiver} (ID: {receiver_id})\n"
        f"<b>Character:</b> {escape_html(receiver_character['name'])} (ID: {receiver_character_id})"
    )
    await send_trade_log(context, log_message)

async def confirm_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    try:
        _, sender_char_id, receiver_char_id, sender_id, receiver_id = query.data.split(":")
        sender_char_id, receiver_char_id = int(sender_char_id), int(receiver_char_id)
        sender_id, receiver_id = int(sender_id), int(receiver_id)
    except ValueError:
        return await query.answer("Invalid trade data.", show_alert=True)

    if query.from_user.id != receiver_id:
        return await query.answer("❌ Only the receiving user can confirm this trade!", show_alert=True)

    if await is_user_banned(sender_id) or await is_user_banned(receiver_id):
        return await query.edit_message_caption("🚫 One of the users is banned.", parse_mode='HTML')

    await query.answer()

    sender_character = await character_collection.find_one({"character_id": sender_char_id})
    receiver_character = await character_collection.find_one({"character_id": receiver_char_id})
    if not sender_character or not receiver_character:
        return await query.edit_message_caption("One or both characters not found.", parse_mode='HTML')

    try:
        sender_deduct = await user_collection.find_one_and_update(
            {"user_id": sender_id, f"characters.{sender_char_id}": {"$gt": 0}},
            {"$inc": {f"characters.{sender_char_id}": -1}},
            return_document=ReturnDocument.AFTER
        )
        if not sender_deduct:
            return await query.edit_message_caption(
                "❌ Trade Failed: Sender no longer owns the character.", 
                parse_mode='HTML'
            )

        receiver_deduct = await user_collection.find_one_and_update(
            {"user_id": receiver_id, f"characters.{receiver_char_id}": {"$gt": 0}},
            {"$inc": {f"characters.{receiver_char_id}": -1}},
            return_document=ReturnDocument.AFTER
        )
        if not receiver_deduct:
            await user_collection.update_one(
                {"user_id": sender_id},
                {"$inc": {f"characters.{sender_char_id}": 1}}
            )
            return await query.edit_message_caption(
                "❌ Trade Failed: Receiver no longer owns the character.", 
                parse_mode='HTML'
            )

        await user_collection.update_one(
            {"user_id": sender_id},
            {"$inc": {f"characters.{receiver_char_id}": 1}}
        )
        await user_collection.update_one(
            {"user_id": receiver_id},
            {"$inc": {f"characters.{sender_char_id}": 1}}
        )

        if sender_deduct["characters"].get(str(sender_char_id), 0) <= 0:
            await user_collection.update_one(
                {"user_id": sender_id}, 
                {"$unset": {f"characters.{sender_char_id}": ""}}
            )
        
        if receiver_deduct["characters"].get(str(receiver_char_id), 0) <= 0:
            await user_collection.update_one(
                {"user_id": receiver_id}, 
                {"$unset": {f"characters.{receiver_char_id}": ""}}
            )

        p2p_updates = []
        if await handle_p2p_removal(sender_id, sender_char_id, sender_deduct["characters"].get(str(sender_char_id), 0)):
            p2p_updates.append(f"Removed {escape_html(sender_character['name'])} from sender's P2P listing")
        if await handle_p2p_removal(receiver_id, receiver_char_id, receiver_deduct["characters"].get(str(receiver_char_id), 0)):
            p2p_updates.append(f"Removed {escape_html(receiver_character['name'])} from receiver's P2P listing")

        success_message = (
            f"✅ <b>Trade Successful!</b>\n\n"
            f"<b>{escape_html(sender_character['name'])}</b> (ID: {sender_char_id}) ⇄ "
            f"<b>{escape_html(receiver_character['name'])}</b> (ID: {receiver_char_id})"
        )
        if p2p_updates:
            success_message += "\n\n<b>P2P Updates:</b>\n" + "\n".join([f"• {u}" for u in p2p_updates])

        await query.edit_message_caption(success_message, parse_mode='HTML')
        await send_trade_log(context, success_message + f"\n\nSender: {sender_id} Receiver: {receiver_id}")

    except Exception as e:
        logger.error(f"Trade failed: {e}", exc_info=True)
        await query.edit_message_caption(f"❌ Trade failed: {escape_html(str(e))}", parse_mode='HTML')

async def cancel_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        _, sender_char_id, receiver_char_id, sender_id, receiver_id = query.data.split(":")
        sender_id, receiver_id = int(sender_id), int(receiver_id)
    except ValueError:
        return await query.answer("Invalid trade data.", show_alert=True)

    if query.from_user.id not in [sender_id, receiver_id]:
        return await query.answer("❌ Only the trade participants can cancel this trade!", show_alert=True)

    await query.answer("Trade cancelled", show_alert=True)
    await query.edit_message_caption("❌ Trade Cancelled", parse_mode='HTML')
    await send_trade_log(context, f"❌ Trade Cancelled by {query.from_user.id} for trade {sender_char_id} ⇄ {receiver_char_id}")

def get_trade_handlers():
    return [
        CallbackQueryHandler(confirm_trade, pattern="^confirm_trade"),
        CallbackQueryHandler(cancel_trade, pattern="^cancel_trade")
    ]
