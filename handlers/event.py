from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from config import EVENT_MAPPING, SUDO_USERS  # Assuming SUDO_USERS is a list in config
from db import db
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

async def set_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to set global events with activation status (restricted to sudo users)."""
    user_id = update.effective_user.id

    if user_id not in SUDO_USERS:  # Check against sudo users list
        await update.message.reply_text("❌ You do not have permission to use this command.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /setevent <command> [args]\n\n"
            "Commands:\n"
            "• add <emoji> - Add an active event\n"
            "• remove <emoji> - Remove an event\n"
            "• list - Show current active events\n"
            "• clear - Remove all events"
        )
        return

    command = context.args[0].lower()
    args = context.args[1:]

    if command == "add":
        if not args:
            await update.message.reply_text("Usage: /setevent add <event emoji> [additional emojis]")
            return

        invalid_emojis = [emoji for emoji in args if emoji not in EVENT_MAPPING]
        if invalid_emojis:
            await update.message.reply_text(
                f"❌ Invalid event emojis: {', '.join(invalid_emojis)}\n"
                f"Valid options: {', '.join(EVENT_MAPPING.keys())}"
            )
            return

        event_names = [EVENT_MAPPING[emoji] for emoji in args]

        await db["spawn_settings"].update_one(
            {"type": "global"},
            {"$addToSet": {"events": {"$each": event_names}}},
            upsert=True
        )

        await update.message.reply_text(f"✅ Added events: {', '.join(event_names)}")
        logger.info(f"Added events: {event_names}")

    elif command == "remove":
        if not args:
            await update.message.reply_text("Usage: /setevent remove <event emoji> [additional emojis]")
            return

        invalid_emojis = [emoji for emoji in args if emoji not in EVENT_MAPPING]
        if invalid_emojis:
            await update.message.reply_text(
                f"❌ Invalid event emojis: {', '.join(invalid_emojis)}\n"
                f"Valid options: {', '.join(EVENT_MAPPING.keys())}"
            )
            return

        event_names = [EVENT_MAPPING[emoji] for emoji in args]

        result = await db["spawn_settings"].update_one(
            {"type": "global"},
            {"$pull": {"events": {"$in": event_names}}}
        )

        if result.modified_count > 0:
            await update.message.reply_text(f"✅ Removed events: {', '.join(event_names)}")
            logger.info(f"Removed events: {event_names}")
        else:
            await update.message.reply_text("ℹ️ No matching events found to remove")

    elif command == "list":
        active_events = await get_active_events()
        if not active_events:
            await update.message.reply_text("ℹ️ No active events currently set")
            return

        emoji_map = {v: k for k, v in EVENT_MAPPING.items()}
        event_display = [f"{emoji_map.get(name, '❓')} {name}" for name in active_events]

        await update.message.reply_text("📋 Active Events:\n" + "\n".join(event_display))

    elif command == "clear":
        await db["spawn_settings"].update_one(
            {"type": "global"},
            {"$set": {"events": []}}
        )
        await update.message.reply_text("✅ All events have been cleared")
        logger.info("Cleared all events")

    else:
        await update.message.reply_text("❌ Unknown command. Use /setevent for usage instructions")

async def get_active_events() -> List[str]:
    """Fetch all currently active events."""
    try:
        doc = await db["spawn_settings"].find_one({"type": "global"})
        return doc.get("events", []) if doc else []
    except Exception as e:
        logger.error(f"Error fetching active events: {e}")
        return []

def register_event_commands(application):
    """Register the event-related command handlers."""
    application.add_handler(CommandHandler("setevent", set_event))
