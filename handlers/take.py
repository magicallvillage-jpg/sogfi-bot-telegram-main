
import asyncio
import html
import traceback
from datetime import datetime, date
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db import user_collection, group_collection, banned_users_collection, elixir_counts_collection
from .spawn import get_last_spawned, SPECIAL_GROUP_ID, get_elixir_incorrect_attempts, reset_elixir_attempts, get_user_message_count, reset_all_user_counts
from .calculate import calculate_anime_count
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

last_spawned_lock = asyncio.Lock()
character_award_locks = {}
DAILY_CHARACTER_LIMIT = 30
ELIXIR_RARITY = "🍭 Elixir"
ELIXIR_MAX_INCORRECT = 2
ELIXIR_MAX_COUNT = 4
ELIXIR_MIN_MESSAGES = 40
EXOTIC_RARITY = "🏵 Exotic"

async def is_user_banned(user_id: int) -> bool:
    banned_user = await banned_users_collection.find_one({"user_id": user_id})
    return bool(banned_user)

async def get_user_elixir_count(user_id: int, character_id: str) -> int:
    count_data = await elixir_counts_collection.find_one(
        {"user_id": user_id, "character_id": character_id}
    )
    return count_data.get("count", 0) if count_data else 0

async def update_user_elixir_count(user_id: int, character_id: str) -> int:
    await elixir_counts_collection.update_one(
        {"user_id": user_id, "character_id": character_id},
        {"$inc": {"count": 1}, "$set": {"last_updated": datetime.utcnow()}},
        upsert=True
    )
    count_data = await elixir_counts_collection.find_one(
        {"user_id": user_id, "character_id": character_id}
    )
    return count_data.get("count", 1)

