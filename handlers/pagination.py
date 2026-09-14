from math import ceil
from typing import *

ITEMS_PER_PAGE = 15

async def paginate_default_characters(
    anime_data: List[Dict[str, Any]],
    page: int,
    items_per_page: int
) -> Tuple[List[Dict[str, Any]], int]:
    all_characters = []
    for anime in anime_data:
        all_characters.extend([(anime['name'], char) for char in anime['characters']])
    
    total_characters = len(all_characters)
    total_pages = ceil(total_characters / items_per_page)
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_chars = all_characters[start_idx:end_idx]
    
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

async def paginate_anime_data(
    anime_data: List[Dict[str, Any]],
    page: int,
    items_per_page: int
) -> Tuple[List[Dict[str, Any]], int]:
    total_items = len(anime_data)
    total_pages = ceil(total_items / items_per_page)
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_animes = anime_data[start_idx:end_idx]
    
    return paginated_animes, total_pages

async def paginate_rarity_characters(
    anime_data: List[Dict[str, Any]], 
    page: int,
    items_per_page: int
) -> Tuple[List[Dict[str, Any]], int]:
    # Flatten characters while maintaining anime structure
    all_chars = []
    for anime in anime_data:
        for char in anime['characters']:
            all_chars.append((anime['name'], char))
    
    total_items = len(all_chars)
    total_pages = ceil(total_items / items_per_page)
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_chars = all_chars[start_idx:end_idx]
    
    # Rebuild anime structure for the current page
    paginated_anime = {}
    for anime_name, char in paginated_chars:
        if anime_name not in paginated_anime:
            original_anime = next(a for a in anime_data if a['name'] == anime_name)
            paginated_anime[anime_name] = {
                'name': anime_name,
                'user_count': original_anime['user_count'],
                'total_count': original_anime['total_count'],
                'characters': []
            }
        paginated_anime[anime_name]['characters'].append(char)
    
    return list(paginated_anime.values()), total_pages

    
async def paginate_characters(
    characters: List[Dict[str, Any]],
    page: int,
    items_per_page: int
) -> Tuple[List[Dict[str, Any]], int]:
    total_items = len(characters)
    total_pages = ceil(total_items / items_per_page)
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_chars = characters[start_idx:end_idx]
    
    return paginated_chars, total_pages
