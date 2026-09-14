import html
import logging
from telegram import Update
from telegram.ext import ContextTypes
from db import collection as character_collection, user_collection

logger = logging.getLogger(__name__)

# Log group ID for exchange notifications
LOG_GROUP_ID = -1002655715837

async def exchange_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Exchange elixir characters for their attached counterparts.
    Requires 3+ copies of an elixir character with valid attachment.
    """
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    user_username = update.effective_user.username or None
    
    if not context.args:
        await update.message.reply_text(
            "Specify character ID for exchange\n"
            "Format: /exchange <character_id>"
        )
        return

    try:
        character_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid character ID format.")
        return

    try:
        # Fetch character data
        character = await character_collection.find_one({"character_id": character_id})
        if not character:
            await update.message.reply_text(f"Character {character_id} does not exist.")
            return

        # Verify elixir rarity requirement
        if character.get("rarity") != "🍭 Elixir":
            await update.message.reply_text(
                f"{html.escape(character.get('name', 'Unknown'))} cannot be exchanged. "
                f"Only elixir rarity characters are eligible."
            )
            return

        # Check attachment requirement
        attached_character_id = character.get("attached_character_id")
        if not attached_character_id:
            await update.message.reply_text(
                f"{html.escape(character.get('name', 'Unknown'))} has no attached character. "
                f"Exchange unavailable."
            )
            return

        # Verify attached character exists
        attached_character = await character_collection.find_one({"character_id": attached_character_id})
        if not attached_character:
            await update.message.reply_text(
                f"Target character {attached_character_id} missing from database. "
                f"Exchange cannot proceed."
            )
            return

        # Get user collection data (using user_id as the field, not _id)
        user_data = await user_collection.find_one({"user_id": user_id})
        if not user_data:
            await update.message.reply_text("No collection found for your account.")
            return

        user_characters = user_data.get("characters", {})
        current_count = user_characters.get(str(character_id), 0)

        # Verify minimum count requirement
        if current_count < 3:
            await update.message.reply_text(
                f"Insufficient copies of {html.escape(character.get('name', 'Unknown'))}. "
                f"Required: 3, Available: {current_count}"
            )
            return

        # Calculate exchange amounts
        elixir_deduction = 3 if current_count > 3 else current_count
        remaining_elixir = current_count - elixir_deduction
        
        current_attached_count = user_characters.get(str(attached_character_id), 0)
        new_attached_count = current_attached_count + 1

        # Execute database updates
        update_operations = {
            "first_name": user_name,
            "username": user_username,
            f"characters.{attached_character_id}": new_attached_count
        }
        
        # Handle elixir character count update or removal
        if remaining_elixir > 0:
            update_operations[f"characters.{character_id}"] = remaining_elixir
        else:
            # Remove the character entirely if count reaches 0
            await user_collection.update_one(
                {"user_id": user_id},
                {"$unset": {f"characters.{character_id}": ""}}
            )

        # Update user collection with new counts
        await user_collection.update_one(
            {"user_id": user_id},
            {"$set": update_operations}
        )

        # Format completion message
        player_name = html.escape(user_name or "Player")
        elixir_name = html.escape(character.get("name", "Unknown"))
        elixir_series = html.escape(character.get("anime", "Unknown"))
        target_name = html.escape(attached_character.get("name", "Unknown"))
        target_series = html.escape(attached_character.get("anime", "Unknown"))
        target_rarity = html.escape(attached_character.get("rarity", "Unknown"))

        completion_message = (
            f"<b>Exchange Completed</b>\n\n"
            f"Trader: {player_name}\n\n"
            f"<b>Consumed:</b>\n"
            f"{elixir_deduction} copies of {elixir_name}\n"
            f"From: {elixir_series}\n\n"
            f"<b>Acquired:</b>\n"
            f"1 copy of {target_name} ({target_rarity})\n"
            f"From: {target_series}\n\n"
            f"<b>Updated Inventory:</b>\n"
            f"{elixir_name}: {remaining_elixir} remaining\n"
            f"{target_name}: {new_attached_count} total"
        )

        # Send log to group
        log_message = (
            f"<b>🔄 EXCHANGE COMPLETED</b>\n\n"
            f"<b>User:</b> {player_name} (ID: {user_id})\n"
            f"<b>Chat:</b> {html.escape(update.effective_chat.title or 'Private')}\n\n"
            f"<b>Exchange Details:</b>\n"
            f"• Consumed: {elixir_deduction}x {elixir_name}\n"
            f"• Received: 1x {target_name} ({target_rarity})\n\n"
            f"<b>Updated Counts:</b>\n"
            f"• {elixir_name}: {remaining_elixir} remaining\n"
            f"• {target_name}: {new_attached_count} total"
        )
        
        try:
            await context.bot.send_message(
                chat_id=LOG_GROUP_ID,
                text=log_message,
                parse_mode="HTML"
            )
        except Exception as log_error:
            logger.error(f"Failed to send exchange log to group: {log_error}")

        await update.message.reply_text(completion_message, parse_mode="HTML")

        logger.info(
            f"Exchange processed - User {user_id}: {elixir_deduction}x{character_id} -> 1x{attached_character_id}"
        )

    except Exception as e:
        logger.error(f"Exchange processing error: {e}")
        await update.message.reply_text("Exchange failed due to system error. Please retry.")
