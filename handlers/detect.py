from telegram import Update
from telegram.ext import ContextTypes
from db import collection as character_collection, user_collection
import random
import html
from typing import List, Dict

async def detect_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Please provide a character ID. Usage: /detect <character_id>")

    try:
        character_id = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("Invalid character ID. Please provide a number.")

    # Fetch character from MongoDB
    character = await character_collection.find_one({"character_id": character_id})
    if not character:
        return await update.message.reply_text("Character not found.")

    # Extract character details
    anime = character.get("anime", "Unknown")
    char_id = character.get("character_id")
    event = character.get("event", "")
    event_emoji = character.get("event_emoji", "")
    image_url = character.get("image")
    name = character.get("name", "Unknown")
    rarity = character.get("rarity", "Unknown")
    uploader_name = character.get("uploader_name", "Unknown")

    # Build the caption with extended character info
    caption = (
        f"<b>Character Info</b>\n\n"
        f"<b>Name:</b> {html.escape(name)}\n"
        f"<b>Anime:</b> {html.escape(anime)}\n"
        f"<b>Rarity:</b> {html.escape(rarity)}\n"
        f"<b>Character ID:</b> {html.escape(str(char_id))}\n"
        f"<b>Uploader:</b> {html.escape(uploader_name)}\n"
    )

    if event:  # Add event details if not empty
        caption += f"<b>Event:</b> {html.escape(event)} {html.escape(event_emoji)}\n"

    # Add spacing before user list
    caption += "\n<b>-------------------------</b>\n\n"

    # Fetch users who own this character with count > 0
    users_cursor = user_collection.find(
        {f"characters.{character_id}": {"$gt": 0}},
        {"username": 1, "first_name": 1, f"characters.{character_id}": 1}
    )
    users = await users_cursor.to_list(length=1000)  # Limit to 1000 users

    if not users:
        caption += "<b>No users own this character yet.</b>"
    else:
        # Select random sample of users (max 10)
        selected_users = random.sample(users, min(15, len(users)))

        # Add user list header
        caption += "<b>Users List:</b>\n\n"

        for user in selected_users:
            username = user.get("username")
            first_name = user.get("first_name", "Unknown")
            char_count = user.get("characters", {}).get(str(character_id), 0)

            # Truncate long names
            truncated_name = " ".join(html.escape(first_name).split()[:10])
            if len(html.escape(first_name).split()) > 10:
                truncated_name += "..."

            # Create user link if username exists
            if username:
                user_link = f"https://t.me/{html.escape(username)}"
                name_link = f'<a href="{user_link}">{truncated_name}</a>'
            else:
                name_link = truncated_name

            # Append count if more than 1
            if char_count > 1:
                caption += f"• {name_link} (×{char_count})\n"
            else:
                caption += f"• {name_link}\n"

    # Send the photo with caption
    await update.message.reply_photo(
        photo=image_url,
        caption=caption,
        parse_mode="HTML"
    )
