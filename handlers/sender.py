from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from typing import Any, Dict, Optional, Tuple
from .formatters import (
    generate_default_harem_message,
    generate_anime_harem_message,
    generate_rarity_harem_message,
    generate_characters_harem_message
)
from .utils import generate_pagination_keyboard
import logging

logger = logging.getLogger(__name__)

async def send_harem_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    first_name: str,
    page: int,
    mode: str,
    data: Any,
    anime_counts: Dict[str, Dict[str, int]] = None,
    selected_media: Optional[Tuple[str, str]] = None,
    rarity: Optional[str] = None
) -> Optional[Update]:
    paginated_data, total_pages = data
    if not paginated_data:
        await update.effective_message.reply_text("No data to display.")
        return None

    formatted_message = (
        generate_default_harem_message(user_id, first_name, paginated_data, anime_counts, page, total_pages) if mode == 'default' else
        generate_anime_harem_message(user_id, first_name, paginated_data, page, total_pages) if mode == 'anime' else
        generate_rarity_harem_message(user_id, first_name, paginated_data, anime_counts, page, total_pages, rarity) if mode == 'rarity' else
        generate_characters_harem_message(user_id, first_name, paginated_data, page, total_pages)
    )
    message_id = update.effective_message.message_id
    keyboard = generate_pagination_keyboard(page, total_pages, user_id, message_id, mode, rarity)

    if selected_media:
        media_url, media_type = selected_media
        try:
            if media_type == 'photo':
                return await update.effective_message.reply_photo(
                    photo=media_url,
                    caption=formatted_message,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            elif media_type == 'video':
                return await update.effective_message.reply_video(
                    video=media_url,
                    caption=formatted_message,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Error sending media: {e}")

    return await update.effective_message.reply_text(
        formatted_message,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
