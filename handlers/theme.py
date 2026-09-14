from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from db import user_collection
from db_sqlite import fetch_characters
from config import RARITY_EMOJIS
from .calculate import calculate_anime_count
import random
import logging
import html
from math import ceil
from typing import List, Dict, Any, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 15

# Define theme constants
THEME_ALL = "all"  # Default theme showing all characters
THEME_RARITY = "rarity"  # Theme to filter by rarity
THEME_ANIME = "anime"  # Theme to filter by specific anime
THEME_FAVORITES = "favorites"  # Theme to show only favorites

def escape_html(text: str) -> str:
    """Escape HTML special characters to prevent injection."""
    if not text:
        return ""
    escape_chars = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&apos;',
    }
    return ''.join(escape_chars.get(c, c) for c in str(text))

def generate_pagination_keyboard(
    page: int, 
    total_pages: int, 
    user_id: int, 
    message_id: int,
    current_theme: str = THEME_ALL,
    theme_value: str = ""
) -> InlineKeyboardMarkup:
    """Generate pagination keyboard with navigation, theme selection, and delete buttons."""
    theme_data = f"_{current_theme}_{theme_value}" if theme_value else f"_{current_theme}"
    
    buttons_row1 = [
        InlineKeyboardButton("⬅️", callback_data=f"page_{page - 1}_{user_id}_{message_id}{theme_data}" if page > 1 else "noop"),
        InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"page_{page + 1}_{user_id}_{message_id}{theme_data}" if page < total_pages else "noop")
    ]

    # Add theme selection row
    theme_buttons = [
        InlineKeyboardButton("🌈 All", callback_data=f"theme_{THEME_ALL}_{user_id}_{message_id}"),
        InlineKeyboardButton("🔮 Rarity", callback_data=f"themelist_rarity_{user_id}_{message_id}"),
        InlineKeyboardButton("📺 Anime", callback_data=f"themelist_anime_{user_id}_{message_id}")
    ]
    
    buttons_row3 = [
        InlineKeyboardButton("🌐", switch_inline_query_current_chat=f"user.{user_id}"),
        InlineKeyboardButton("❤️ Favorites", callback_data=f"theme_{THEME_FAVORITES}_{user_id}_{message_id}"),
        InlineKeyboardButton("🗑️", callback_data=f"delete_{message_id}_{user_id}")
    ]

    return InlineKeyboardMarkup([buttons_row1, theme_buttons, buttons_row3])

def generate_theme_selection_keyboard(
    theme_type: str,
    options: List[str],
    user_id: int,
    message_id: int
) -> InlineKeyboardMarkup:
    """Generate keyboard for selecting specific theme values."""
    buttons = []
    row = []
    
    # Create buttons for each theme option
    for i, option in enumerate(options):
        display_text = option
        if theme_type == "rarity":
            display_text = f"{RARITY_EMOJIS.get(option, '⚪️')} {option}"
        
        callback_data = f"theme_{theme_type}_{user_id}_{message_id}_{option}"
        row.append(InlineKeyboardButton(display_text, callback_data=callback_data))
        
        # Create rows with 2 buttons each
        if len(row) == 2 or i == len(options) - 1:
            buttons.append(row.copy())
            row = []
    
    # Add back button
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"theme_{THEME_ALL}_{user_id}_{message_id}")])
    
    return InlineKeyboardMarkup(buttons)

