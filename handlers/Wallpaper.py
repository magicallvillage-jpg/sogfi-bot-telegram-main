from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler
from db import user_collection
import aiohttp
import datetime

user_states = {}

async def upload_to_catbox(image_data: bytes, filename: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('reqtype', 'fileupload')
            data.add_field('fileToUpload', image_data, filename=filename)
            
            async with session.post('https://catbox.moe/user/api.php', data=data) as response:
                if response.status == 200:
                    url = await response.text()
                    return url.strip()
                else:
                    print(f"Catbox API error: {response.status}")
                    return None
    except Exception as e:
        print(f"Error uploading to Catbox: {e}")
        return None

async def wallpaper_command(update: Update, context: CallbackContext):
    if update.effective_chat.type != 'private':
        return
        
    user_id = update.effective_user.id
    
    user = await user_collection.find_one({"user_id": user_id})
    
    if not user:
        await update.message.reply_text("Use /dart first to create account!")
        return
    
    current_astrites = user.get("astrites", 0)
    
    if current_astrites < 100:
        await update.message.reply_text(f"Need 100 Astrites. You have {current_astrites}")
        return
    
    keyboard = [
        [InlineKeyboardButton("Confirm (100 Astrites)", callback_data=f"confirm_wallpaper_{user_id}")],
        [InlineKeyboardButton("Cancel", callback_data=f"cancel_wallpaper_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Set wallpaper: 100 Astrites\nYour balance: {current_astrites}\nConfirm?",
        reply_markup=reply_markup
    )

async def wallpaper_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = update.effective_user.id
    
    if callback_data.startswith("confirm_wallpaper_"):
        target_user_id = int(callback_data.split("_")[-1])
        
        if user_id != target_user_id:
            await query.answer("Not your request!", show_alert=True)
            return
        
        user = await user_collection.find_one({"user_id": user_id})
        current_astrites = user.get("astrites", 0)
        
        if current_astrites < 100:
            await query.edit_message_text(f"Need 100 Astrites. You have {current_astrites}")
            return
        
        user_states[user_id] = "waiting_for_wallpaper_image"
        
        await query.edit_message_text("Send wallpaper image now")
        
        context.job_queue.run_once(
            clear_user_state, 
            300,
            data=user_id,
            name=f"clear_state_{user_id}"
        )
    
    elif callback_data.startswith("cancel_wallpaper_"):
        target_user_id = int(callback_data.split("_")[-1])
        
        if user_id != target_user_id:
            await query.answer("Not your request!", show_alert=True)
            return
        
        await query.edit_message_text("Cancelled")

async def clear_user_state(context: CallbackContext):
    user_id = context.job.data
    if user_id in user_states:
        del user_states[user_id]

async def handle_wallpaper_image(update: Update, context: CallbackContext):
    if update.effective_chat.type != 'private':
        return
        
    user_id = update.effective_user.id
    
    if user_id not in user_states or user_states[user_id] != "waiting_for_wallpaper_image":
        return
    
    if not update.message.photo:
        await update.message.reply_text("Send image only!")
        return
    
    del user_states[user_id]
    
    for job in context.job_queue.get_jobs_by_name(f"clear_state_{user_id}"):
        job.schedule_removal()
    
    processing_msg = await update.message.reply_text("Processing...")
    
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_data = await file.download_as_bytearray()
        
        filename = f"wallpaper_{user_id}_{datetime.datetime.now().timestamp()}.jpg"
        image_url = await upload_to_catbox(bytes(image_data), filename)
        
        if not image_url:
            await processing_msg.edit_text("Upload failed. Try again")
            return
        
        user = await user_collection.find_one({"user_id": user_id})
        current_astrites = user.get("astrites", 0)
        
        if current_astrites < 100:
            await processing_msg.edit_text("Insufficient Astrites!")
            return
        
        new_balance = current_astrites - 100
        
        await user_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "astrites": new_balance,
                    "wallpaper_url": image_url,
                    "wallpaper_set_date": datetime.datetime.utcnow(),
                    "last_updated": datetime.datetime.utcnow()
                }
            }
        )
        
        keyboard = [
            [InlineKeyboardButton("Visit WebApp", url="https://t.me/Takers_AstriSwap_bot/Market")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.delete()
        
        await update.message.reply_photo(
            photo=image_url,
            caption=f"Wallpaper set! New balance: {new_balance} Astrites",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        print(f"Error processing wallpaper: {e}")
        await processing_msg.edit_text("Error occurred. Try again")

