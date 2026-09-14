from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db import user_collection, collection as character_collection, banned_users_collection
import html
import logging
from typing import Dict, List
from config import SUDO_USERS 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

def escape(text: str) -> str:
    return html.escape(str(text)) if text is not None else ""


async def is_user_banned(user_id: int) -> bool:
  
    banned_user = await banned_users_collection.find_one({"user_id": user_id})
    return bool(banned_user)


async def calculate_rarity_stats(character_rarities: Dict[int, str], char_ids: List[int] = None) -> Dict[str, List[int]]:
    stats = {}
    characters_to_count = character_rarities.items() if char_ids is None else (
        (char_id, character_rarities.get(char_id, "Unknown")) for char_id in char_ids
    )

    for char_id, rarity in characters_to_count:
        if rarity not in stats:
            stats[rarity] = [0, rarity]
        stats[rarity][0] += 1

    return stats

async def rarity_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = update.effective_user
        user_id = user.id
        mention = f'<a href="tg://user?id={user_id}">{escape(user.first_name)}</a>'
        async def is_user_banned(user_id: int) -> bool:
          
          banned_user = await banned_users_collection.find_one({"user_id": user_id})
          return bool(banned_user)


        chars = await character_collection.find(
            {},
            {"character_id": 1, "rarity": 1}
        ).to_list(length=None)
        character_rarities = {char["character_id"]: char.get("rarity", "Unknown") for char in chars}
        if not character_rarities:
            await update.message.reply_text("No characters found in the database.")
            return

        global_stats = await calculate_rarity_stats(character_rarities)
        total_chars = sum(count for count, _ in global_stats.values())

        user_data = await user_collection.find_one({"user_id": user_id}, {"characters": 1})
        
        if not user_data or not user_data.get("characters"):
            await update.message.reply_text(
                f"{mention}, your collection is empty!",
                parse_mode="HTML"
            )
            return

        user_char_ids = [
            int(char_id) for char_id, count in user_data["characters"].items() 
            if int(count) > 0
        ]
        user_stats = await calculate_rarity_stats(character_rarities, user_char_ids)
        user_total = sum(count for count, _ in user_stats.values())

        tier_order = [
            "🎭 Eternal", "🎐 Celestia X", "🪩 Harmony", "🔮 Vortex", 
            "🏵 Exotic", "🟡 Legendary", "🟢 Medium", "🟠 Rare", "⚪️ Common"
        ]

        message = [
            f"<b>{mention}'s Rarity Distribution</b>",
            f"<i>Total Collected: {user_total}/{total_chars} ({user_total/total_chars:.1%})</i>",
            ""
        ]

        for rarity_name in tier_order:
            if rarity_name in user_stats:
                count, _ = user_stats[rarity_name]
                global_count = global_stats.get(rarity_name, [0])[0]
                percentage = (count / global_count) if global_count > 0 else 0
                progress = "▰" * int(percentage * 10) + "▱" * (10 - int(percentage * 10))
                
                message.append(
                    f"{rarity_name}: {count}/{global_count}\n"
                    f"{progress} {percentage:.0%}"
                )

        await update.message.reply_text(
            "\n".join(message),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error in rarity_stats: {e}", exc_info=True)
        await update.message.reply_text(
            "🌀 Whoops! The cosmic energies are disturbed. Try again later.",
            parse_mode="HTML"
        )

async def top_rarities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = update.effective_user
        user_id = user.id
        mention = f'<a href="tg://user?id={user_id}">{escape(user.first_name)}</a>'

        if user_id not in SUDO_USERS:
            await update.message.reply_text(
                f"{mention}, this command is restricted to sudo users only!",
                parse_mode="HTML"
            )
            return

        characters = await character_collection.find(
            {},
            {"rarity": 1}
        ).to_list(length=None)
        if not characters:
            await update.message.reply_text("No characters found in the database.")
            return

        unique_rarity_counts: Dict[str, int] = {}
        for char in characters:
            rarity = char.get("rarity", "Unknown")
            unique_rarity_counts[rarity] = unique_rarity_counts.get(rarity, 0) + 1

        user_collections = await user_collection.find(
            {"characters": {"$exists": True}},
            {"characters": 1}
        ).to_list(length=None)
        if not user_collections:
            await update.message.reply_text("No user collections found.")
            return

        char_rarities = await character_collection.find(
            {},
            {"character_id": 1, "rarity": 1}
        ).to_list(length=None)
        char_rarity_map = {char["character_id"]: char.get("rarity", "Unknown") for char in char_rarities}

        total_rarity_counts: Dict[str, int] = {}
        user_rarity_counts: Dict[str, int] = {}
        for user in user_collections:
            user_chars = user.get("characters", {})
            user_rarities = set()
            for char_id, count in user_chars.items():
                char_id = int(char_id)
                count = int(count)
                if count > 0:
                    rarity = char_rarity_map.get(char_id, "Unknown")
                    total_rarity_counts[rarity] = total_rarity_counts.get(rarity, 0) + count
                    if rarity not in user_rarities:
                        user_rarities.add(rarity)
                        user_rarity_counts[rarity] = user_rarity_counts.get(rarity, 0) + 1

        tier_order = [
            "🎭 Eternal", "🎐 Celestia X", "🪩 Harmony", "🔮 Vortex", 
            "🏵 Exotic", "🟡 Legendary", "🟢 Medium", "🟠 Rare", "⚪️ Common"
        ]

        message = [f"<b>Rarity Distribution (Sudo Report)</b>", ""]

        for rarity in tier_order:
            total_count = total_rarity_counts.get(rarity, 0)
            unique_count = unique_rarity_counts.get(rarity, 0)
            user_count = user_rarity_counts.get(rarity, 0)
            if unique_count > 0:
                message.append(f"● {rarity}: {total_count}/{unique_count} (Distributed: {user_count})")

        await update.message.reply_text(
            "\n".join(message),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error in top_rarities: {e}", exc_info=True)
        await update.message.reply_text(
            "🌀 Whoops! The cosmic energies are disturbed. Try again later.",
            parse_mode="HTML"
        )

def get_handlers() -> List[CommandHandler]:
    return [
        CommandHandler("rarity", rarity_stats),
        CommandHandler("toprarities", top_rarities)
              ]