async def get_media(
    characters: List[Dict[str, Any]],
    user_id: int,
    theme: str = THEME_ALL,
    theme_value: str = ""
) -> Optional[tuple[str, str]]:
    """Select random character media, prioritizing favorite character media if available."""
    if not characters:
        return None
        
    # Fetch the user's favorite character ID
    user_data = await user_collection.find_one({"user_id": user_id})
    fav_character_id = user_data.get("fav") if user_data else None

    # Filter characters by theme if specified
    filtered_chars = characters
    if theme == THEME_RARITY and theme_value:
        filtered_chars = [c for c in characters if c.get('rarity') == theme_value]
    elif theme == THEME_ANIME and theme_value:
        filtered_chars = [c for c in characters if c.get('anime') == theme_value]
    elif theme == THEME_FAVORITES and fav_character_id:
        filtered_chars = [c for c in characters if c.get('character_id') == fav_character_id]
    
    if not filtered_chars:
        filtered_chars = characters  # Fallback to all characters if filter results in empty list

    if fav_character_id and (theme == THEME_ALL or theme == THEME_FAVORITES):
        # Fetch the favorite character details using the ID
        favorite_character = next((c for c in filtered_chars if c.get('character_id') == fav_character_id), None)
        if favorite_character:
            image_field = favorite_character.get("image")
            if image_field and isinstance(image_field, str):
                if image_field.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    return image_field, 'photo'
                elif image_field.endswith(('.mp4', '.mov', '.avi')):
                    return image_field, 'video'

    # Randomly select media from filtered characters
    characters_with_image = [char for char in filtered_chars if char.get("image") and isinstance(char["image"], str)]
    if not characters_with_image:
        return None
        
    random_char = random.choice(characters_with_image)
    image_field = random_char["image"]
    
    if image_field.endswith(('.jpg', '.jpeg', '.png', '.gif')):
        return image_field, 'photo'
    elif image_field.endswith(('.mp4', '.mov', '.avi')):
        return image_field, 'video'
    
    logger.warning(f"Unrecognized media type for {image_field}")
    return image_field, 'photo'

async def organize_characters_by_anime(
    user_id: int, 
    character_ids: List[int],
    theme: str = THEME_ALL,
    theme_value: str = ""
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, int]], List[Dict[str, Any]]]:
    """Organize characters by anime and calculate counts with theme filtering."""
    try:
        characters = await fetch_characters(character_ids)
    except Exception as e:
        logger.error(f"Error fetching characters: {e}")
        return [], {}, []

    user_data = await user_collection.find_one({"user_id": user_id})
    user_characters = user_data.get("characters", {}) if user_data else {}
    fav_character_id = user_data.get("fav") if user_data else None

    # Apply theme filtering to characters
    filtered_characters = characters
    if theme == THEME_RARITY and theme_value:
        filtered_characters = [c for c in characters if c.get('rarity') == theme_value]
    elif theme == THEME_ANIME and theme_value:
        filtered_characters = [c for c in characters if c.get('anime') == theme_value]
    elif theme == THEME_FAVORITES and fav_character_id:
        filtered_characters = [c for c in characters if c.get('character_id') == fav_character_id]

    anime_data = {}
    anime_counts = {}

    for char in filtered_characters:
        anime_name = char['anime']
        char_id = str(char['character_id'])
        char_count = user_characters.get(char_id, 0)

        if anime_name not in anime_data:
            user_anime_count, total_anime_count = await calculate_anime_count(user_id, anime_name)
            anime_data[anime_name] = {
                "name": anime_name,
                "user_count": user_anime_count,
                "total_count": total_anime_count,
                "characters": []
            }
            anime_counts[anime_name] = {
                "user_count": user_anime_count,
                "total_count": total_anime_count
            }

        anime_data[anime_name]['characters'].append({
            "id": char['character_id'],
            "rarity_emoji": RARITY_EMOJIS.get(char.get('rarity', 'Common'), "⚪️"),
            "name": char['name'],
            "event": char.get('event_emoji'),
            "count": char_count,
            "rarity": char.get('rarity', 'Common'),
            "is_favorite": char['character_id'] == fav_character_id
        })

    # Sort characters within each anime by ID
    for anime in anime_data.values():
        anime['characters'].sort(key=lambda x: x['id'])

    return list(anime_data.values()), anime_counts, filtered_characters

