from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Create a single inline button that opens a URL when clicked
    keyboard = [
        [InlineKeyboardButton("Open Marketplace", url="https://t.me/Takers_astriswap_bot/Market")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_photo(
        photo="https://files.catbox.moe/xgq1pa.jpg",
        caption="Click the button below to access the marketplace:",
        reply_markup=reply_markup
    )

