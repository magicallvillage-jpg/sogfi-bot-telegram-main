
import re
import time
from html import escape
import logging

from telegram import InlineQueryResultPhoto, InlineQueryResultVideo, Update
from telegram.ext import InlineQueryHandler, CallbackContext

from db import (
    collection as characters_collection,
    user_collection
)
from .calculate import calculate_anime_count

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RARITY_PRIORITY = {
    "⚪️ Common": 1,
    "🟠 Rare": 2,
    "🟢 Medium": 3,
    "🟡 Legendary": 4,
    "🏵 Exotic": 5,
    "🔮 Vortex": 6,
    "🎐 Celestia X": 7,
    "🪩 Harmony": 8,
    "🎭 Eternal": 9,
    "🍭 Elixir": 10,
    "💳 Custom": 99
}

CUSTOM_RARITY = "💳 Custom"

_indexes_created = False

async def ensure_text_index():
    global _indexes_created
    if _indexes_created:
        return

    indexes = await characters_collection.index_information()
    if "name_anime_text" not in indexes:
        await characters_collection.create_index(
            [("name", "text"), ("anime", "text"), ("rarity", "text"), ("event", "text")],
            name="name_anime_text"
        )
        logger.info("Created text index for name, anime, rarity, and event")
    
    _indexes_created = True

def determine_media_type(character):
    ext = character["image"].split(".")[-1].lower()
    return "image" if ext in ["jpg", "jpeg", "png", "gif", "webp"] else "video"

def contains_emoji_or_non_ascii(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text)

