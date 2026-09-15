
import asyncio
import random
import time
import logging
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db import db, collection as character_collection, banned_users_collection
from config import RARITY_MAPPING, RARITY_EMOJIS, SUDO_USERS as ADMIN_IDS
from .drop import init_default_drop_rates, get_current_drop_rates, set_single_drop_rate

# Try to import the safe sender from the main app (app.py). If not available, fall back to local safe-send.
try:
    from app import telegram_send_with_handling, application
except Exception:
    try:
        from app_modified import telegram_send_with_handling, application
    except Exception:
        telegram_send_with_handling = None
        application = None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Constants
SPECIAL_GROUP_ID = "-1003987395271"
ELIXIR_RARITY = "🍭 Elixir"

# Counters
total_message_counts = defaultdict(int)
regular_message_counts = defaultdict(int)
special_message_counts = defaultdict(int)  # For special group only
last_spawned = {}
group_settings = db["gsettings"]
taken_characters = {}
event_triggers = defaultdict(dict)
special_triggers = defaultdict(dict)  # For special group Elixir spawns
user_activity = defaultdict(dict)

# Use asyncio locks for proper synchronization
spawn_locks = defaultdict(asyncio.Lock)

# Database collections
special_group_settings = db["special_group_settings"]
user_message_counts = db["user_message_counts"]

# Elixir attempt tracking system
elixir_incorrect_attempts = defaultdict(lambda: defaultdict(int))

def get_elixir_incorrect_attempts():
    """Returns the dictionary tracking incorrect attempts for Elixir characters"""
    return elixir_incorrect_attempts

def reset_elixir_attempts(chat_id):
    """Reset incorrect attempts for a chat when a new Elixir spawns"""
    if chat_id in elixir_incorrect_attempts:
        del elixir_incorrect_attempts[chat_id]
        logger.info(f"Reset Elixir attempts for chat: {chat_id}")

# Initialize special group settings with proper field defaults
async def init_special_group_settings():
    settings = await special_group_settings.find_one({"group_id": SPECIAL_GROUP_ID})
    if not settings:
        await special_group_settings.insert_one({
            "group_id": SPECIAL_GROUP_ID,
            "enabled": True,
            "allowed_characters": [],
            "stop_counts": {}
        })
    else:
        # Ensure all required fields exist with defaults
        update_fields = {}
        if "enabled" not in settings:
            update_fields["enabled"] = True
        if "allowed_characters" not in settings:
            update_fields["allowed_characters"] = []
        if "stop_counts" not in settings:
            update_fields["stop_counts"] = {}

        if update_fields:
            await special_group_settings.update_one(
                {"group_id": SPECIAL_GROUP_ID},
                {"$set": update_fields}
            )
    return await special_group_settings.find_one({"group_id": SPECIAL_GROUP_ID})

# Per-user message tracking
async def update_user_message_count(group_id, user_id):
    group_id = str(group_id)  # Ensure consistent type
    await user_message_counts.update_one(
        {"group_id": group_id, "user_id": user_id},
        {"$inc": {"count": 1}},
        upsert=True
    )

async def reset_all_user_counts(group_id):
    group_id = str(group_id)  # Ensure consistent type
    await user_message_counts.update_many(
        {"group_id": group_id},
        {"$set": {"count": 0}}
    )

async def get_user_message_count(group_id, user_id):
    group_id = str(group_id)  # Ensure consistent type
    doc = await user_message_counts.find_one(
        {"group_id": group_id, "user_id": user_id}
    )
    return doc["count"] if doc else 0

# Special group character management
async def get_special_group_settings():
    return await special_group_settings.find_one({"group_id": SPECIAL_GROUP_ID}) or {}

async def toggle_special_spawn(enable: bool):
    await special_group_settings.update_one(
        {"group_id": SPECIAL_GROUP_ID},
        {"$set": {"enabled": enable}},
        upsert=True
    )

async def allow_elixir_character(character_id: int):
    await special_group_settings.update_one(
        {"group_id": SPECIAL_GROUP_ID},
        {"$addToSet": {"allowed_characters": character_id}},
        upsert=True
    )

