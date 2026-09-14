from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from db import user_collection
from config import SUDO_USERS  # Import SUDO_USERS restriction

async def remove_character_from_user(user_id: int, character_id: str):
    """Removes a character from a specific user's collection."""
    try:
        user_data = await user_collection.find_one({"user_id": user_id})

        if not user_data or character_id not in user_data.get("characters", {}):
            return f"❌ User {user_id} does not own Character {character_id}."

        await user_collection.update_one({"user_id": user_id}, {"$unset": {f"characters.{character_id}": ""}})
        return f"✅ Removed Character {character_id} from User {user_id}."
    except Exception as e:
        return f"⚠️ Error removing character: {e}"

async def cdelete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /cdelete command to remove a character from a specific user."""
    user_id = update.message.from_user.id
    
    # Check if the user is in SUDO_USERS
    if user_id not in SUDO_USERS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return
    
    # Check if the command is used via reply or direct arguments
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("Usage: /cdelete <character_id> <user_id> OR reply with /cdelete <character_id>")
        return
    
    character_id = context.args[0] if context.args else None

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id  # Get user ID from reply
    elif len(context.args) > 1:
        target_user_id = int(context.args[1])  # Get user ID from arguments
    else:
        await update.message.reply_text("❌ Please provide a user ID or reply to a user.")
        return

    result_message = await remove_character_from_user(target_user_id, character_id)
    await update.message.reply_text(result_message)

def register_handlers(application):
    """Registers /cdelete command in the bot."""
    application.add_handler(CommandHandler("cdelete", cdelete_command))