def generate_harem_message(
    user_id: int, 
    first_name: str, 
    anime_list: List[Dict[str, Any]],
    anime_counts: Dict[str, Dict[str, int]],
    page: int,
    total_pages: int,
    theme: str = THEME_ALL,
    theme_value: str = ""
) -> str:
    """Generate formatted harem message with pagination and theme information."""
    # Create custom title based on theme
    if theme == THEME_ALL:
        title_line = f"<b><a href=\"tg://user?id={user_id}\">{escape_html(first_name)}</a>'s Character Harem</b>"
    elif theme == THEME_RARITY:
        title_line = f"<b><a href=\"tg://user?id={user_id}\">{escape_html(first_name)}</a>'s {theme_value} Characters</b>"
    elif theme == THEME_ANIME:
        title_line = f"<b><a href=\"tg://user?id={user_id}\">{escape_html(first_name)}</a>'s {theme_value} Collection</b>"
    elif theme == THEME_FAVORITES:
        title_line = f"<b><a href=\"tg://user?id={user_id}\">{escape_html(first_name)}</a>'s Favorite Characters</b>"
    else:
        title_line = f"<b><a href=\"tg://user?id={user_id}\">{escape_html(first_name)}</a>'s Character Harem</b>"
    
    message_lines = [title_line, "⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋"]

    for anime in anime_list:
        anime_name = escape_html(anime['name'])
        counts = anime_counts.get(anime_name, {"user_count": 0, "total_count": 0})
        message_lines.append(f"\n⥱ ✦ {anime_name} ✦ {counts['user_count']}/{counts['total_count']}")
        message_lines.append("⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋")

        for character in anime['characters']:
            event_part = f"[{escape_html(character['event'])}]" if character.get('event') else ""
            char_name = escape_html(character['name'])
            count_part = f" ×{character['count']}" if character['count'] > 1 else ""
            favorite_mark = "❤️ " if character.get('is_favorite') else ""
            
            line = f"➥ {favorite_mark}✧{character['id']}✧ | {character['rarity_emoji']} | {char_name}{count_part} {event_part}"
            message_lines.append(line)

        message_lines.append("⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋")

    # Add theme and page info at the bottom
    theme_info = ""
    if theme == THEME_RARITY:
        theme_info = f" • {RARITY_EMOJIS.get(theme_value, '⚪️')} {theme_value} Filter"
    elif theme == THEME_ANIME:
        theme_info = f" • 📺 {theme_value} Filter"
    elif theme == THEME_FAVORITES:
        theme_info = f" • ❤️ Favorites"
        
    message_lines.append(f"\n📖 Page {page}/{total_pages}{theme_info}")
    
    caption = "\n".join(message_lines)
    return caption[:1020] + "..." if len(caption) > 1024 else caption

async def paginate_characters(
    anime_data: List[Dict[str, Any]],
    page: int,
    items_per_page: int
) -> Tuple[List[Dict[str, Any]], int]:
    """Paginate characters across all animes."""
    all_characters = []
    for anime in anime_data:
        all_characters.extend([(anime['name'], char) for char in anime['characters']])
    
    total_characters = len(all_characters)
    total_pages = max(1, ceil(total_characters / items_per_page))
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_chars = all_characters[start_idx:end_idx]
    
    # Reorganize paginated characters back into anime structure
    result_animes = {}
    for anime_name, char in paginated_chars:
        if anime_name not in result_animes:
            original_anime = next(a for a in anime_data if a['name'] == anime_name)
            result_animes[anime_name] = {
                "name": anime_name,
                "user_count": original_anime['user_count'],
                "total_count": original_anime['total_count'],
                "characters": []
            }
        result_animes[anime_name]['characters'].append(char)
    
    return list(result_animes.values()), total_pages

async def send_harem_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    first_name: str,
    page: int,
    anime_data: List[Dict[str, Any]],
    anime_counts: Dict[str, Dict[str, int]],
    selected_media: Optional[tuple[str, str]] = None,
    theme: str = THEME_ALL,
    theme_value: str = ""
) -> Optional[Update]:
    """Send paginated harem message with optional media."""
    paginated_animes, total_pages = await paginate_characters(anime_data, page, ITEMS_PER_PAGE)
    
    if not paginated_animes:
        await update.effective_message.reply_text("No characters to display.")
        return None

    formatted_message = generate_harem_message(
        user_id, 
        first_name, 
        paginated_animes, 
        anime_counts, 
        page, 
        total_pages,
        theme,
        theme_value
    )
    message_id = update.effective_message.message_id
    keyboard = generate_pagination_keyboard(page, total_pages, user_id, message_id, theme, theme_value)

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