async def take_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    user_username = update.effective_user.username or None
    error_group_id = -1002655715837

    try:
        if await is_user_banned(user_id):
            await update.message.reply_text("🚫 You are banned from using this bot.")
            return

        async with last_spawned_lock:
            last_spawned = get_last_spawned()
            if chat_id not in last_spawned:
                logger.info(f"No character spawned for chat_id {chat_id}")
                await update.message.reply_text("No character has been spawned yet!")
                return

            char = last_spawned[chat_id]["character"].copy()
            char_id = str(char["character_id"])
            is_elixir = char.get("rarity") == ELIXIR_RARITY
            in_special_group = str(chat_id) == SPECIAL_GROUP_ID
            is_exotic = char.get("rarity") == EXOTIC_RARITY

        if not context.args:
            await update.message.reply_text("Please guess the name of the character.")
            return

        name_query = " ".join(context.args).strip().lower()
        full_name = char["name"].strip().lower()
        reversed_name = " ".join(reversed(full_name.split()))
        name_parts = full_name.split()
        correct = name_query in {full_name, reversed_name} or name_query in name_parts

        user_data = await user_collection.find_one({"user_id": user_id})
        if not user_data:
            user_data = {
                "user_id": user_id,
                "first_name": user_name,
                "username": user_username,
                "daily_stats": {"daily_count": 0, "last_date": ""},
                "characters": {},
                "has_exotic": False,
            }

        current_date = datetime.utcnow().date()
        daily_stats = user_data.get("daily_stats", {"daily_count": 0, "last_date": ""})
        daily_count = daily_stats.get("daily_count", 0)
        last_date_str = daily_stats.get("last_date", "")

        try:
            last_date = datetime.fromisoformat(last_date_str).date() if last_date_str else None
        except Exception:
            last_date = None

        if last_date is None or last_date < current_date:
            daily_count = 0

        if daily_count >= DAILY_CHARACTER_LIMIT:
            await update.message.reply_text(f"You've reached your daily limit of {DAILY_CHARACTER_LIMIT} characters!")
            return

        elixir_incorrect_attempts = get_elixir_incorrect_attempts()

        if is_elixir and in_special_group:
            current_elixir_count = await get_user_elixir_count(user_id, char_id)
            if current_elixir_count >= ELIXIR_MAX_COUNT:
                await update.message.reply_text(f"❌ You've already collected the maximum of {ELIXIR_MAX_COUNT} of this Elixir!")
                return

            user_message_count = await get_user_message_count(chat_id, user_id)
            if user_message_count < ELIXIR_MIN_MESSAGES:
                await update.message.reply_text(f"❌ You need {ELIXIR_MIN_MESSAGES} messages! (You have {user_message_count})")
                return

            async with last_spawned_lock:
                attempts_made = elixir_incorrect_attempts.get(chat_id, {}).get(user_id, 0)
                if attempts_made >= ELIXIR_MAX_INCORRECT:
                    await update.message.reply_text("❌ No attempts left for this Elixir!")
                    return

        if not correct:
            if is_elixir and in_special_group:
                async with last_spawned_lock:
                    elixir_incorrect_attempts.setdefault(chat_id, {})[user_id] = elixir_incorrect_attempts[chat_id].get(user_id, 0) + 1
                    attempts_left = ELIXIR_MAX_INCORRECT - elixir_incorrect_attempts[chat_id][user_id]
                    await update.message.reply_text(f"❌ Incorrect! {attempts_left} attempt(s) left.")
            else:
                await update.message.reply_text("Incorrect name, try again!")
            return

        lock_key = f"award_character_{chat_id}"
        character_award_locks.setdefault(lock_key, asyncio.Lock())

        async with character_award_locks[lock_key]:
            async with last_spawned_lock:
                if chat_id not in last_spawned:
                    await update.message.reply_text("No character has been spawned yet!")
                    return

                if last_spawned[chat_id].get("taken_by") and not (is_elixir and in_special_group):
                    await update.message.reply_text("This character has already been taken!")
                    return

                if is_elixir and in_special_group:
                    if chat_id in elixir_incorrect_attempts and user_id in elixir_incorrect_attempts[chat_id]:
                        del elixir_incorrect_attempts[chat_id][user_id]

                last_spawned[chat_id]["taken_by"] = user_id

            if is_elixir and in_special_group:
                await reset_all_user_counts(chat_id)

            await group_collection.update_one(
                {"group_id": chat_id},
                {
                    "$set": {"group_name": update.effective_chat.title, f"user_stats.{user_id}.name": user_name, f"user_stats.{user_id}.username": user_username},
                    "$inc": {"total_characters": 1, f"user_stats.{user_id}.character_count": 1}
                },
                upsert=True
            )

            current_count = user_data.get("characters", {}).get(char_id, 0)
            new_count = current_count + 1

            if is_elixir:
                current_elixir_count = await update_user_elixir_count(user_id, char_id)

            # --- CONFLICT FIX BLOCK ---
            set_fields = {
                "first_name": user_name,
                "username": user_username,
                f"characters.{char_id}": new_count,
                "daily_stats": {"daily_count": daily_count + 1, "last_date": current_date.isoformat()},
            }

            if is_exotic:
                # If Exotic, set it to True in $set. Don't use $setOnInsert for this key.
                set_fields["has_exotic"] = True
                update_query = {"$set": set_fields}
            else:
                # If not Exotic, set False ONLY on new user creation ($setOnInsert)
                update_query = {
                    "$set": set_fields,
                    "$setOnInsert": {"has_exotic": False}
                }

            await user_collection.update_one({"user_id": user_id}, update_query, upsert=True)
            # --- END FIX ---

            user_anime_count, total_anime_count = await calculate_anime_count(user_id, char["anime"])
            event_emoji = char.get("event_emoji", "") if char.get("event_emoji") not in [None, "None"] else ""
            char_display_name = f"{event_emoji} {char['name']} x{new_count}".strip() if new_count > 1 else f"{event_emoji} {char['name']}".strip()

            response = (
                f"<b>✅ <a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>, Character Taken!</b>\n\n"
                f"<blockquote><b>🪭 Name:</b> {html.escape(char_display_name)}\n"
                f"<b>💖 Anime:</b> {html.escape(char['anime'])} ({user_anime_count}/{total_anime_count})\n"
                f"<b>🧧 Rarity:</b> {html.escape(char.get('rarity', 'Unknown'))}</blockquote>\n\n"
                f"<i>Daily captures: {daily_count + 1}/{DAILY_CHARACTER_LIMIT}</i>"
            )

            if is_elixir:
                response += f"\n\n⚠️ <b>Elixir:</b> Collected {current_elixir_count}/{ELIXIR_MAX_COUNT}."

            await update.message.reply_html(text=response, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("See Collection", switch_inline_query_current_chat=f"user.{user_id}")]]))

            async with last_spawned_lock:
                last_spawned.pop(chat_id, None)

    except Exception:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in take_character: {error_traceback}")
        try:
            await context.bot.send_message(chat_id=error_group_id, text=f"🚨 <b>Error</b>\n<code>{html.escape(error_traceback)}</code>", parse_mode='HTML')
        except Exception: pass
        await update.message.reply_text("⚠️ Something went wrong.")
    finally:
        character_award_locks.pop(f"award_character_{chat_id}", None)
         
