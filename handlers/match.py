from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from db import user_collection 


async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    match_text = ' '.join(context.args).strip()

    user_data = await user_collection.find_one({"user_id": user_id})
    saved_match_text = user_data.get("match_text", "")

    if not match_text:
        if saved_match_text:
            keyboard = [[InlineKeyboardButton("❌ Clear Match Text", callback_data=f"match_clear_{user_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Your current match text: <b>{saved_match_text}</b>", reply_markup=reply_markup, parse_mode="HTML")
        else:
            await update.message.reply_text("You have no match text saved. Use <b>/match &lt;text&gt;</b> to set one.", parse_mode="HTML")
        return

    await user_collection.update_one(
        {"user_id": user_id},
        {"$set": {"match_text": match_text}},
        upsert=True
    )

    await update.message.reply_text(f"Match text saved: <b>{match_text}</b>", parse_mode="HTML")

    keyboard = [[InlineKeyboardButton("❌ Clear Match Text", callback_data=f"match_clear_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(f"Your current match text: <b>{match_text}</b>", reply_markup=reply_markup, parse_mode="HTML")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pattern = query.data.split("_")
    action, user_id = pattern[1], int(pattern[2])
    from_user_id = query.from_user.id

    if from_user_id != user_id:
        await query.answer("🚫 You cannot modify another user's match text!", show_alert=True)
        return

    if action == "clear":
        await user_collection.update_one(
            {"user_id": user_id},
            {"$unset": {"match_text": ""}}
        )
        await query.edit_message_text("✅ Match text has been <b>cleared</b>", parse_mode="HTML")

