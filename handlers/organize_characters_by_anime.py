from typing import List, Dict, Any, Tuple
from db import user_collection, collection as character_collection
from .calculate import calculate_anime_count
import logging

logger = logging.getLogger(__name__)

async def organize_characters_by_anime(user_id: int, character_ids: List[int]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, int]]]:
    try:
        characters = await character_collection.find(
            {"character_id": {"$in": character_ids}}
        ).to_list(length=None)
    except Exception as e:
        logger.error(f"Error fetching characters from MongoDB: {e}")
        return [], {}

    user_data = await user_collection.find_one({"user_id": user_id})
    match_text = user_data.get("match_text", "").lower()
    user_characters = user_data.get("characters", {}) if user_data else {}

    anime_data = {}
    anime_counts = {}

    for char in characters:
        anime_name = char['anime']
        char_id = str(char['character_id'])
        char_count = user_characters.get(char_id, 0)
        rarity = char.get('rarity', '⚪️ common')
        rarity_parts = rarity.split()
        rarity_emoji = rarity_parts[0] if rarity_parts else '⚪️'
        rarity_name = ' '.join(rarity_parts[1:]) if len(rarity_parts) > 1 else rarity

        # Check if match_text exists in either character name or anime name
        if match_text:
            name_match = match_text in char['name'].lower()
            anime_match = match_text in anime_name.lower()
            if not (name_match or anime_match):
                continue

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
            "rarity": rarity,
            "rarity_emoji": rarity_emoji,
            "name": char['name'],
            "event": char.get('event_emoji'),
            "count": char_count,
            "anime": anime_name
        })

    for anime in anime_data.values():
        anime['characters'].sort(key=lambda x: x['id'])

    sorted_anime_data = sorted(anime_data.values(), key=lambda x: x['name'].lower())
    return sorted_anime_data, anime_counts
