from telegram.ext import *
from telegram import *

async def delete_harem_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    callback_data = query.data.split("_")
    if callback_data[0] != "delete":
        await query.answer(text="Invalid action", show_alert=True)
        return

    try:
        user_id = int(callback_data[2])
        if query.from_user.id != user_id:
            await query.answer(text="You are not authorized to perform this action.", show_alert=True)
            return

        await query.message.delete()
        context.user_data.pop('harem_media', None)
        context.user_data.pop('anime_data', None)
        context.user_data.pop('anime_counts', None)
    except Exception as e:
        logger.error(f"Error deleting harem message: {e}")
        await query.answer(text="Failed to delete message", show_alert=True)
