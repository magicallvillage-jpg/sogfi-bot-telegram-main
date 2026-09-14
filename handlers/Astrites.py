from telegram import Update, User
from telegram.ext import Application, CommandHandler, CallbackContext
from db import user_collection

LOG_CHAT_ID = "-1002737691607"

async def pay_astrites(update: Update, context: CallbackContext):
    """Command to send Astrites to another user."""
    sender_id = update.effective_user.id
    sender = await user_collection.find_one({"user_id": sender_id})

    if not sender:
        await update.message.reply_text("You are not registered in the database.")
        return
    
    # If message is a reply, get recipient's ID
    if update.message.reply_to_message:
        recipient: User = update.message.reply_to_message.from_user
        recipient_id = recipient.id
        # Check if user is replying to themselves
        if recipient_id == sender_id:
            await update.message.reply_text("You cannot send Astrites to yourself.")
            return
        try:
            amount = int(context.args[0]) if context.args else None
        except (ValueError, IndexError):
            await update.message.reply_text("Please specify a valid amount after the command.")
            return
    elif len(context.args) >= 2:
        try:
            recipient_id = int(context.args[0])
            # Check if user is trying to send to themselves
            if recipient_id == sender_id:
                await update.message.reply_text("You cannot send Astrites to yourself.")
                return
            amount = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Invalid input. User ID and amount must be numbers.")
            return
    else:
        await update.message.reply_text("Usage: /atransfer <user_id> <amount> OR reply to a user with /atransfer <amount>")
        return

    # Validate amount
    if not amount or amount <= 0:
        await update.message.reply_text("Invalid transaction amount. Please enter a positive number.")
        return

    # Get recipient
    recipient = await user_collection.find_one({"user_id": recipient_id})
    if not recipient:
        await update.message.reply_text("Recipient not found in the database.")
        return

    # Check sender's balance
    sender_balance = sender.get("astrites", 0)
    if sender_balance < amount:
        await update.message.reply_text("Insufficient Astrites to complete the payment.")
        return

    # Perform transaction
    try:
        # Deduct from sender
        await user_collection.update_one(
            {"user_id": sender_id},
            {"$inc": {"astrites": -amount}}
        )
        # Add to recipient
        await user_collection.update_one(
            {"user_id": recipient_id},
            {"$inc": {"astrites": amount}}
        )
        
        # Get updated balances
        updated_sender = await user_collection.find_one({"user_id": sender_id})
        updated_recipient = await user_collection.find_one({"user_id": recipient_id})
        
        # Format success message
        success_msg = (
            f"𝗔𝗦𝗧𝗥𝗜𝗧𝗘𝗦 𝗧𝗥𝗔𝗡𝗦𝗔𝗖𝗧𝗜𝗢𝗡\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"𝗦𝗲𝗻𝗱𝗲𝗿: {update.effective_user.first_name}\n"
            f"𝗥𝗲𝗰𝗶𝗽𝗶𝗲𝗻𝘁: {recipient.get('first_name', 'User')}\n"
            f"𝗔𝗺𝗼𝘂𝗻𝘁: Æ {amount}\n"
            f"𝗦𝘁𝗮𝘁𝘂𝘀: 𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱\n"
            f"━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(success_msg)
        
        # Log the transaction
        log_msg = (
            "#AST_TRANSFER\n"
            f"Sender: {update.effective_user.full_name} (@{update.effective_user.username or 'N/A'}) [{sender_id}]\n"
            f"Recipient: {recipient.get('first_name', 'Unknown')} (@{recipient.get('username', 'N/A')}) [{recipient_id}]\n"
            f"Amount: Æ {amount}\n"
            f"Sender New Balance: Æ {updated_sender.get('astrites', 0)}\n"
            f"Recipient New Balance: Æ {updated_recipient.get('astrites', 0)}"
        )
        await context.bot.send_message(chat_id=LOG_CHAT_ID, text=log_msg)
        
    except Exception as e:
        error_msg = "An error occurred during the transaction. Please try again."
        await update.message.reply_text(error_msg)
        
        # Log the error
        error_log = (
            "#AST_TRANSFER_ERROR\n"
            f"Sender: {update.effective_user.full_name} [{sender_id}]\n"
            f"Recipient ID: {recipient_id}\n"
            f"Amount: Æ {amount}\n"
            f"Error: {str(e)}"
        )
        await context.bot.send_message(chat_id=LOG_CHAT_ID, text=error_log)
        print(f"Transaction error: {e}")

async def get_vault(update: Update, context: CallbackContext):
    """Command to check user's complete inventory (Astrites, Virex, Vault)."""
    user_id = update.effective_user.id
    user = await user_collection.find_one({"user_id": user_id})
    
    if not user:
        await update.message.reply_text("User not found in the database.")
        return
    
    astrites = user.get("astrites", 0)
    virex = user.get("virex", 0)
    vault = user.get("vault", 0)
    
    # Calculate total worth in Astrites (VX to Æ conversion)
    total_worth = astrites + (virex * 400) + vault
    
    await update.message.reply_text(
        f"𝗜𝗡𝗩𝗘𝗡𝗧𝗢𝗥𝗬\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"𝗨𝘀𝗲𝗿: {update.effective_user.first_name}\n\n"
        f"𝗔𝘀𝘁𝗿𝗶𝘁𝗲𝘀: Æ {astrites}\n"
        f"𝗩𝗶𝗿𝗲𝘅: VX {virex}\n"
        f"𝗩𝗮𝘂𝗹𝘁: Æ {vault}\n\n"
        f"𝗧𝗼𝘁𝗮𝗹 𝗪𝗼𝗿𝘁𝗵: Æ {total_worth}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"𝗖𝗼𝗻𝘃𝗲𝗿𝘀𝗶𝗼𝗻 𝗥𝗮𝘁𝗲: 400 Æ = 1 VX"
    )

async def swap_currency(update: Update, context: CallbackContext):
    """Unified command to swap between Astrites and Virex currencies."""
    user_id = update.effective_user.id
    user = await user_collection.find_one({"user_id": user_id})
    
    if not user:
        await update.message.reply_text("You are not registered in the database.")
        return
    
    # Show help if no arguments provided
    if not context.args:
        help_msg = (
            f"💱 𝗖𝗨𝗥𝗥𝗘𝗡𝗖𝗬 𝗦𝗪𝗔𝗣 𝗚𝗨𝗜𝗗𝗘\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"𝗨𝘀𝗮𝗴𝗲:\n"
            f"/swap <currency> <amount>\n\n"
            f"𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝗲𝗱 𝗖𝘂𝗿𝗿𝗲𝗻𝗰𝗶𝗲𝘀:\n"
            f"• ae, ast, astrites → Convert Æ to VX\n"
            f"• vx, virex → Convert VX to Æ\n\n"
            f"𝗘𝘅𝗮𝗺𝗽𝗹𝗲𝘀:\n"
            f"/swap ae 800 → Convert 800 Æ to 2 VX\n"
            f"/swap vx 5 → Convert 5 VX to 2000 Æ\n"
            f"/swap astrites 1200 → Convert 1200 Æ to 3 VX\n"
            f"/swap virex 10 → Convert 10 VX to 4000 Æ\n\n"
            f"𝗘𝘅𝗰𝗵𝗮𝗻𝗴𝗲 𝗥𝗮𝘁𝗲:\n"
            f"1 VX = 400 Æ\n"
            f"400 Æ = 1 VX\n\n"
            f"𝗡𝗼𝘁𝗲: Only exact multiples of 400 Æ can be converted to VX"
        )
        await update.message.reply_text(help_msg)
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Invalid format!\n\n"
            "Usage: /swap <currency> <amount>\n"
            "Example: /swap ae 800 or /swap vx 2\n\n"
            "Use /swap without arguments to see the full guide."
        )
        return
    
    currency = context.args[0].lower()
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("Please enter a positive amount to swap.")
            return
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a valid number.")
        return
    
    current_astrites = user.get("astrites", 0)
    current_virex = user.get("virex", 0)
    
    # Convert Astrites to Virex
    if currency in ['ae', 'ast', 'astrites']:
        # Check if amount is divisible by 400
        if amount % 400 != 0:
            await update.message.reply_text(
                f"❌ 𝗜𝗡𝗩𝗔𝗟𝗜𝗗 𝗔𝗠𝗢𝗨𝗡𝗧\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"Only multiples of 400 Æ can be converted to VX.\n\n"
                f"𝗬𝗼𝘂𝗿 𝗮𝗺𝗼𝘂𝗻𝘁: Æ {amount}\n"
                f"𝗡𝗲𝗮𝗿𝗲𝘀𝘁 𝘃𝗮𝗹𝗶𝗱 𝗮𝗺𝗼𝘂𝗻𝘁𝘀:\n"
                f"• Æ {(amount // 400) * 400} (converts to {amount // 400} VX)\n"
                f"• Æ {((amount // 400) + 1) * 400} (converts to {(amount // 400) + 1} VX)"
            )
            return
        
        virex_to_receive = amount // 400
        
        if current_astrites < amount:
            await update.message.reply_text(
                f"❌ 𝗜𝗡𝗦𝗨𝗙𝗙𝗜𝗖𝗜𝗘𝗡𝗧 𝗔𝗦𝗧𝗥𝗜𝗧𝗘𝗦\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"𝗥𝗲𝗾𝘂𝗶𝗿𝗲𝗱: Æ {amount}\n"
                f"𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲: Æ {current_astrites}\n"
                f"𝗦𝗵𝗼𝗿𝘁𝗮𝗴𝗲: Æ {amount - current_astrites}\n\n"
                f"𝗠𝗮𝘅 𝗰𝗼𝗻𝘃𝗲𝗿𝘁𝗮𝗯𝗹𝗲: Æ {(current_astrites // 400) * 400} → {current_astrites // 400} VX"
            )
            return
        
        # Perform conversion
        try:
            new_astrites = current_astrites - amount
            new_virex = current_virex + virex_to_receive
            
            await user_collection.update_one(
                {"user_id": user_id}, 
                {"$set": {"astrites": new_astrites, "virex": new_virex}}
            )
            
            success_msg = (
                f"✅ 𝗦𝗪𝗔𝗣 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"𝗨𝘀𝗲𝗿: {update.effective_user.first_name}\n"
                f"𝗦𝘄𝗮𝗽𝗽𝗲𝗱: Æ {amount} → VX {virex_to_receive}\n\n"
                f"𝗡𝗘𝗪 𝗕𝗔𝗟𝗔𝗡𝗖𝗘𝗦:\n"
                f"𝗔𝘀𝘁𝗿𝗶𝘁𝗲𝘀: Æ {new_astrites}\n"
                f"𝗩𝗶𝗿𝗲𝘅: VX {new_virex}\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            await update.message.reply_text(success_msg)
            
            # Log the conversion
            log_msg = (
                "#CURRENCY_SWAP\n"
                f"User: {update.effective_user.full_name} (@{update.effective_user.username or 'N/A'}) [{user_id}]\n"
                f"Type: Æ → VX\n"
                f"Swapped: Æ {amount} → VX {virex_to_receive}\n"
                f"New Astrites: Æ {new_astrites}\n"
                f"New Virex: VX {new_virex}"
            )
            await context.bot.send_message(chat_id=LOG_CHAT_ID, text=log_msg)
            
        except Exception as e:
            await update.message.reply_text("❌ An error occurred during the swap. Please try again.")
            error_log = (
                "#CURRENCY_SWAP_ERROR\n"
                f"User: {update.effective_user.full_name} [{user_id}]\n"
                f"Type: Æ → VX\n"
                f"Amount: Æ {amount}\n"
                f"Error: {str(e)}"
            )
            await context.bot.send_message(chat_id=LOG_CHAT_ID, text=error_log)
            print(f"Swap error: {e}")
    
    # Convert Virex to Astrites
    elif currency in ['vx', 'virex']:
        if current_virex < amount:
            await update.message.reply_text(
                f"❌ 𝗜𝗡𝗦𝗨𝗙𝗙𝗜𝗖𝗜𝗘𝗡𝗧 𝗩𝗜𝗥𝗘𝗫\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"𝗥𝗲𝗾𝘂𝗶𝗿𝗲𝗱: VX {amount}\n"
                f"𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲: VX {current_virex}\n"
                f"𝗦𝗵𝗼𝗿𝘁𝗮𝗴𝗲: VX {amount - current_virex}"
            )
            return
        
        astrites_to_receive = amount * 400
        
        try:
            new_virex = current_virex - amount
            new_astrites = current_astrites + astrites_to_receive
            
            await user_collection.update_one(
                {"user_id": user_id}, 
                {"$set": {"virex": new_virex, "astrites": new_astrites}}
            )
            
            success_msg = (
                f"✅ 𝗦𝗪𝗔𝗣 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"𝗨𝘀𝗲𝗿: {update.effective_user.first_name}\n"
                f"𝗦𝘄𝗮𝗽𝗽𝗲𝗱: VX {amount} → Æ {astrites_to_receive}\n\n"
                f"𝗡𝗘𝗪 𝗕𝗔𝗟𝗔𝗡𝗖𝗘𝗦:\n"
                f"𝗩𝗶𝗿𝗲𝘅: VX {new_virex}\n"
                f"𝗔𝘀𝘁𝗿𝗶𝘁𝗲𝘀: Æ {new_astrites}\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            await update.message.reply_text(success_msg)
            
            # Log the conversion
            log_msg = (
                "#CURRENCY_SWAP\n"
                f"User: {update.effective_user.full_name} (@{update.effective_user.username or 'N/A'}) [{user_id}]\n"
                f"Type: VX → Æ\n"
                f"Swapped: VX {amount} → Æ {astrites_to_receive}\n"
                f"New Virex: VX {new_virex}\n"
                f"New Astrites: Æ {new_astrites}"
            )
            await context.bot.send_message(chat_id=LOG_CHAT_ID, text=log_msg)
            
        except Exception as e:
            await update.message.reply_text("❌ An error occurred during the swap. Please try again.")
            error_log = (
                "#CURRENCY_SWAP_ERROR\n"
                f"User: {update.effective_user.full_name} [{user_id}]\n"
                f"Type: VX → Æ\n"
                f"Amount: VX {amount}\n"
                f"Error: {str(e)}"
            )
            await context.bot.send_message(chat_id=LOG_CHAT_ID, text=error_log)
            print(f"Swap error: {e}")
    
    else:
        await update.message.reply_text(
            f"❌ 𝗨𝗡𝗦𝗨𝗣𝗣𝗢𝗥𝗧𝗘𝗗 𝗖𝗨𝗥𝗥𝗘𝗡𝗖𝗬\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Supported currencies:\n"
            f"• ae, ast, astrites (for Æ → VX)\n"
            f"• vx, virex (for VX → Æ)\n\n"
            f"Use /swap without arguments for the complete guide."
        )

async def pay_virex(update: Update, context: CallbackContext):
    """Command to send Virex to another user."""
    sender_id = update.effective_user.id
    sender = await user_collection.find_one({"user_id": sender_id})

    if not sender:
        await update.message.reply_text("You are not registered in the database.")
        return
    
    # If message is a reply, get recipient's ID
    if update.message.reply_to_message:
        recipient: User = update.message.reply_to_message.from_user
        recipient_id = recipient.id
        # Check if user is replying to themselves
        if recipient_id == sender_id:
            await update.message.reply_text("You cannot send Virex to yourself.")
            return
        try:
            amount = int(context.args[0]) if context.args else None
        except (ValueError, IndexError):
            await update.message.reply_text("Please specify a valid amount after the command.")
            return
    elif len(context.args) >= 2:
        try:
            recipient_id = int(context.args[0])
            # Check if user is trying to send to themselves
            if recipient_id == sender_id:
                await update.message.reply_text("You cannot send Virex to yourself.")
                return
            amount = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Invalid input. User ID and amount must be numbers.")
            return
    else:
        await update.message.reply_text("Usage: /vtransfer <user_id> <amount> OR reply to a user with /vtransfer <amount>")
        return

    # Validate amount
    if not amount or amount <= 0:
        await update.message.reply_text("Invalid transaction amount. Please enter a positive number.")
        return

    # Get recipient from database
    recipient = await user_collection.find_one({"user_id": recipient_id})
    if not recipient:
        await update.message.reply_text("Recipient not found in the database.")
        return

    # Check sender's balance
    sender_balance = sender.get("virex", 0)
    if sender_balance < amount:
        await update.message.reply_text("Insufficient Virex to complete the payment.")
        return

    # Perform transaction
    try:
        # Deduct from sender
        await user_collection.update_one(
            {"user_id": sender_id},
            {"$inc": {"virex": -amount}}
        )
        # Add to recipient
        await user_collection.update_one(
            {"user_id": recipient_id},
            {"$inc": {"virex": amount}}
        )
        
        # Get updated balances
        updated_sender = await user_collection.find_one({"user_id": sender_id})
        updated_recipient = await user_collection.find_one({"user_id": recipient_id})
        
        # Format success message
        success_msg = (
            f"𝗩𝗜𝗥𝗘𝗫 𝗧𝗥𝗔𝗡𝗦𝗔𝗖𝗧𝗜𝗢𝗡\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"𝗦𝗲𝗻𝗱𝗲𝗿: {update.effective_user.first_name}\n"
            f"𝗥𝗲𝗰𝗶𝗽𝗶𝗲𝗻𝘁: {recipient.get('first_name', 'User')}\n"
            f"𝗔𝗺𝗼𝘂𝗻𝘁: VX {amount}\n"
            f"𝗦𝘁𝗮𝘁𝘂𝘀: 𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱\n"
            f"━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(success_msg)
        
        # Log the transaction
        log_msg = (
            "#VX_TRANSFER\n"
            f"Sender: {update.effective_user.full_name} (@{update.effective_user.username or 'N/A'}) [{sender_id}]\n"
            f"Recipient: {recipient.get('first_name', 'Unknown')} (@{recipient.get('username', 'N/A')}) [{recipient_id}]\n"
            f"Amount: VX {amount}\n"
            f"Sender New Balance: VX {updated_sender.get('virex', 0)}\n"
            f"Recipient New Balance: VX {updated_recipient.get('virex', 0)}"
        )
        await context.bot.send_message(chat_id=LOG_CHAT_ID, text=log_msg)
        
    except Exception as e:
        error_msg = "An error occurred during the transaction. Please try again."
        await update.message.reply_text(error_msg)
        
        # Log the error
        error_log = (
            "#VX_TRANSFER_ERROR\n"
            f"Sender: {update.effective_user.full_name} [{sender_id}]\n"
            f"Recipient ID: {recipient_id}\n"
            f"Amount: VX {amount}\n"
            f"Error: {str(e)}"
        )
        await context.bot.send_message(chat_id=LOG_CHAT_ID, text=error_log)
        print(f"Transaction error: {e}")

# Register the new swap command handler
# app.add_handler(CommandHandler("swap", swap_currency))
