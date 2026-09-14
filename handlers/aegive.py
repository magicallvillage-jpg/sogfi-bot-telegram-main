from telegram import Update, User
from telegram.ext import Application, CommandHandler, ContextTypes
from config import SUDO_USERS
from db import user_collection
import os


async def aegive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sudo command to grant Astrites to a user."""
    sender_id = update.effective_user.id
    
    # Check if sender is a sudo user
    if sender_id not in SUDO_USERS:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return
    
    recipient_id = None
    amount = None

    # If message is a reply, get recipient's ID
    if update.message.reply_to_message:
        recipient: User = update.message.reply_to_message.from_user
        recipient_id = recipient.id
        amount_text = " ".join(context.args) if context.args else None
    elif len(context.args) >= 2:
        try:
            recipient_id = int(context.args[0])
            amount_text = context.args[1]
        except ValueError:
            await update.message.reply_text("Invalid input. User ID and amount must be numbers.")
            return
    else:
        await update.message.reply_text("Usage: /aegive <user_id> <amount> OR reply to a user with /aegive <amount>")
        return

    # Validate recipient
    recipient = await user_collection.find_one({"user_id": recipient_id})
    if not recipient:
        await update.message.reply_text("Recipient not found.")
        return
    
    try:
        amount = int(amount_text)
        if amount <= 0:
            await update.message.reply_text("Invalid amount. Please enter a positive number.")
            return
    except ValueError:
        await update.message.reply_text("Invalid amount. It must be a positive number.")
        return

    # Update recipient's balance
    await user_collection.update_one(
        {"user_id": recipient_id},
        {"$set": {"astrites": recipient.get("astrites", 0) + amount}}
    )

    await update.message.reply_text(f"𝗔𝗦𝗧𝗥𝗜𝗧𝗘𝗦 𝗚𝗥𝗔𝗡𝗧𝗘𝗗: Æ {amount}")


async def aeremove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sudo command to remove Astrites from a user. Removes all if no amount is specified."""
    sender_id = update.effective_user.id
    
    # Check if sender is a sudo user
    if sender_id not in SUDO_USERS:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return
    
    recipient_id = None
    amount = None

    # If message is a reply, get recipient's ID
    if update.message.reply_to_message:
        recipient: User = update.message.reply_to_message.from_user
        recipient_id = recipient.id
        amount_text = " ".join(context.args) if context.args else None
    elif len(context.args) >= 1:
        try:
            recipient_id = int(context.args[0])
            amount_text = context.args[1] if len(context.args) > 1 else None
        except ValueError:
            await update.message.reply_text("Invalid input. User ID must be a number.")
            return
    else:
        await update.message.reply_text("Usage: /aeremove <user_id> [<amount>] OR reply to a user with /aeremove [<amount>]")
        return

    # Validate recipient
    recipient = await user_collection.find_one({"user_id": recipient_id})
    if not recipient:
        await update.message.reply_text("Recipient not found.")
        return

    current_balance = recipient.get("astrites", 0)
    
    # If no amount is specified, remove all Astrites
    if not amount_text:
        if current_balance == 0:
            await update.message.reply_text("User already has Æ 0.")
            return
        amount = current_balance
    else:
        try:
            amount = int(amount_text)
            if amount <= 0:
                await update.message.reply_text("Invalid amount. Please enter a positive number.")
                return
            if current_balance < amount:
                await update.message.reply_text(f"Cannot remove Æ {amount}. User only has Æ {current_balance}.")
                return
        except ValueError:
            await update.message.reply_text("Invalid amount. It must be a positive number.")
            return

    # Update recipient's balance
    await user_collection.update_one(
        {"user_id": recipient_id},
        {"$set": {"astrites": current_balance - amount}}
    )

    await update.message.reply_text(f"�_A𝗦𝗧𝗥𝗜𝗧𝗘𝗦 𝗥𝗘𝗠𝗢𝗩𝗘𝗗: Æ {amount}")


