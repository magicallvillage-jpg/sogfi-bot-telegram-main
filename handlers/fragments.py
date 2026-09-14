import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db import db, collection as character_collection
from config import SUDO_USERS as ADMIN_IDS
from io import BytesIO

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Constants
SPECIAL_GROUP_ID = "-1002588814659"
ELIXIR_RARITY = "🍭 Elixir"

# Database collections
special_group_settings = db["special_group_settings"]

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
    import random
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

# Unified fragments command with safe settings access
async def fragments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await init_special_group_settings()
    
    if not context.args:
        return await fragments_help(update)
    
    subcommand = context.args[0].lower()
    
    if subcommand == "help":
        await fragments_help(update)
    elif subcommand == "on":
        await fragments_on(update, context)
    elif subcommand == "off":
        await fragments_off(update, context)
    elif subcommand == "stop":
        await fragments_stop(update, context)
    elif subcommand == "list":
        await fragments_list(update)
    elif subcommand == "status":
        await fragments_status(update)
    elif subcommand == "toggle":
        await fragments_toggle(update)
    else:
        await update.message.reply_text("❌ Unknown subcommand. Use /fragments help for instructions.")

async def fragments_help(update: Update):
    help_text = """
🍭 Fragments System Commands:

/fragments help - Show this help
/fragments on <id> - Allow character for Elixir spawns
/fragments off <id> - Disallow character for Elixir spawns
/fragments stop <count> <id> - Stop character after X spawns
/fragments list - List allowed Elixir characters (as TXT file)
/fragments status - Show current settings
/fragments toggle - Toggle Elixir spawning

Example:
/fragments on 123 - Allow character with ID 123
/fragments stop 5 123 - Stop character 123 after 5 more spawns
"""
    await update.message.reply_text(help_text)

async def fragments_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Please provide a character ID.")
        return
    
    try:
        character_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Character ID must be an integer.")
        return
    
    # Verify character exists
    character = await character_collection.find_one({"character_id": character_id})
    if not character:
        await update.message.reply_text("❌ Character not found.")
        return
    
    await allow_elixir_character(character_id)
    await update.message.reply_text(f"✅ Character {character_id} added to allowed Elixir characters.")

async def fragments_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Please provide a character ID.")
        return
    
    try:
        character_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Character ID must be an integer.")
        return
    
    # Verify character exists
    character = await character_collection.find_one({"character_id": character_id})
    if not character:
        await update.message.reply_text("❌ Character not found.")
        return
    
    await disallow_elixir_character(character_id)
    await update.message.reply_text(f"✅ Character {character_id} removed from allowed Elixir characters.")

async def fragments_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text("❌ Usage: /fragments stop <count> <character_id>")
        return
    
    try:
        count = int(context.args[1])
        character_id = int(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ Both count and character ID must be integers.")
        return
    
    # Verify character exists
    character = await character_collection.find_one({"character_id": character_id})
    if not character:
        await update.message.reply_text("❌ Character not found.")
        return
    
    settings = await get_special_group_settings()
    allowed_characters = settings.get("allowed_characters", [])
    if character_id not in allowed_characters:
        await update.message.reply_text("⚠️ Character not in allowed list. Adding it first.")
        await allow_elixir_character(character_id)
    
    await set_elixir_stop_count(character_id, count)
    await update.message.reply_text(
        f"✅ Character {character_id} will be stopped after {count} more spawns."
    )

async def fragments_list(update: Update):
    settings = await get_special_group_settings()
    allowed_characters = settings.get("allowed_characters", [])
    if not allowed_characters:
        await update.message.reply_text("❌ No allowed Elixir characters.")
        return
    
    chars = await character_collection.find(
        {"character_id": {"$in": allowed_characters}}
    ).to_list(length=None)
    
    # Create text file content
    file_content = "🍭 Allowed Elixir Characters:\n\n"
    stop_counts = settings.get("stop_counts", {})
    
    for char in chars:
        char_id = char["character_id"]
        stop_info = f" (stops after {stop_counts.get(char_id, '∞')} spawns)" if char_id in stop_counts else ""
        file_content += f"ID: {char_id}\nName: {char.get('name', 'Unknown')}\nRarity: {char.get('rarity', 'Unknown')}{stop_info}\n\n"
    
    # Create a file-like object in memory
    file = BytesIO(file_content.encode('utf-8'))
    file.name = "elixir_characters.txt"
    
    await update.message.reply_document(
        document=file,
        caption="Here's the list of allowed Elixir characters"
    )

async def fragments_status(update: Update):
    settings = await get_special_group_settings()
    status = "🍭 Elixir Spawning Status:\n"
    status += f"• Enabled: {'✅ Yes' if settings.get('enabled', True) else '❌ No'}\n"
    status += f"• Allowed Characters: {len(settings.get('allowed_characters', []))}\n"
    status += f"• Characters with Stop Count: {len(settings.get('stop_counts', {}))}"
    
    await update.message.reply_text(status)

async def fragments_toggle(update: Update):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return
    
    settings = await get_special_group_settings()
    new_state = not settings.get('enabled', True)  # Default to True if missing
    await toggle_special_spawn(new_state)
    
    status = "ENABLED" if new_state else "DISABLED"
    await update.message.reply_text(f"✅ Special Elixir spawning is now {status}.")

# Register fragment handlers
def register_fragment_handlers(application):
    application.add_handler(CommandHandler("fragments", fragments))
