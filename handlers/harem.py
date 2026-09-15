from typing import List, Dict, Any, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto, InputMediaVideo, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from db import user_collection, collection as character_collection, banned_users_collection
from config import RARITY_EMOJIS, BOT_TOKEN  # Assume BOT_TOKEN is in config
from .calculate import calculate_anime_count
from .utils import escape_html, generate_pagination_keyboard
from .deleteh import delete_harem_message
from .formatters import (
    generate_default_harem_message,
    generate_anime_harem_message,
    generate_rarity_harem_message,
    generate_characters_harem_message
)
from .pagination import (
    paginate_default_characters,
    paginate_anime_data,
    paginate_rarity_characters,
    paginate_characters
)
from .media import get_media
from .organize_characters_by_anime import organize_characters_by_anime
from .sender import send_harem_message
import logging
import traceback
import asyncio
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 10
ANIME_PER_PAGE = 6

# Error logging channel configuration
ERROR_LOG_CHANNEL_ID = -1004341552881  # Replace with your actual error log channel ID

async def send_error_to_channel(bot: Bot, error: Exception, context: str, user_id: int = None, additional_info: Dict = None):
    """
    Send error details to the designated error logging channel.
    
    Args:
        bot (Bot): The Telegram Bot instance
        error (Exception): The exception that occurred
        context (str): Context where the error occurred
        user_id (int, optional): User ID if relevant
        additional_info (Dict, optional): Additional information about the error
    """
    try:
        error_message = f"🚨 **ERROR REPORT** 🚨\n\n"
        error_message += f"**Context:** {escape_html(context)}\n"  # Added escape here for safety
        error_message += f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        
        if user_id:
            error_message += f"**User ID:** {user_id}\n"
        
        error_message += f"**Error Type:** {type(error).__name__}\n"
        error_message += f"**Error Message:** {escape_html(str(error))}\n\n"  # Escape error message
        
        if additional_info:
            error_message += "**Additional Info:**\n"
            for key, value in additional_info.items():
                error_message += f"- {escape_html(key)}: {escape_html(str(value))}\n"  # Escape keys and values
            error_message += "\n"
        
        # Get traceback
        tb_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        error_message += f"**Traceback:**\n``````"  # Escape and limit traceback
        
        # Split message if it's too long (Telegram limit is 4096 characters)
        if len(error_message) > 4090:
            parts = [error_message[i:i+4090] for i in range(0, len(error_message), 4090)]
            for i, part in enumerate(parts):
                if i == 0:
                    await bot.send_message(chat_id=ERROR_LOG_CHANNEL_ID, text=part, parse_mode='Markdown')
                else:
                    await bot.send_message(chat_id=ERROR_LOG_CHANNEL_ID, text=f"**Continued ({i+1}/{len(parts)}):**\n{part}", parse_mode='Markdown')
        else:
            await bot.send_message(chat_id=ERROR_LOG_CHANNEL_ID, text=error_message, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Failed to send error to channel: {e}")
        # Fallback to regular logging
        logger.error(f"Original error in {context}: {error}")
        if user_id:
            logger.error(f"User ID: {user_id}")
        if additional_info:
            logger.error(f"Additional info: {additional_info}")

async def check_user_telegram_membership(user_id: int, bot: Bot) -> Tuple[bool, str, Optional[InlineKeyboardMarkup]]:
    """
    Check if a user is a member of both the Taker update channel and group.
    
    Args:
        user_id (int): The Telegram user ID to check.
        bot (Bot): The Telegram Bot instance for API access.
        
    Returns:
        Tuple[bool, str, Optional[InlineKeyboardMarkup]]: 
            - bool: True if the user is a member of both, False otherwise.
            - str: A warning message indicating membership status and instructions.
            - Optional[InlineKeyboardMarkup]: Inline keyboard with join buttons, or None if not needed.
    """
    UPDATE_CHANNEL_ID = -1004341552881  # @sogficannel
    GROUP_ID = -1003987395271           # @sogfigap
    CHANNEL_LINK = "https://t.me/sogficannel"
    GROUP_LINK = "https://t.me/sogfigap"

    is_in_channel = False
    is_in_group = False
    channel_button = InlineKeyboardButton("Join Update Channel", url=CHANNEL_LINK)
    group_button = InlineKeyboardButton("Join Group", url=GROUP_LINK)

    try:
        channel_status = await bot.get_chat_member(chat_id=UPDATE_CHANNEL_ID, user_id=user_id)
        if channel_status.status in ['member', 'administrator', 'creator']:
            is_in_channel = True
    except TelegramError as e:
        logger.error(f"Error checking channel membership for user {user_id}: {e}")
        await send_error_to_channel(
            bot, e, "check_user_telegram_membership - channel check",
            user_id, {"channel_id": UPDATE_CHANNEL_ID}
        )

    try:
        group_status = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        if group_status.status in ['member', 'administrator', 'creator']:
            is_in_group = True
    except TelegramError as e:
        logger.error(f"Error checking group membership for user {user_id}: {e}")
        await send_error_to_channel(
            bot, e, "check_user_telegram_membership - group check",
            user_id, {"group_id": GROUP_ID}
        )

    if is_in_channel and is_in_group:
        message = "You are already a member of both the Taker update channel and group! 🎉"
        return True, message, None
    elif is_in_channel:
        message = "⚠️ You cannot use the harem until you join our group! Join and retry /harem."
        keyboard = InlineKeyboardMarkup([[group_button]])  # Single row for one button
        return False, message, keyboard
    elif is_in_group:
        message = "⚠️ You cannot use the harem until you join our update channel! Join and retry /harem."
        keyboard = InlineKeyboardMarkup([[channel_button]])  # Single row for one button
        return False, message, keyboard
    else:
        message = "⚠️ You cannot use the harem until you join our update channel and group! Join and retry /harem."
        keyboard = InlineKeyboardMarkup([[channel_button], [group_button]])  # Vertical: two rows
        return False, message, keyboard

async def is_user_banned(user_id: int) -> bool:
    try:
        banned_user = await banned_users_collection.find_one({"user_id": user_id})
        return bool(banned_user)
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is banned: {e}")
        # Don't send to error channel for this as it might be called frequently
        return False  # Default to not banned if there's an error

async def show_harem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[Update]:
    user = update.effective_user
    user_id = user.id
    first_name = escape_html(user.first_name or "User")  # Added escape here for first_name
    
    try:
        # Check if user is banned
        if await is_user_banned(user_id):
            await update.message.reply_text("🚫 You are banned from using this bot.")
            return None

        # Check Telegram membership
        is_member, membership_message, membership_keyboard = await check_user_telegram_membership(user_id, context.bot)
        if not is_member:
            await update.message.reply_text(escape_html(membership_message), reply_markup=membership_keyboard, parse_mode='HTML')  # Escape message
            return None

        # Proceed with harem display
        user_data = await user_collection.find_one({"user_id": user_id})
        if not user_data or not user_data.get("characters"):
            await update.effective_message.reply_text("You have no characters yet.")
            return None

        sort_mode = user_data.get("sort_mode", "default")
        rarity_filter = user_data.get("rarity_filter")

        user_character_ids = [int(cid) for cid in user_data.get("characters", {}).keys()][::-1]
        anime_data, anime_counts = await organize_characters_by_anime(user_id, user_character_ids)

        # Escape anime_data contents (assuming organize_characters_by_anime returns dicts with strings)
        for anime in anime_data:
            anime['name'] = escape_html(anime['name'])
            for char in anime['characters']:
                char['name'] = escape_html(char['name'])
                char['rarity'] = escape_html(char['rarity'])  # Escape rarity if it's a string

        # Check if anime_data is empty due to match_text filter
        match_text = user_data.get("match_text", "")
        if not anime_data and user_data.get("characters") and match_text:
            await update.effective_message.reply_text(escape_html("Your /match text doesn't have any matching characters, so clear it and try /harem again."))
            return None

        characters = await character_collection.find(
            {"character_id": {"$in": user_character_ids}}
        ).to_list(length=None)
        
        # Escape character data
        for char in characters:
            if 'name' in char:
                char['name'] = escape_html(char['name'])
            if 'rarity' in char:
                char['rarity'] = escape_html(char['rarity'])

        selected_media = await get_media(characters, user_id)
        context.user_data['harem_media'] = selected_media
        context.user_data['anime_data'] = anime_data
        context.user_data['anime_counts'] = anime_counts  # Assuming anime_counts are numbers, no escape needed

        if sort_mode == 'default':
            paginated_data = await paginate_default_characters(anime_data, 1, ITEMS_PER_PAGE)
            return await send_harem_message(
                update, context, user_id, first_name, 1, 'default', paginated_data, anime_counts, selected_media
            )
        elif sort_mode == 'anime':
            paginated_data = await paginate_anime_data(anime_data, 1, ANIME_PER_PAGE)
            return await send_harem_message(
                update, context, user_id, first_name, 1, 'anime', paginated_data, anime_counts, selected_media
            )
        elif sort_mode == 'rarity':
            if not rarity_filter:
                await update.effective_message.reply_text("Please select a rarity filter first.")
                return None
                
            rarity_filter = escape_html(rarity_filter)  # Escape rarity_filter
            filtered_anime = []
            for anime in anime_data:
                filtered_chars = [char for char in anime['characters'] if char['rarity'] == rarity_filter]
                if filtered_chars:
                    filtered_anime.append({
                        'name': escape_html(anime['name']),  # Re-escape if needed
                        'user_count': len(filtered_chars),
                        'total_count': sum(1 for char in anime['characters'] if char['rarity'] == rarity_filter),
                        'characters': filtered_chars
                    })
            
            if not filtered_anime:
                rarity_display = escape_html(rarity_filter)
                await update.effective_message.reply_text(escape_html(f"No {rarity_display} characters found."))
                return None
            
            paginated_data = await paginate_rarity_characters(filtered_anime, 1, ITEMS_PER_PAGE)
            return await send_harem_message(
                update, context, user_id, first_name, 1, 'rarity', paginated_data, anime_counts, selected_media, rarity_filter
            )
        elif sort_mode == 'character':
            all_characters = []
            for anime in anime_data:
                all_characters.extend(anime['characters'])
            paginated_data = await paginate_characters(all_characters, 1, ITEMS_PER_PAGE)
            return await send_harem_message(
                update, context, user_id, first_name, 1, 'character', paginated_data, anime_counts, selected_media
            )
    
    except Exception as e:
        logger.error(f"Error in show_harem for user {user_id}: {e}")
        await send_error_to_channel(
            context.bot, e, "show_harem",
            user_id, {
                "first_name": first_name,
                "sort_mode": user_data.get("sort_mode", "unknown") if 'user_data' in locals() else "unknown",
                "has_characters": bool(user_data.get("characters")) if 'user_data' in locals() else "unknown"
            }
        )
        try:
            await update.effective_message.reply_text(escape_html("❌ An error occurred while displaying your harem. The issue has been reported."))
        except:
            pass  # If we can't even send an error message, just log it
        return None

async def paginate_harem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    callback_data = query.data.split("_")
    
    if query.data == "noop":
        await query.answer(text="This button does nothing.", show_alert=True)
        return

    try:
        mode = callback_data[1]
        page = int(callback_data[2])
        user_id = int(callback_data[3])
        message_id = int(callback_data[4])
        rarity = "_".join(callback_data[5:]) if mode == 'rarity' and len(callback_data) > 5 else None
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing callback data: {query.data}")
        await send_error_to_channel(
            context.bot, e, "paginate_harem - callback data parsing",
            query.from_user.id, {"callback_data": query.data}
        )
        await query.answer(text="Invalid pagination request", show_alert=True)
        return

    if query.from_user.id != user_id:
        await query.answer(text="You are not authorized to perform this action.", show_alert=True)
        return

    try:
        # Check Telegram membership
        is_member, membership_message, membership_keyboard = await check_user_telegram_membership(user_id, context.bot)
        if not is_member:
            await query.edit_message_caption(caption=escape_html(membership_message), reply_markup=membership_keyboard, parse_mode='HTML')  # Escape message
            return

        anime_data = context.user_data.get('anime_data', [])
        anime_counts = context.user_data.get('anime_counts', {})
        selected_media = context.user_data.get('harem_media')

        # Fetch user_data to check for match_text (for empty data handling)
        user_data = await user_collection.find_one({"user_id": user_id})
        match_text = user_data.get("match_text", "") if user_data else ""

        if not anime_data:
            if user_data and user_data.get("characters") and match_text:
                await query.edit_message_caption(caption=escape_html("Your /match text doesn't have any matching characters, so clear it and try /harem again."), parse_mode='HTML')
            else:
                await query.edit_message_caption(caption="You have no characters yet.", parse_mode='HTML')
            return

        # Escape anime_data again if needed (for pagination)
        for anime in anime_data:
            anime['name'] = escape_html(anime['name'])
            for char in anime['characters']:
                char['name'] = escape_html(char['name'])
                char['rarity'] = escape_html(char['rarity'])

        if mode == 'default':
            paginated_data = await paginate_default_characters(anime_data, page, ITEMS_PER_PAGE)
        elif mode == 'anime':
            paginated_data = await paginate_anime_data(anime_data, page, ANIME_PER_PAGE)
        elif mode == 'rarity':
            filtered_anime = []
            rarity_filter = escape_html(rarity.replace("_", " ") if rarity else None)  # Escape rarity_filter
            for anime in anime_data:
                filtered_chars = [char for char in anime['characters'] if char['rarity'] == rarity_filter]
                if filtered_chars:
                    filtered_anime.append({
                        'name': escape_html(anime['name']),
                        'user_count': len(filtered_chars),
                        'total_count': sum(1 for char in anime['characters'] if char['rarity'] == rarity_filter),
                        'characters': filtered_chars
                    })
            
            if not filtered_anime:
                await query.edit_message_caption(caption=escape_html(f"No {rarity_filter} characters found."), parse_mode='HTML')
                return
            
            paginated_data = await paginate_rarity_characters(filtered_anime, page, ITEMS_PER_PAGE)
        elif mode == 'character':
            characters = []
            for anime in anime_data:
                characters.extend(anime['characters'])
            paginated_data = await paginate_characters(characters, page, ITEMS_PER_PAGE)
        else:
            await query.answer(text="Invalid mode.", show_alert=True)
            return

        if page < 1 or page > paginated_data[1]:
            await query.answer(text="Invalid page selection.", show_alert=True)
            return

        first_name = escape_html(query.from_user.first_name or "User")  # Escape first_name here too
        formatted_message = (
            generate_default_harem_message(user_id, first_name, paginated_data[0], anime_counts, page, paginated_data[1]) if mode == 'default' else
            generate_anime_harem_message(user_id, first_name, paginated_data[0], page, paginated_data[1]) if mode == 'anime' else
            generate_rarity_harem_message(user_id, first_name, paginated_data[0], anime_counts, page, paginated_data[1], escape_html(rarity.replace("_", " ") if rarity else "All Rarities")) if mode == 'rarity' else
            generate_characters_harem_message(user_id, first_name, paginated_data[0], page, paginated_data[1])
        )
        formatted_message = escape_html(formatted_message)  # Final escape on the entire message for safety (though formatters should handle it)
        keyboard = generate_pagination_keyboard(page, paginated_data[1], user_id, message_id, mode, rarity)

        if selected_media:
            media_url, media_type = selected_media
            try:
                media = InputMediaPhoto(media=media_url, caption=formatted_message, parse_mode='HTML') if media_type == 'photo' else InputMediaVideo(media=media_url, caption=formatted_message, parse_mode='HTML')
                await query.edit_message_media(media=media, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Error editing media: {e}")
                await send_error_to_channel(
                    context.bot, e, "paginate_harem - edit media",
                    user_id, {
                        "media_url": media_url,
                        "media_type": media_type,
                        "mode": mode,
                        "page": page
                    }
                )
                await query.edit_message_text(formatted_message, reply_markup=keyboard, parse_mode='HTML')
        else:
            await query.edit_message_text(formatted_message, reply_markup=keyboard, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in paginate_harem for user {user_id}: {e}")
        await send_error_to_channel(
            context.bot, e, "paginate_harem",
            user_id, {
                "mode": mode,
                "page": page,
                "message_id": message_id,
                "rarity": rarity,
                "callback_data": query.data
            }
        )
        try:
            await query.answer(text=escape_html("❌ An error occurred while paginating. The issue has been reported."), show_alert=True)
        except:
            pass  # If we can't even send an error message, just log it