async def show_harem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[Update]:
    """Display user's harem with pagination and media."""
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name or "User"

    user_data = await user_collection.find_one({"user_id": user_id})
    if not user_data or not user_data.get("characters"):
        await update.effective_message.reply_text("You have no characters yet.")
        return None

    # Get character IDs in reverse order (recently added first)
    user_character_ids = [int(cid) for cid in user_data.get("characters", {}).keys()][::-1]
    
    # Get the current theme from args or default to ALL
    theme = THEME_ALL
    theme_value = ""
    if context.args:
        if len(context.args) >= 2:
            theme = context.args[0].lower()
            theme_value = context.args[1]
        elif len(context.args) == 1:
            if context.args[0].lower() == "favorites":
                theme = THEME_FAVORITES
            else:
                theme = THEME_ALL
    
    # Organize characters by anime and get counts with theme filtering
    anime_data, anime_counts, filtered_characters = await organize_characters_by_anime(
        user_id, 
        user_character_ids,
        theme,
        theme_value
    )
    
    if not anime_data:
        await update.effective_message.reply_text(f"No characters found in this theme.")
        return None
    
    # Get media for the user's harem, prioritizing favorite character
    selected_media = await get_media(filtered_characters, user_id, theme, theme_value)
    
    # Store data in context
    context.user_data['harem_media'] = selected_media
    context.user_data['anime_data'] = anime_data
    context.user_data['anime_counts'] = anime_counts
    context.user_data['all_characters'] = filtered_characters
    context.user_data['harem_theme'] = theme
    context.user_data['theme_value'] = theme_value

    # Send first page
    return await send_harem_message(
        update, 
        context, 
        user_id, 
        first_name, 
        1,  # Start at page 1
        anime_data,
        anime_counts,
        selected_media,
        theme,
        theme_value
    )

