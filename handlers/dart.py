from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from db import user_collection
import datetime

async def throw_dart(update: Update, context: CallbackContext):
    """Send a dart throw and reward Astrites based on the result, with a daily limit."""
    user_id = update.effective_user.id
    
    # Retrieve user data
    user = await user_collection.find_one({"user_id": user_id})
    
    # Initialize daily stats if user is new
    today = datetime.date.today().isoformat()
    if not user:
        user = {"user_id": user_id, "astrites": 0, "dart_throws": {}, "last_throw_date": today}
        await user_collection.insert_one(user)

    # Fix KeyError by properly handling dart_throws dictionary
    dart_throws = user.get("dart_throws", {})
    dart_throws_today = dart_throws.get(today, 0)

    if dart_throws_today >= 5:
        await update.message.reply_text("𝗬𝗼𝘂 𝗵𝗮𝘃𝗲 𝗿𝗲𝗮𝗰𝗵𝗲𝗱 𝘁𝗵𝗲 𝗱𝗮𝗶𝗹𝘆 𝗹𝗶𝗺𝗶𝘁.")
        return

    # Send the dart throw
    message = await update.message.reply_dice(emoji="🎯")
    dart_value = message.dice.value  # Result of dart throw (1-6)

    # Astrites reward based on dart value
    rewards = {1: 2, 2: 4, 3: 6, 4: 8, 5: 10, 6: 15}
    astrites_won = rewards.get(dart_value, 0)

    # Update database: Astrites and throw count
    new_balance = user["astrites"] + astrites_won
    dart_throws[today] = dart_throws_today + 1  # Ensure the dictionary updates correctly
    await user_collection.update_one({"user_id": user_id}, {"$set": {"astrites": new_balance, "dart_throws": dart_throws, "last_throw_date": today}})

    # Notify the user with minimal message format
    await update.message.reply_text(f"𝗬𝗼𝘂 𝗲𝗮𝗿𝗻𝗲𝗱 Æ {astrites_won}")

# Register command with the bot application
