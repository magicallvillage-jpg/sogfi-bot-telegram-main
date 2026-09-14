import random
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import motor.motor_asyncio
from db import db 

# Collections
rarity_collection = db["r-market"]
event_collection = db["event-market"]

# Rarity Mapping
RARITY_MAPPING = {
    1: "⚪️ Common",
    2: "🟠 Rare",
    3: "🟢 Medium",
    4: "🟡 Legendary",
    5: "🏵 Exotic",
    6: "🔮 Vortex",
    7: "🎐 Celestia X",
    8: "🪩 Harmony",
    9: "🎭 Eternal"
}

async def set_market(update: Update, context: CallbackContext):
    try:
        if not context.args:
            await update.message.reply_text(
                "📊 *Market Configuration*\n\n"
                "Usage:\n"
                "- `/R-market <rarity_emoji> on <min-max>` - Enable rarity with price range\n"
                "- `/R-market <rarity_emoji> off` - Disable rarity\n"
                "- `/R-market event <event_emoji> on/off` - Toggle event status\n"
                "- `/R-market list` - Show current market status\n\n"
                "Example:\n"
                "`/R-market ⚪️ on 100-200`\n"
                "`/R-market event 🎄 off`",
                parse_mode="Markdown"
            )
            return

        command_type = context.args[0].lower()

        if command_type == "list":
            # Get active rarities
            active_rarities = []
            async for rarity in rarity_collection.find({"active": True}):
                rarity_name = RARITY_MAPPING.get(int(rarity["rarity_id"]), "Unknown")
                price_range = (f"{rarity['price_range'][0]}-{rarity['price_range'][1]}" 
                             if rarity.get("price_range") else "Not set")
                active_rarities.append(f"• {rarity_name} - 💰 {price_range}")

            # Get disabled events
            disabled_events = []
            async for event in event_collection.find({"active": False}):
                disabled_events.append(f"• {event['event_emoji']}")

            # Build response
            response = []
            if active_rarities:
                response.append("🌟 *Active Rarities:*\n" + "\n".join(active_rarities))
            else:
                response.append("ℹ️ No active rarities in market.")

            if disabled_events:
                response.append("\n🚫 *Disabled Events:*\n" + "\n".join(disabled_events))
            else:
                response.append("\nℹ️ All events are currently enabled.")

            await update.message.reply_text("\n".join(response), parse_mode="Markdown")
            return

        if command_type == "event":
            if len(context.args) != 3 or context.args[2].lower() not in ["on", "off"]:
                await update.message.reply_text(
                    "❌ Invalid format. Usage:\n"
                    "`/R-market event <event_emoji> on/off`\n\n"
                    "Example:\n"
                    "`/R-market event 🎄 off`",
                    parse_mode="Markdown"
                )
                return

            event_emoji = context.args[1]
            status = context.args[2].lower() == "on"

            await event_collection.update_one(
                {"event_emoji": event_emoji},
                {"$set": {"active": status}},
                upsert=True
            )
            
            action = "enabled" if status else "disabled"
            await update.message.reply_text(f"✅ Event {event_emoji} has been {action} in the market.")
            return

        # Handle rarity commands
        if len(context.args) < 2:
            raise ValueError("Insufficient arguments")

        rarity_emoji = context.args[0]
        status = context.args[1].lower()

        # Find matching rarity
        rarity_id = next((k for k, v in RARITY_MAPPING.items() if v.startswith(rarity_emoji)), None)
        if rarity_id is None:
            await update.message.reply_text("❌ Invalid rarity emoji. Use one of:\n" + 
                                          "\n".join(RARITY_MAPPING.values()))
            return

        if status == "on":
            if len(context.args) != 3 or "-" not in context.args[2]:
                await update.message.reply_text(
                    "❌ Invalid format. Usage:\n"
                    "`/R-market <rarity_emoji> on <min-max>`\n\n"
                    "Example:\n"
                    "`/R-market ⚪️ on 100-200`",
                    parse_mode="Markdown"
                )
                return

            try:
                min_price, max_price = map(int, context.args[2].split("-"))
                if min_price >= max_price:
                    raise ValueError("Min price must be less than max price")
            except ValueError as e:
                await update.message.reply_text(f"❌ Invalid price range: {str(e)}")
                return

            await rarity_collection.update_one(
                {"rarity_id": str(rarity_id)},
                {"$set": {
                    "active": True,
                    "price_range": [min_price, max_price],
                    "rarity_name": RARITY_MAPPING[rarity_id]
                }},
                upsert=True
            )
            await update.message.reply_text(
                f"✅ {RARITY_MAPPING[rarity_id]} added to market with price range {min_price}-{max_price}."
            )

        elif status == "off":
            await rarity_collection.update_one(
                {"rarity_id": str(rarity_id)},
                {"$set": {"active": False, "price_range": None}}
            )
            await update.message.reply_text(f"✅ {RARITY_MAPPING[rarity_id]} removed from market.")

        else:
            await update.message.reply_text("❌ Invalid status. Use 'on' or 'off'.")

    except Exception as e:
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")
        raise e

