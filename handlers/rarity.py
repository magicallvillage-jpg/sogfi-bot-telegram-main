from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db import user_collection, collection as character_collection, banned_users_collection
import html
import logging
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

def escape(text: str) -> str:
    """Escape text for HTML safety."""
    return html.escape(str(text)) if text is not None else ""


async def is_user_banned(user_id: int) -> bool:
    banned_user = await banned_users_collection.find_one({"user_id": user_id})
    return bool(banned_user)


async def get_character_rarities() -> Dict[int, str]:
    """Fetch all character rarities from MongoDB."""
    try:
        chars = await character_collection.find(
            {},
            {"character_id": 1, "rarity": 1}
        ).to_list(length=None)
        return {char["character_id"]: char.get("rarity", "Unknown") for char in chars}
    except Exception as e:
        logger.error(f"Error fetching character rarities: {e}")
        return {}

async def calculate_rarity_stats(character_rarities: Dict[int, str], char_ids: List[int] = None) -> Dict[str, Tuple[int, str]]:
    """
    Calculate rarity statistics using raw database values with emojis.
    Returns {rarity: (count, rarity_name)}
    """
    stats = {}
    characters_to_count = character_rarities.items() if char_ids is None else (
        (char_id, character_rarities.get(char_id, "Unknown")) for char_id in char_ids
    )

    for char_id, rarity in characters_to_count:
        if rarity not in stats:
            stats[rarity] = [0, rarity]  # [count, rarity_name]
        stats[rarity][0] += 1

    return stats

async def rarity_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /rarity command using rarity values directly from character_collection."""
    try:
        user = update.effective_user
        user_id = user.id
        mention = f'<a href="tg://user?id={user_id}">{escape(user.first_name)}</a>'

        if await is_user_banned(user_id):
          
            await update.message.reply_text("🚫 You are banned from using this bot.")
            return
        # Get all character rarities
        character_rarities = await get_character_rarities()
        if not character_rarities:
            await update.message.reply_text("No characters found in the database.")
            return

        # Calculate global stats using raw rarity values
        global_stats = await calculate_rarity_stats(character_rarities)
        total_chars = sum(count for count, _ in global_stats.values())

        # Get user's collection
        user_data = await user_collection.find_one({"user_id": user_id}, {"characters": 1})
        
        if not user_data or not user_data.get("characters"):
            await update.message.reply_text(
                f"{mention}, your collection is empty!",
                parse_mode="HTML"
            )
            return

        # Get user's character IDs with counts > 0
        user_char_ids = [
            int(char_id) for char_id, count in user_data["characters"].items() 
            if int(count) > 0
        ]
        user_stats = await calculate_rarity_stats(character_rarities, user_char_ids)
        user_total = sum(count for count, _ in user_stats.values())

        # Predefined rarity tier order
        tier_order = [
           "🍭 Elixir", "🎭 Eternal", "🎐 Celestia X", "🪩 Harmony", "🔮 Vortex", 
            "🏵 Exotic", "🟡 Legendary", "🟢 Medium", "🟠 Rare", "⚪️ Common"
        ]

        message = [
            f"<b>{mention}'s Rarity Distribution</b>",
            f"<i>Total Collected: {user_total}/{total_chars} ({user_total/total_chars:.1%})</i>",
            ""
        ]

        # Add progress bars for each tier
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

def get_rarity_handler() -> List[CommandHandler]:
    """Returns command handlers for rarity stats."""
    return [CommandHandler("rarity", rarity_stats)]