async def inlinequery(update: Update, context: CallbackContext) -> None:
    query = update.inline_query.query.strip()
    offset = int(update.inline_query.offset) if update.inline_query.offset else 0

    user_query_match = re.match(r"user\.(\d+)(?:\s+(.+))?", query)
    if user_query_match:
        target_user_id = int(user_query_match.group(1))
        search_term = user_query_match.group(2) if user_query_match.group(2) else None

        user_data = await user_collection.find_one(
            {"user_id": target_user_id},
            {
                "characters": 1,
                "first_name": 1,
            }
        ) or {}

        if not user_data or not user_data.get("characters"):
            await update.inline_query.answer([], cache_time=5)
            return

        character_ids = [int(k) for k in user_data["characters"].keys()]
        user_name = user_data.get("first_name", "Unknown")

        base_query = {"character_id": {"$in": character_ids}}
        
        user_characters = await characters_collection.find(
            base_query,
            {"_id": 0}
        ).sort("character_id", 1).to_list(length=None)

        if search_term:
            pattern = re.compile(re.escape(search_term), re.IGNORECASE)
            filtered = []
            for c in user_characters:
                if (
                    pattern.search(c.get("name", "")) or
                    pattern.search(c.get("anime", "")) or
                    pattern.search(c.get("rarity", "")) or
                    pattern.search(c.get("event", "") or "") or
                    pattern.search(c.get("event_emoji", "") or "")
                ):
                    filtered.append(c)
            user_characters = filtered

        page_characters = user_characters[offset:offset + 50]
        if not page_characters:
            await update.inline_query.answer([], cache_time=5)
            return

        results = []
        for char in page_characters:
            char_count = user_data["characters"].get(str(char["character_id"]), 0)
            user_anime_count, total_anime_count = await calculate_anime_count(
                target_user_id, char["anime"]
            )

            display_name = f"{char['name']} ×{char_count}" if char_count > 1 else char["name"]

            caption = (
                f"OwO! Check out <a href='tg://user?id={target_user_id}'>{escape(user_name)}</a>'s Character!\n\n"
                f"<b>{escape(char['anime'])}</b> ({user_anime_count}/{total_anime_count})\n"
                f"<b>{char['character_id']} {escape(display_name)}</b>\n"
                f"(𝙍𝘼𝙍𝙄𝙏𝙔: {escape(char['rarity'])})\n"
            )

            if "event" in char and char["event"]:
                caption += f"\n🌟 Event: {escape(char['event'])}\n"

            media_type = determine_media_type(char)
            result_id = f"{char['character_id']}_{time.time()}"

            if media_type == "image":
                results.append(
                    InlineQueryResultPhoto(
                        id=result_id,
                        photo_url=char["image"],
                        thumbnail_url=char["image"],
                        caption=caption,
                        title=display_name,
                        parse_mode="HTML"
                    )
                )
            else:
                results.append(
                    InlineQueryResultVideo(
                        id=result_id,
                        video_url=char["image"],
                        mime_type="video/mp4",
                        thumbnail_url=char["image"],
                        title=display_name,
                        caption=caption,
                        parse_mode="HTML"
                    )
                )

        next_offset = str(offset + 50) if len(user_characters) > offset + 50 else ""
        await update.inline_query.answer(results, next_offset=next_offset, cache_time=5)
        return

    await ensure_text_index()

    global_base_filter = {
        "custome": {"$exists": False},
        "rarity": {"$ne": CUSTOM_RARITY},
    }

    if query:
        if contains_emoji_or_non_ascii(query):
            regex_pattern = re.escape(query)
            cursor = characters_collection.find(
                {
                    "$and": [
                        global_base_filter,
                        {
                            "$or": [
                                {"rarity": {"$regex": regex_pattern, "$options": "i"}},
                                {"event_emoji": {"$regex": regex_pattern, "$options": "i"}},
                            ]
                        }
                    ]
                }
            ).sort("character_id", 1)
        else:
            try:
                cursor = characters_collection.find(
                    {
                        "$and": [
                            global_base_filter,
                            {"$text": {"$search": query}},
                        ]
                    },
                    {"score": {"$meta": "textScore"}}
                ).sort([("score", {"$meta": "textScore"}), ("character_id", 1)])
            except Exception as e:
                logger.warning(f"Text search failed, falling back to regex: {e}")
                cursor = characters_collection.find(
                    {
                        "$and": [
                            global_base_filter,
                            {
                                "$or": [
                                    {"name": {"$regex": query, "$options": "i"}},
                                    {"anime": {"$regex": query, "$options": "i"}},
                                    {"rarity": {"$regex": query, "$options": "i"}},
                                    {"event": {"$regex": query, "$options": "i"}},
                                ]
                            }
                        ]
                    }
                ).sort("character_id", 1)
    else:
        cursor = characters_collection.find(global_base_filter).sort("character_id", -1)

    characters = await cursor.skip(offset).limit(50).to_list(length=50)
    
    results = []
    for char in characters:
        display_name = char["name"]

        caption = (
            f"OwO! Check out this Character!\n\n"
            f"<b>{escape(char['anime'])}</b>\n"
            f"<b>{char['character_id']} {escape(display_name)}</b>\n"
            f"(𝙍𝘼𝙍𝙄𝙏𝙔: {escape(char['rarity'])})\n"
        )

        if "event" in char and char["event"]:
            caption += f"\n🌟 Event: {escape(char['event'])}\n"

        media_type = determine_media_type(char)
        result_id = f"{char['character_id']}_{offset}"

        if media_type == "image":
            results.append(
                InlineQueryResultPhoto(
                    id=result_id,
                    photo_url=char["image"],
                    thumbnail_url=char["image"],
                    caption=caption,
                    parse_mode="HTML"
                )
            )
        else:
            results.append(
                InlineQueryResultVideo(
                    id=result_id,
                    video_url=char["image"],
                    mime_type="video/mp4",
                    thumbnail_url=char["image"],
                    title=display_name,
                    caption=caption,
                    parse_mode="HTML"
                )
            )

    next_offset = str(offset + 50) if len(characters) == 50 else ""
    await update.inline_query.answer(results, next_offset=next_offset, cache_time=300)

def register_inline_handler(application):
    application.add_handler(InlineQueryHandler(inlinequery))
