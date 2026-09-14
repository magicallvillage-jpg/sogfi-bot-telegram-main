from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from db import user_collection, collection as character_collection, banned_users_collection
import html
import logging
from typing import Optional, Dict

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def is_user_banned(user_id: int) -> bool:
    banned_user = await banned_users_collection.find_one({"user_id": user_id})
    return bool(banned_user)

def escape_html(text: str) -> str:
    return html.escape(str(text)) if text else ""

async def fav_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    
    user_id = user.id
    if await is_user_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    mention = f'<a href="tg://user?id={user_id}">{escape_html(user.first_name)}</a>'

    if not context.args:
        await update.message.reply_text("Usage: /fav <character_id>")
        return

    try:
        char_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Character ID must be a number.")
        return

    user_data = await user_collection.find_one(
        {"user_id": user_id, f"characters.{char_id}": {"$gt": 0}}
    )
    if not user_data:
        await update.message.reply_text("You don't own this character.")
        return

    character = await character_collection.find_one({"character_id": char_id})
    if not character:
        await update.message.reply_text("Character not found.")
        return

    rarity = character.get("rarity", "Unknown")
    if rarity == "l":
        await update.message.reply_text(
            "Characters with 🎭 Eternal rarity cannot be set as favorites."
        )
        return

    context.user_data["fav_candidate"] = {
        "char_id": char_id,
        "character": character,
        "message_id": update.message.message_id
    }

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data="fav_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="fav_cancel")
        ]
    ])

    name = escape_html(character.get("name", "Unknown"))
    anime = escape_html(character.get("anime", "Unknown"))
    rarity = escape_html(rarity)
    image_url = character.get("image")

    caption = (
        f"{mention}, do you want to set <b>{name}</b> as your favorite character?\n\n"
        f"<b>Character Info</b>\n"
        f"Name: {name}\n"
        f"Anime: {anime}\n"
        f"Rarity: {rarity}\n"
        f"ID: {char_id}"
    )

    try:
        if image_url:
            await update.message.reply_photo(
                photo=image_url,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                caption,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error sending favorite confirmation: {e}")
        await update.message.reply_text(
            "Couldn't load character image. Please try again.",
            parse_mode="HTML"
        )

async def fav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if await is_user_banned(user_id):
        await query.edit_message_caption("🚫 You are banned from using this bot.", parse_mode='HTML')
        return
    user_name = query.from_user.first_name or "User"

    data: Optional[Dict] = context.user_data.get("fav_candidate")
    if not data or query.from_user.id != update.effective_user.id:
        return await query.edit_message_caption(
            caption="Session expired. Please use /fav <id> again.",
            parse_mode="HTML"
        )

    if query.data == "fav_confirm":
        try:
            result = await user_collection.update_one(
                {"user_id": user_id},
                {"$set": {"fav": data["char_id"]}},
                upsert=True
            )

            if result.modified_count > 0 or result.upserted_id:
                character = data["character"]
                mention = f"<a href='tg://user?id={user_id}'>{escape_html(user_name)}</a>"
                name = escape_html(character.get("name", "Unknown"))
                anime = escape_html(character.get("anime", "Unknown"))
                rarity = escape_html(character.get("rarity", "Unknown"))

                new_caption = (
                    f"{mention} set <b>{name}</b> as their favorite character!\n\n"
                    f"<b>Anime:</b> {anime}\n"
                    f"<b>Rarity:</b> {rarity}\n"
                    f"<b>ID:</b> {data['char_id']}"
                )

                try:
                    if "image" in character and character["image"]:
                        await query.edit_message_caption(
                            caption=new_caption,
                            parse_mode="HTML"
                        )
                    else:
                        await query.edit_message_text(
                            new_caption,
                            parse_mode="HTML"
                        )
                except Exception as e:
                    logger.error(f"Error editing favorite message: {e}")
                    await query.edit_message_text(
                        new_caption,
                        parse_mode="HTML"
                    )
            else:
                await query.edit_message_caption(
                    caption="Failed to update favorite character. Please try again.",
                    parse_mode="HTML"
                )

        except Exception as e:
            logger.error(f"Error setting favorite character: {e}")
            await query.edit_message_caption(
                caption="An error occurred while updating your favorite character.",
                parse_mode="HTML"
            )

    elif query.data == "fav_cancel":
        await query.edit_message_caption(
            caption="Favorite selection canceled.",
            parse_mode="HTML"
        )

    context.user_data.pop("fav_candidate", None)

def get_fav_handler() -> list:
    return [
        CommandHandler("fav", fav_character),
        CallbackQueryHandler(fav_callback, pattern="^fav_")
    ]
