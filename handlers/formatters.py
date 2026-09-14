
from .utils import escape_html
from typing import List, Dict, Any
import html

def safe_escape_html(text: str) -> str:
    """Enhanced HTML escaping for special Unicode characters"""
    if not text:
        return ""
    
    # First apply standard HTML escaping
    escaped = html.escape(text, quote=True)
    
    # Additional escaping for problematic characters
    escaped = escaped.replace('>', '&gt;').replace('<', '&lt;')
    escaped = escaped.replace('"', '&quot;').replace("'", '&#x27;')
    
    return escaped

def generate_default_harem_message(
    user_id: int, 
    first_name: str, 
    anime_list: List[Dict[str, Any]],
    anime_counts: Dict[str, Dict[str, int]],
    page: int,
    total_pages: int
) -> str:
    safe_name = safe_escape_html(first_name)
    title_line = f"<b><a href=\"tg://user?id={user_id}\">{safe_name}</a>'s Character Harem</b>"
    message_lines = [title_line]

    for anime in anime_list:
        anime_name = safe_escape_html(anime['name'])
        counts = anime_counts.get(anime_name, {"user_count": 0, "total_count": 0})
        message_lines.append(f"\n⤿ <b>{anime_name}</b> {counts['user_count']}/{counts['total_count']}")

        for character in anime['characters']:
            event_part = f"[{safe_escape_html(character['event'])}]" if character.get('event') else ""
            char_name = safe_escape_html(character['name'])
            count_part = f" ×{character['count']}" if character['count'] > 1 else ""
            line = f"↳ {character['rarity_emoji']} [{character['id']}] | {char_name}{count_part} {event_part}"
            message_lines.append(line)
    
    caption = "\n".join(message_lines)
    return caption[:4000] + "..." if len(caption) > 4000 else caption

def generate_anime_harem_message(
    user_id: int,
    first_name: str,
    anime_list: List[Dict[str, Any]],
    page: int,
    total_pages: int
) -> str:
    safe_name = safe_escape_html(first_name)
    title_line = f"● <b><a href=\"tg://user?id={user_id}\">{safe_name}</a>'s Anime Harem - Sorted by Collection</b>"
    message_lines = [title_line]

    for anime in anime_list:
        anime_name = safe_escape_html(anime['name'])
        total = anime['total_count']
        took = anime['user_count']
        left = total - took

        message_lines.append(f"\n⤿ <b>{anime_name}</b>")
        message_lines.append(f"↳ Total Characters: {total}")
        message_lines.append(f"↳ Took: {took}")
        message_lines.append(f"↳ Left: {left}")

    caption = "\n".join(message_lines)
    return caption[:4000] + "..." if len(caption) > 4000 else caption

def generate_rarity_harem_message(
    user_id: int,
    first_name: str,
    anime_list: List[Dict[str, Any]],
    anime_counts: Dict[str, Dict[str, int]],
    page: int,
    total_pages: int,
    rarity: str
) -> str:
    safe_name = safe_escape_html(first_name)
    title_line = f"<b><a href=\"tg://user?id={user_id}\">{safe_name}</a>'s {rarity} Characters</b>"
    message_lines = [title_line]

    for anime in anime_list:
        anime_name = safe_escape_html(anime['name'])
        counts = anime_counts.get(anime_name, {"user_count": 0, "total_count": 0})
        message_lines.append(f"\n▪ <b>{anime_name}</b> {counts['user_count']}/{counts['total_count']}")
        
        for character in anime['characters']:
            event_part = f"[{safe_escape_html(character['event'])}]" if character.get('event') else ""
            char_name = safe_escape_html(character['name'])
            count_part = f" ×{character['count']}" if character['count'] > 1 else ""
            line = f"→ ✧{character['id']}✧ | {character['rarity_emoji']} | {char_name}{count_part} {event_part}"
            message_lines.append(line)

    caption = "\n".join(message_lines)
    return caption[:4000] + "..." if len(caption) > 4000 else caption

def generate_characters_harem_message(
    user_id: int,
    first_name: str,
    characters: List[Dict[str, Any]],
    page: int,
    total_pages: int
) -> str:
    safe_name = safe_escape_html(first_name)
    title_line = f"<b><a href=\"tg://user?id={user_id}\">{safe_name}</a>'s Character Harem</b>"
    message_lines = [title_line]

    for char in characters:
        event_part = f"[{safe_escape_html(char['event'])}]" if char.get('event') else ""
        char_name = safe_escape_html(char['name'])
        count_part = f" ×{char['count']}" if char['count'] > 1 else ""
        line = f"↳ {char['rarity_emoji']} [{char['id']}] | {char_name}{count_part} {event_part}"
        message_lines.append(line)

    caption = "\n".join(message_lines)
    return caption[:4000] + "..." if len(caption) > 4000 else caption