async def paginate_harem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination for harem display."""
    query = update.callback_query
    callback_data = query.data.split("_")
    
    if query.data == "noop":
        await query.answer(text="This button does nothing.", show_alert=True)
        return

    try:
        requested_page = int(callback_data[1])
        owner_user_id = int(callback_data[2])
        message_id = int(callback_data[3])
        
        # Extract theme info if available
        theme = THEME_ALL
        theme_value = ""
        if len(callback_data) > 4:
            theme = callback_data[4]
            if len(callback_data) > 5:
                theme_value = callback_data[5]
    except (IndexError, ValueError):
        await query.answer(text="Invalid pagination request", show_alert=True)
        return

    if query.from_user.id != owner_user_id:
        await query.answer(text="You are not authorized to perform this action.", show_alert=True)
        return

    anime_data = context.user_data.get('anime_data', [])
    anime_counts = context.user_data.get('anime_counts', {})
    selected_media = context.user_data.get('harem_media')

    if not anime_data:
        await query.edit_message_caption(caption="You have no characters yet.", parse_mode='HTML')
        return

    paginated_animes, total_pages = await paginate_characters(anime_data, requested_page, ITEMS_PER_PAGE)
    
    if requested_page < 1 or requested_page > total_pages:
        await query.answer(text="Invalid page selection.", show_alert=True)
        return

    if not paginated_animes:
        await query.edit_message_caption(caption="No characters to display.", parse_mode='HTML')
        return

    formatted_message = generate_harem_message(
        owner_user_id, 
        query.from_user.first_name or "User", 
        paginated_animes,
        anime_counts,
        requested_page,
        total_pages,
        theme,
        theme_value
    )
    
    keyboard = generate_pagination_keyboard(requested_page, total_pages, owner_user_id, message_id, theme, theme_value)

    if selected_media:
        media_url, media_type = selected_media
        try:
            media = InputMediaPhoto(media=media_url, caption=formatted_message, parse_mode='HTML') if media_type == 'photo' else InputMediaVideo(media=media_url, caption=formatted_message, parse_mode='HTML')
            await query.edit_message_media(media=media, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error editing media: {e}")
            await query.edit_message_text(formatted_message, reply_markup=keyboard, parse_mode='HTML')
    else:
        await query.edit_message_text(formatted_message, reply_markup=keyboard, parse_mode='HTML')

async def handle_theme_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle theme selection callbacks."""
    query = update.callback_query
    callback_data = query.data.split("_")
    
    if callback_data[0] != "theme" and callback_data[0] != "themelist":
        return
    
    try:
        action = callback_data[0]
        theme_type = callback_data[1]
        owner_user_id = int(callback_data[2])
        message_id = int(callback_data[3])
        theme_value = callback_data[4] if len(callback_data) > 4 else ""
    except (IndexError, ValueError):
        await query.answer(text="Invalid theme request", show_alert=True)
        return

    if query.from_user.id != owner_user_id:
        await query.answer(text="You are not authorized to perform this action.", show_alert=True)
        return
    
    # If this is a request to show the theme selection list
    if action == "themelist":
        user_data = await user_collection.find_one({"user_id": owner_user_id})
        if not user_data or not user_data.get("characters"):
            await query.answer(text="You have no characters.", show_alert=True)
            return
            
        user_character_ids = [int(cid) for cid in user_data.get("characters", {}).keys()]
        characters = await fetch_characters(user_character_ids)
        
        if theme_type == "rarity":
            # Get all unique rarities from user's characters
            rarities = sorted(set(char.get('rarity', 'Common') for char in characters if char.get('rarity')))
            keyboard = generate_theme_selection_keyboard(theme_type, rarities, owner_user_id, message_id)
            await query.edit_message_reply_markup(reply_markup=keyboard)
            
        elif theme_type == "anime":
            # Get all unique animes from user's characters
            animes = sorted(set(char.get('anime') for char in characters if char.get('anime')))
            keyboard = generate_theme_selection_keyboard(theme_type, animes, owner_user_id, message_id)
            await query.edit_message_reply_markup(reply_markup=keyboard)
            
        return
    
    # If this is a request to apply a theme
    user_data = await user_collection.find_one({"user_id": owner_user_id})
    if not user_data or not user_data.get("characters"):
        await query.answer(text="You have no characters.", show_alert=True)
        return
        
    user_character_ids = [int(cid) for cid in user_data.get("characters", {}).keys()][::-1]
    
    # Organize characters by anime and get counts with theme filtering
    anime_data, anime_counts, filtered_characters = await organize_characters_by_anime(
        owner_user_id, 
        user_character_ids,
        theme_type,
        theme_value
    )
    
    if not anime_data:
        await query.answer(text=f"No characters found with this theme.", show_alert=True)
        return
    
    # Get media for the filtered harem
    selected_media = await get_media(filtered_characters, owner_user_id, theme_type, theme_value)
    
    # Update context data
    context.user_data['harem_media'] = selected_media
    context.user_data['anime_data'] = anime_data
    context.user_data['anime_counts'] = anime_counts
    context.user_data['all_characters'] = filtered_characters
    context.user_data['harem_theme'] = theme_type
    context.user_data['theme_value'] = theme_value
    
    # Generate the first page
    paginated_animes, total_pages = await paginate_characters(anime_data, 1, ITEMS_PER_PAGE)
    
    formatted_message = generate_harem_message(
        owner_user_id, 
        query.from_user.first_name or "User", 
        paginated_animes,
        anime_counts,
        1,  # Start at page 1
        total_pages,
        theme_type,
        theme_value
    )
    
    keyboard = generate_pagination_keyboard(1, total_pages, owner_user_id, message_id, theme_type, theme_value)
    
    if selected_media:
        media_url, media_type = selected_media
        try:
            media = InputMediaPhoto(media=media_url, caption=formatted_message, parse_mode='HTML') if media_type == 'photo' else InputMediaVideo(media=media_url, caption=formatted_message, parse_mode='HTML')
            await query.edit_message_media(media=media, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error editing media with theme: {e}")
            await query.edit_message_text(formatted_message, reply_markup=keyboard, parse_mode='HTML')
    else:
        await query.edit_message_text(formatted_message, reply_markup=keyboard, parse_mode='HTML')

async def delete_harem_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete harem message and clean up user data."""
    query = update.callback_query
    callback_data = query.data.split("_")
    if callback_data[0] != "delete":
        await query.answer(text="Invalid action", show_alert=True)
        return

    try:
        owner_user_id = int(callback_data[2])
        if query.from_user.id != owner_user_id:
            await query.answer(text="You are not authorized to perform this action.", show_alert=True)
            return

        await query.message.delete()
        # Clear all harem-related data from context
        context.user_data.pop('harem_media', None)
        context.user_data.pop('anime_data', None)
        context.user_data.pop('anime_counts', None)
        context.user_data.pop('all_characters', None)
        context.user_data.pop('harem_theme', None)
        context.user_data.pop('theme_value', None)
    except Exception as e:
        logger.error(f"Error deleting harem message: {e}")
        await query.answer(text="Failed to delete message", show_alert=True)
