from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from db import user_collection
import logging

logging.basicConfig(
    level=logging.DEBUG, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

RARITIES = {
    "Common": "⚪️ Common",
    "Rare": "🟠 Rare",
    "Medium": "🟢 Medium",
    "Legendary": "🟡 Legendary",
    "Exotic": "🏵 Exotic",
    "Vortex": "🔮 Vortex",
    "Celestia X": "🎐 Celestia X",
    "Harmony": "🪩 Harmony",
    "Eternal": "🎭 Eternal",
    "Elixir": "🍭 Elixir"
}

async def sorts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display sorting options for harem and update user preference."""
    user_id = update.effective_user.id
    user_data = await user_collection.find_one({"user_id": user_id}) or {}

    current_sort = user_data.get("sort_mode", "default")
    current_rarity = user_data.get("rarity_filter")

    buttons = [
        InlineKeyboardButton(f"{'✅ ' if current_sort == 'anime' else ''}Anime", callback_data=f"sort_anime_{user_id}"),
        InlineKeyboardButton(f"{'✅ ' if current_sort == 'character' else ''}Character", callback_data=f"sort_character_{user_id}"),
        InlineKeyboardButton(f"{'✅ ' if current_sort == 'rarity' else ''}Rarity", callback_data=f"sort_rarity_{user_id}"),
        InlineKeyboardButton(f"{'✅ ' if current_sort == 'default' else ''}Default", callback_data=f"sort_default_{user_id}"),
    ]

    keyboard = InlineKeyboardMarkup([buttons[:2], buttons[2:]])

    rarity_text = current_rarity if current_rarity else "All Rarities"

    await update.effective_message.reply_text(
        f"Choose sorting mode:\n(Current sorting: {current_sort.capitalize()})\nSelected rarity: {rarity_text}",
        reply_markup=keyboard
    )

async def handle_sort_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle sorting mode selection and update user data."""
    query = update.callback_query
    callback_data = query.data
    user_id = int(callback_data.split("_")[-1])  
    sort_mode = callback_data.split("_")[1]

    logger.debug(f"Sorting mode selected: {sort_mode} by user {user_id}")

    if query.from_user.id != user_id:
        await query.answer(text="You are not authorized to perform this action.", show_alert=True)
        return

    if sort_mode == "rarity":
        buttons = [
            InlineKeyboardButton(f"{emoji}", callback_data=f"rarity_{name}_{user_id}")
            for name, emoji in RARITIES.items()
        ]
        buttons.append(InlineKeyboardButton("All Rarities", callback_data=f"rarity_all_{user_id}"))

        keyboard = InlineKeyboardMarkup([buttons[i:i+2] for i in range(0, len(buttons), 2)])

        await query.message.edit_text(
            "Select a specific rarity or show all characters:",
            reply_markup=keyboard
        )
    else:
        await user_collection.update_one(
            {"user_id": user_id},
            {"$set": {"sort_mode": sort_mode, "rarity_filter": None}},
            upsert=True
        )
        await query.message.edit_text(f"Harem sort set to: {sort_mode.capitalize()}")

async def handle_rarity_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rarity selection and store emoji representation in the database."""
    query = update.callback_query
    callback_data = query.data
    user_id = int(callback_data.split("_")[-1])  
    rarity_key = callback_data.split("_")[1]

    logger.debug(f"Selected rarity: {rarity_key} for user {user_id}")

    if query.from_user.id != user_id:
        logger.warning(f"Unauthorized action: {query.from_user.id} (Expected {user_id})")
        await query.answer(text="You are not authorized to perform this action.", show_alert=True)
        return

    if rarity_key != "all" and rarity_key not in RARITIES.keys():
        logger.error(f"Invalid rarity selection: {rarity_key}")
        await query.answer(text="Invalid rarity selection!", show_alert=True)
        return

    # Store rarity with emoji in DB
    rarity_filter = None if rarity_key == "all" else RARITIES[rarity_key]

    logger.info(f"Updating rarity filter for user {user_id}: {rarity_filter}")

    await user_collection.update_one(
        {"user_id": user_id},
        {"$set": {"sort_mode": "rarity", "rarity_filter": rarity_filter}},
        upsert=True
    )

    await query.message.edit_text(f"Harem sort set to: Rarity ({rarity_filter})")
