import html
from datetime import datetime
from telegram import Update, ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import ContextTypes
from db import user_collection, group_collection, db
from config import SUDO_USERS

group_settings = db["gsettings"]

async def set_group_threshold(group_id, count):
    await group_settings.update_one(
        {"group_id": str(group_id)},
        {"$set": {"spawn_threshold": count}},
        upsert=True
    )

async def set_spawn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in {"group", "supergroup"}:
        await update.message.reply_text("This command can only be used in a group.")
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check permissions
    is_sudo = user_id in SUDO_USERS
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        is_admin = isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
    except Exception as e:
        await update.message.reply_text(f"Error checking admin status: {e}")
        return

    if not (is_sudo or is_admin):
        await update.message.reply_text("Only group admins and sudo users can use this command.")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /setspawn <number>")
        return

    count = int(context.args[0])
    MIN_ADMIN_THRESHOLD = 100

    # Permission hierarchy: SUDO > Admin
    if is_sudo:
        # Sudo users can set any value
        pass
    elif is_admin:
        # Regular admins have restrictions
        if count < MIN_ADMIN_THRESHOLD:
            await update.message.reply_text(
                f"Admins cannot set thresholds below {MIN_ADMIN_THRESHOLD}. "
                f"Ask a sudo user to set lower values."
            )
            return

    await set_group_threshold(str(chat_id), count)
    await update.message.reply_text(
        f"✔️ Spawn threshold set to {count} messages for this group.\n"
        f"Set by: {'SUDO user' if is_sudo else 'Group admin'}"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in SUDO_USERS:
        return await update.message.reply_text("You are not authorized to use this command.")
    
    try:
        total_users = await user_collection.count_documents({})
        total_groups = await group_collection.count_documents({})
        active_groups = await group_collection.count_documents({
            "user_stats": {"$exists": True, "$not": {"$size": 0}}
        })
        
        await update.message.reply_html(
            f"<b>System Statistics</b>\n\n"
            f"<b>⇨ Total Users:</b> {total_users}\n"
            f"<b>⇨ Total Groups:</b> {total_groups}\n"
            f"<b>⇨ Active Groups:</b> {active_groups}\n\n"
            f"<i>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        
    except Exception as e:
        await update.message.reply_text(f"Error fetching stats: {e.__class__.__name__} - {str(e)}")

async def kill_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in SUDO_USERS:
        return await update.message.reply_text("You are not authorized to use this command.")
    
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /kill <user_id>")
        return

    user_id = int(context.args[0])

    result = await user_collection.delete_one({"user_id": user_id})

    if result.deleted_count > 0:
        await update.message.reply_text(f"✅ User {user_id} has been removed from the database.")
    else:
        await update.message.reply_text(f"⚠️ User {user_id} not found in the database.")
