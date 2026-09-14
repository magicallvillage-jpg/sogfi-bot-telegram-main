from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from db import user_collection
from config import SUDO_USERS  # Importing SUDO_USERS from config.py

async def remove_character_globally(character_id: str):
    """Removes a character globally from all users who own it."""
    try:
        users_with_character = user_collection.find({"characters." + character_id: {"$exists": True}})

        async for user in users_with_character:
            user_id = user["user_id"]
            await user_collection.update_one({"user_id": user_id}, {"$unset": {f"characters.{character_id}": ""}})

        return f"Character {character_id} has been removed from all users."
    except Exception as e:
        return f"Error removing character globally: {e}"

async def ckill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /ckill command to remove a character globally, restricted to SUDO_USERS."""
    user_id = update.message.from_user.id
    
    # Check if user is in SUDO_USERS
    if user_id not in SUDO_USERS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return
    
    # Ensure the command has an argument
    if not context.args:
        await update.message.reply_text("Usage: /ckill <character_id>")
        return
    
    character_id = context.args[0]
    result_message = await remove_character_globally(character_id)  # Corrected function call
    await update.message.reply_text(result_message)

def register_handlers(application):
    """Registers command handlers in the bot application."""
    application.add_handler(CommandHandler("ckill", ckill_command))