async def disallow_elixir_character(character_id: int):
    await special_group_settings.update_one(
        {"group_id": SPECIAL_GROUP_ID},
        {"$pull": {"allowed_characters": character_id}}
    )

async def set_elixir_stop_count(character_id: int, count: int):
    await special_group_settings.update_one(
        {"group_id": SPECIAL_GROUP_ID},
        {"$set": {f"stop_counts.{character_id}": count}}
    )

async def get_elixir_character():
    settings = await get_special_group_settings()
    allowed_characters = settings.get("allowed_characters", [])
    if not allowed_characters:
        return None

    # Get random allowed character
    char_id = random.choice(allowed_characters)
    character = await character_collection.find_one({"character_id": char_id})

    if not character:
        return None

    # Handle stop count if exists
    stop_counts = settings.get("stop_counts", {})
    if char_id in stop_counts:
        new_count = stop_counts[char_id] - 1

        if new_count <= 0:
            # Remove stop count and character from allowed list
            await special_group_settings.update_one(
                {"group_id": SPECIAL_GROUP_ID},
                {"$pull": {"allowed_characters": char_id},
                 "$unset": {f"stop_counts.{char_id}": ""}}
            )
        else:
            # Decrement stop count
            await special_group_settings.update_one(
                {"group_id": SPECIAL_GROUP_ID},
                {"$set": {f"stop_counts.{char_id}": new_count}}
            )

    return character

# Core functions
async def is_user_banned(user_id):
    banned_user = await banned_users_collection.find_one({"user_id": user_id})
    return bool(banned_user)

async def get_active_events():
    try:
        doc = await db["spawn_settings"].find_one({"type": "global"})
        return doc.get("events", []) if doc else []
    except Exception as e:
        logger.error(f"Error fetching active events: {e}")
        return []

async def get_random_event():
    active_events = await get_active_events()
    return random.choice(active_events) if active_events else None

async def get_group_threshold(group_id):
    doc = await group_settings.find_one({"group_id": str(group_id)})
    return doc["spawn_threshold"] if doc else 100

async def fetch_characters(character_ids):
    try:
        return await character_collection.find({"character_id": {"$in": character_ids}}).to_list(length=None)
    except Exception as e:
        logger.error(f"MongoDB fetch_characters error: {e}")
        return []

async def fetch_characters_by_event(event_name):
    try:
        return await character_collection.find({"event": event_name}).to_list(length=None)
    except Exception as e:
        logger.error(f"MongoDB fetch_characters_by_event error: {e}")
        return []

async def get_random_character_by_rarity(rarity_name, require_no_event=True):
    query = {"rarity": rarity_name, "custome": {"$exists": False}}
    if require_no_event:
        query["$and"] = [
            {"event": {"$exists": False}},
            {"event_emoji": {"$exists": False}}
        ]
    try:
        count = await character_collection.count_documents(query)
        if count == 0:
            return None
        random_skip = random.randint(0, count - 1)
        return await character_collection.find_one(query, skip=random_skip)
    except Exception as e:
        logger.error(f"Error getting random character: {e}")
        return None

async def get_random_character_wrapper():
    current_rates = await get_current_drop_rates()
    rarity_ids = list(current_rates.keys())
    weights = list(current_rates.values())

    for rarity_id in random.choices(rarity_ids, weights=weights, k=len(rarity_ids)):
        rarity_name = RARITY_MAPPING[rarity_id]
        char = await get_random_character_by_rarity(rarity_name, True)
        if char:
            return char
    logger.error("No non-event characters found for any rarity")
    return None

