from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional

def escape_html(text: str) -> str:
    if not text:
        return ""
    escape_chars = {
        '&': '&',
        '<': '<',
        '>': '>',
        '"': '"',
    }
    return ''.join(escape_chars.get(c, c) for c in str(text))

def generate_pagination_keyboard(
    page: int,
    total_pages: int,
    user_id: int,
    message_id: int,
    mode: str,
    rarity: Optional[str] = None
) -> InlineKeyboardMarkup:
    callback_data = f"page_{mode}_{page}_{user_id}_{message_id}" + (f"_{rarity}" if rarity else "")
    buttons_row1 = [
        InlineKeyboardButton("⬅️", callback_data=f"page_{mode}_{page - 1}_{user_id}_{message_id}" + (f"_{rarity}" if rarity else "") if page > 1 else "noop"),
        InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"page_{mode}_{page + 1}_{user_id}_{message_id}" + (f"_{rarity}" if rarity else "") if page < total_pages else "noop")
    ]

    buttons_row2 = [
        InlineKeyboardButton("🌐", switch_inline_query_current_chat=f"user.{user_id}"),
        InlineKeyboardButton("🗑️", callback_data=f"delete_{message_id}_{user_id}")
    ]

    return InlineKeyboardMarkup([buttons_row1, buttons_row2])
