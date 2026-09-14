from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes, CallbackContext
from db import banned_users_collection
from config import SUDO_USERS

# -------------------- Banning System -------------------- #

async def is_user_banned(user_id: int) -> bool:
    """Check if a user is banned."""
    return await banned_users_collection.count_documents({"user_id": user_id}) > 0

async def ban_user(user_id: int):
    """Ban a user without deleting their data."""
    if not await is_user_banned(user_id):
        await banned_users_collection.insert_one({"user_id": user_id})
        return f"🚫 User {user_id} has been banned."
    return f"⚠️ User {user_id} is already banned."

async def unban_user(user_id: int):
    """Unban a user."""
    await banned_users_collection.delete_one({"user_id": user_id})
    return f"✅ User {user_id} has been unbanned."

async def banbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /banbot command."""
    admin_id = update.message.from_user.id
    if admin_id not in SUDO_USERS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("⚠️ Invalid user ID format.")
            return
    else:
        await update.message.reply_text("Usage: /banbot <user_id> or reply to the user.")
        return

    result_message = await ban_user(target_user_id)
    await update.message.reply_text(result_message)

async def unbanbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unbanbot command."""
    admin_id = update.message.from_user.id
    if admin_id not in SUDO_USERS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("⚠️ Invalid user ID format.")
            return
    else:
        await update.message.reply_text("Usage: /unbanbot <user_id> or reply to the user.")
        return

    result_message = await unban_user(target_user_id)
    await update.message.reply_text(result_message)

async def check_ban(update: Update, context: CallbackContext):
    """Check if a user is banned before processing commands."""
    user_id = update.message.from_user.id
    if await is_user_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return False
    return True

# -------------------- Match Command -------------------- #

async def current_match():
    """Fetch current match details (dummy data)."""
    return "🏏 Current Match: Team A vs Team B\nScore: 150/3 (Overs: 17)"

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display current match if no arguments are provided."""
    if context.args:
        await update.message.reply_text(f"You entered: {' '.join(context.args)}")
    else:
        match_info = await current_match()
        keyboard = [[InlineKeyboardButton("❌ Clear", callback_data="clear_message")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(match_info, reply_markup=reply_markup)

async def clear_callback(update: Update, context: CallbackContext):
    """Remove the match status message."""
    await update.callback_query.message.delete()

# -------------------- Handler Registration -------------------- #

def register_handlers(application):
    """Register bot handlers."""
    application.add_handler(CommandHandler("banbot", banbot_command))
    application.add_handler(CommandHandler("unbanbot", unbanbot_command))
    application.add_handler(CommandHandler("match", match_command))
    application.add_handler(CallbackQueryHandler(clear_callback, pattern="clear_message"))