async def send_character(chat_id, context, char):
    """Sends a character announcement to the chat using app's safe sender when available."""
    emoji = RARITY_EMOJIS.get(char.get('rarity'), '👾')
    caption = (
        f"<b>{emoji} 𝖭𝖾𝗐 𝖢𝗁𝖺𝗋𝖺𝖼𝗍𝖾𝗋 𝗁𝖺𝗌 𝖲𝗉𝖺𝗐𝗇𝖾𝖽 𝗂𝗇𝗍𝗈 𝗍𝗁𝖾 𝖼𝗁𝖺𝗍!</b>"
    "<b>  🥡 𝗎𝗌𝖾 /take [𝗇𝖺𝗆𝖾] 𝗍𝗈 𝗀𝖾𝗍 𝗍𝖺𝗄𝖾 𝗍𝗁𝗂𝗌 𝖼𝗁𝖺𝗋𝖺𝖼𝗍𝖾𝗋 𝗂𝗇 𝗒𝗈𝗎𝗋 𝗁𝖺𝗋𝖾𝗆</b>"
    )
    media_url = char.get("image")
    media_type = "video" if media_url and media_url.lower().endswith(".mp4") else "photo"

    async def _local_safe_send(bot_method, *args, **kwargs):
        from telegram.error import RetryAfter
        try:
            return await bot_method(*args, **kwargs)
        except RetryAfter as e:
            wait = int(getattr(e, "retry_after", getattr(e, "timeout", 60)))
            logger.warning("Local caught RetryAfter from Telegram. Sleeping %s seconds.", wait)
            await asyncio.sleep(min(wait, 5))
            return None
        except Exception as e:
            logger.exception("Local send failed: %s", e)
            return None

    try:
        # Use app-level safe sender if available (handles FloodWait + queue drain)
        if telegram_send_with_handling and application:
            if media_type == "photo":
                await telegram_send_with_handling(application, context.bot.send_photo, chat_id=chat_id, photo=media_url, caption=caption, parse_mode="HTML")
            else:
                await telegram_send_with_handling(application, context.bot.send_video, chat_id=chat_id, video=media_url, caption=caption, parse_mode="HTML")
        else:
            # fallback to local safe sender
            if media_type == "photo":
                await _local_safe_send(context.bot.send_photo, chat_id=chat_id, photo=media_url, caption=caption, parse_mode="HTML")
            else:
                await _local_safe_send(context.bot.send_video, chat_id=chat_id, video=media_url, caption=caption, parse_mode="HTML")

        # Only update last_spawned if send was successful
        last_spawned[chat_id] = {"character": char, "time": time.time()}

        # Reset incorrect attempts when a new Elixir spawns
        if char.get("rarity") == ELIXIR_RARITY and str(chat_id) == SPECIAL_GROUP_ID:
            reset_elixir_attempts(chat_id)

        return True
    except Exception as e:
        logger.error(f"Error sending character {char.get('name')}: {e}")
        return False

