from db import user_collection, collection as character_collection
import random
import logging
from typing import List, Dict, Any, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_media(characters: List[Dict[str, Any]], user_id: int) -> Optional[Tuple[str, str]]:
    user_data = await user_collection.find_one({"user_id": user_id})
    fav_character_id = user_data.get("fav") if user_data else None

    if fav_character_id:
        favorite_character = await character_collection.find_one({"character_id": fav_character_id})
        if favorite_character:
            image_field = favorite_character.get("image")
            if image_field and isinstance(image_field, str):
                if image_field.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    return image_field, 'photo'
                elif image_field.lower().endswith(('.mp4', '.mov', '.avi')):
                    return image_field, 'video'

    characters_with_image = [char for char in characters if char.get("image") and isinstance(char["image"], str)]
    if not characters_with_image:
        return None
    random_char = random.choice(characters_with_image)
    image_field = random_char["image"]
    if image_field.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
        return image_field, 'photo'
    elif image_field.lower().endswith(('.mp4', '.mov', '.avi')):
        return image_field, 'video'
    logger.warning(f"Unrecognized media type for {image_field}")
    return image_field, 'photo'
