from telegram import Update
from telegram.ext import ContextTypes
import html
import logging
from config import SUDO_USERS  # Import SUDO_USERS from config
from db import user_collection, group_collection  # Import collections from the database

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast a replied message to all users and groups in the database."""
    try:
        # Ensure the command is used by a sudo user
        if update.message.from_user.id not in SUDO_USERS:
            await update.message.reply_text(
                "🚫 You are not authorized to use this commandHTML"
            )
            return

        # Ensure the message is a reply
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "Please reply to the message you want to broadcast.", parse_mode="HTML"
            )
            return

        replied_message = update.message.reply_to_message

        # Initialize counters
        stats = {"successful_users": 0, "failed_users": 0, "successful_groups": 0, "failed_groups": 0}

        # Fetch all user and group IDs
        user_ids = [user["user_id"] for user in await user_collection.find({}, {"user_id": 1}).to_list(length=None)]
        group_ids = [group["group_id"] for group in await group_collection.find({}, {"group_id": 1}).to_list(length=None)]

        # Broadcast message
        for user_id in user_ids:
            try:
                await context.bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=replied_message.chat_id,
                    message_id=replied_message.message_id
                )
                stats["successful_users"] += 1
                logger.info(f"Broadcasted to user {user_id}")
            except Exception as e:
                stats["failed_users"] += 1
                logger.error(f"Failed to broadcast to user {user_id}: {str(e)}")

        for group_id in group_ids:
            try:
                await context.bot.forward_message(
                    chat_id=group_id,
                    from_chat_id=replied_message.chat_id,
                    message_id=replied_message.message_id
                )
                stats["successful_groups"] += 1
                logger.info(f"Broadcasted to group {group_id}")
            except Exception as e:
                stats["failed_groups"] += 1
                logger.error(f"Failed to broadcast to group {group_id}: {str(e)}")

        # Send summary
        await update.message.reply_text(
            f"<b>Broadcast Summary</b>\n"
            f"{'━' * 25}\n\n"
            f"<b>Users:</b>\n✅ {stats['successful_users']} | ❌ {stats['failed_users']}\n\n"
            f"<b>Groups:</b>\n✅ {stats['successful_groups']} | ❌ {stats['failed_groups']}",
            parse_mode="HTML"
        )

    except Exception as e:
        await update.message.reply_text(
            f"An error occurred during broadcast: {html.escape(str(e))}", parse_mode="HTML"
        )
        logger.error(f"Broadcast error: {str(e)}")
