import random
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db import db, collection as character_collection
from config import RARITY_MAPPING, RARITY_EMOJIS, SUDO_USERS as ADMIN_IDS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================
# Mongo-safe default rates
# =========================
DEFAULT_DROP_RATES = {
    "1": 35.0,  # Common
    "2": 25.0,  # Uncommon
    "3": 20.0,  # Rare
    "4": 10.0,  # Epic
    "5": 5.0,   # Legendary
    "6": 3.0,   # Mythic
    "7": 1.5,   # Divine
    "8": 0.5    # Celestial
}

# =========================
# DB Init
# =========================
async def init_default_drop_rates():
    try:
        existing = await db["drop_rate"].find_one({"type": "current"})
        if not existing:
            await db["drop_rate"].insert_one({
                "type": "current",
                "rates": DEFAULT_DROP_RATES
            })
            logger.info("Initialized default drop rates")
    except Exception as e:
        logger.error(f"Error initializing drop rates: {e}")

# =========================
# Get rates
# =========================
async def get_current_drop_rates():
    try:
        doc = await db["drop_rates"].find_one({"type": "current"})
        return doc.get("rates", DEFAULT_DROP_RATES) if doc else DEFAULT_DROP_RATES
    except Exception as e:
        logger.error(f"Error fetching drop rates: {e}")
        return DEFAULT_DROP_RATES

# =========================
# Set single rate (ADMIN)
# =========================
async def set_single_drop_rate(rarity: int, rate: float):
    try:
        current_rates = await get_current_drop_rates()
        current_rates[str(rarity)] = rate  # 🔑 STRING KEY

        await db["drop_rates"].update_one(
            {"type": "current"},
            {"$set": {"rates": current_rates}},
            upsert=True
        )
        logger.info(f"Updated drop rate for rarity {rarity} → {rate}%")
    except Exception as e:
        logger.error(f"Error setting drop rate: {e}")

# =========================
# Reset rates
# =========================
async def reset_drop_rates():
    try:
        await db["drop_rate"].update_one(
            {"type": "current"},
            {"$set": {"rates": DEFAULT_DROP_RATES}},
            upsert=True
        )
        logger.info("Reset drop rates to default")
    except Exception as e:
        logger.error(f"Error resetting drop rates: {e}")

# =========================
# Random character logic
# =========================
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

# =========================
# Drop wrapper
# =========================
async def get_random_character_wrapper():
    current_rates = await get_current_drop_rates()

    rarity_ids = [int(k) for k in current_rates.keys()]
    weights = list(current_rates.values())

    for rarity_id in random.choices(rarity_ids, weights=weights, k=len(rarity_ids)):
        rarity_name = RARITY_MAPPING[rarity_id]
        char = await get_random_character_by_rarity(rarity_name, True)
        if char:
            return char

    logger.error("No non-event characters found")
    return None

# =========================
# ADMIN COMMANDS
# =========================
async def show_drop_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_rates = await get_current_drop_rates()
    response = "📊 Current Drop Rates:\n\n"

    total = 0
    for rarity in sorted(map(int, current_rates.keys())):
        rate = current_rates[str(rarity)]
        rarity_name = RARITY_MAPPING[rarity]
        emoji = RARITY_EMOJIS.get(rarity_name, "❓")
        response += f"{emoji} {rarity_name}: {rate}%\n"
        total += rate

    response += f"\n📈 Total: {total}%"
    if total != 100:
        response += " ⚠️"

    await update.message.reply_text(response)

async def set_drop_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 Permission denied.")
        return

    try:
        rarity = int(context.args[0])
        new_rate = float(context.args[1])

        if rarity < 1 or rarity > 8:
            raise ValueError

        current_rates = await get_current_drop_rates()
        old = current_rates.get(str(rarity), 0)
        total_without = sum(current_rates.values()) - old

        if total_without + new_rate > 100:
            await update.message.reply_text(
                f"⚠️ Total would exceed 100% (current: {total_without}%)"
            )
            return

        await set_single_drop_rate(rarity, new_rate)

        rarity_name = RARITY_MAPPING[rarity]
        emoji = RARITY_EMOJIS.get(rarity_name, "❓")

        await update.message.reply_text(
            f"✅ {emoji} {rarity_name} set to {new_rate}%"
        )

    except Exception:
        await update.message.reply_text(
            "❌ Usage: /droprate <rarity 1-8> <rate>"
        )

async def reset_rates_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 Permission denied.")
        return

    await reset_drop_rates()
    await update.message.reply_text("✅ Drop rates reset.")

async def drop_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Drop System\n\n"
        "/droprates - show rates\n"
        "/droprate <rarity> <rate> - set rate\n"
    )

# =========================
# Register handlers
# =========================
def register_drop_handlers(application):
    application.add_handler(CommandHandler("droprates", show_drop_rates))
    application.add_handler(CommandHandler("droprate", set_drop_rate))
    application.add_handler(CommandHandler("resetrates", reset_rates_command))
    application.add_handler(CommandHandler("dropinfo", drop_info))