# Updated handle_group_messages with proper synchronization
async def handle_group_messages(update, context):
    await init_special_group_settings()

    if update.effective_chat.type not in ("group", "supergroup"):
        return

    group_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    current_time = time.time()

    # Anti-spam checks
    if await is_user_banned(user_id):
        return

    if group_id not in user_activity:
        user_activity[group_id] = {
            "last_user": None,
            "consecutive_count": 0,
            "blocked_users": {}
        }

    group_data = user_activity[group_id]

    # User blocking logic
    if user_id in group_data["blocked_users"]:
        if current_time < group_data["blocked_users"][user_id]:
            return
        del group_data["blocked_users"][user_id]

    # Consecutive message tracking
    if group_data["last_user"] == user_id:
        group_data["consecutive_count"] += 1
    else:
        group_data["consecutive_count"] = 1
        group_data["last_user"] = user_id

    # Block spammers
    if group_data["consecutive_count"] >= 11:
        group_data["blocked_users"][user_id] = current_time + 360
        try:
            username = update.effective_user.first_name or "User"
            await update.message.reply_text(
                f"{username}, no spamming! Blocked for 11 minutes."
            )
            logger.info(f"Blocked user {user_id} in group {group_id}")
        except Exception as e:
            logger.error(f"Error sending spam warning: {e}")
        return

    # Update message counters
    if update.message or update.edited_message:
        total_message_counts[group_id] += 1
        regular_message_counts[group_id] += 1

        # Update message count for ALL groups
        await update_user_message_count(group_id, user_id)

        # Special handling for special group only
        if group_id == SPECIAL_GROUP_ID:
            special_message_counts[group_id] += 1

    # Initialize event trigger if not exists
    if not event_triggers.get(group_id):
        next_trigger = random.randint(3000, 3200)
        event_triggers[group_id] = {
            "next_trigger": next_trigger,
            "triggered": False
        }
        logger.info(f"Initialized event trigger for {group_id}: {next_trigger}")

    # Initialize special trigger for special group
    if group_id == SPECIAL_GROUP_ID and not special_triggers.get(group_id):
        next_trigger = random.randint(700, 800)
        special_triggers[group_id] = {
            "next_trigger": next_trigger,
            "triggered": False
        }
        logger.info(f"Initialized special trigger for {group_id}: {next_trigger}")

    # Get group-specific settings
    threshold = await get_group_threshold(int(group_id))
    event_trigger = event_triggers[group_id]

    # Get lock for this group
    lock = spawn_locks[group_id]
    async with lock:
        # Cooldown check - prevent multiple spawns in quick succession
        if group_id in last_spawned:
            elapsed = current_time - last_spawned[group_id].get("time", 0)
            if elapsed < 5:  # 5-second cooldown
                return

        # SPECIAL GROUP HANDLING: Elixir spawn
        if group_id == SPECIAL_GROUP_ID:
            settings = await get_special_group_settings()
            special_trigger = special_triggers[group_id]

            # Use safe access with defaults
            enabled = settings.get("enabled", True)

            if (enabled and 
                not special_trigger["triggered"] and 
                special_message_counts[group_id] >= special_trigger["next_trigger"]):

                try:
                    char = await get_elixir_character()
                    if not char:
                        logger.warning("No allowed Elixir characters found")
                        char = await get_random_character_by_rarity(ELIXIR_RARITY, False)

                    if char:
                        success = await send_character(update.effective_chat.id, context, char)
                        if success:
                            # Reset ALL counters and set new trigger
                            special_message_counts[group_id] = 0
                            total_message_counts[group_id] = 0
                            regular_message_counts[group_id] = 0
                            new_trigger = random.randint(700, 800)
                            special_triggers[group_id] = {
                                "next_trigger": new_trigger,
                                "triggered": False
                            }

                            logger.info(f"Special Elixir spawned in {group_id}. New trigger: {new_trigger}")
                except Exception as e:
                    logger.error(f"Special spawn error: {e}")
                return  # Return after handling special spawn

        # Event spawn logic
        if (not event_trigger["triggered"] and 
            total_message_counts[group_id] >= event_trigger["next_trigger"]):

            try:
                active_event = await get_random_event()
                char = None

                if active_event:
                    event_chars = await fetch_characters_by_event(active_event)
                    if event_chars:
                        char = random.choice(event_chars)
                        logger.info(f"Spawning event character in {group_id} ({active_event})")

                if not char:
                    char = await get_random_character_wrapper()
                    logger.info(f"Using fallback character in {group_id}")

                if char:
                    success = await send_character(update.effective_chat.id, context, char)
                    if success:
                        # Reset both counters
                        total_message_counts[group_id] = 0
                        regular_message_counts[group_id] = 0
                        new_trigger = random.randint(3000, 3200)
                        event_triggers[group_id] = {
                            "next_trigger": new_trigger,
                            "triggered": False
                        }
                        logger.info(f"Event spawned in {group_id}. New trigger: {new_trigger}")
            except Exception as e:
                logger.error(f"Event spawn error: {e}")
            return  # Return after handling event spawn

        # Regular spawn logic
        if regular_message_counts[group_id] >= threshold:
            try:
                char = await get_random_character_wrapper()
                if char:
                    success = await send_character(update.effective_chat.id, context, char)
                    if success:
                        regular_message_counts[group_id] = 0
                        logger.info(f"Regular spawn in {group_id}")
            except Exception as e:
                logger.error(f"Regular spawn error: {e}")


def get_last_spawned():
    return last_spawned
