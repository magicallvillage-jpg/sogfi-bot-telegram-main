import sqlite3
import re
import random
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "characters.db")

_conn = None

def connect():
    """Establish a single SQLite connection for the bot's lifetime."""
    global _conn
    if _conn is None:
        try:
            _conn = sqlite3.connect(SQLITE_DB_PATH)
            _conn.execute("PRAGMA journal_mode=WAL")  # Enable Write-Ahead Logging
            logger.info("SQLite connection established with WAL mode.")
        except sqlite3.Error as e:
            logger.error(f"SQLite connection error: {e}")
            raise
    return _conn

def close_connection():
    """Close the SQLite connection."""
    global _conn
    if _conn:
        _conn.close()
        logger.info("SQLite connection closed.")
        _conn = None

async def ensure_characters_table():
    """Ensure the characters table exists with the correct schema."""
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS characters (
                anime TEXT,
                channel_message_id INTEGER,
                character_id INTEGER PRIMARY KEY,
                event TEXT,
                event_emoji TEXT,
                image TEXT,
                name TEXT,
                rarity TEXT,
                uploader_id INTEGER,
                uploader_name TEXT
            )
        ''')
        conn.commit()
        logger.info("Characters table ensured.")
    except sqlite3.Error as e:
        logger.error(f"SQLite ensure_characters_table error: {e}")

async def create_indexes():
    """
    Create indexes on all columns of the characters table to optimize query performance.
    """
    try:
        conn = connect()
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='characters'")
        if not cursor.fetchone():
            logger.error("Characters table does not exist. Creating it.")
            await ensure_characters_table()

        # Create indexes for all columns
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_anime ON characters (anime)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel_message_id ON characters (channel_message_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_character_id ON characters (character_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_event ON characters (event)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_emoji ON characters (event_emoji)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_image ON characters (image)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON characters (name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rarity ON characters (rarity)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_uploader_id ON characters (uploader_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_uploader_name ON characters (uploader_name)')
        # Composite index for common query pattern
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rarity_event ON characters (rarity, event)')

        conn.commit()
        logger.info("SQLite indexes ensured for all columns.")
        await log_table_schema()  # Log schema and indexes
    except sqlite3.Error as e:
        logger.error(f"SQLite create_indexes error: {e}")

async def log_table_schema():
    """Log the schema and indexes of the characters table for debugging."""
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(characters)")
        columns = cursor.fetchall()
        logger.info("SQLite characters table schema: %s", columns)
        cursor.execute("PRAGMA index_list(characters)")
        indexes = cursor.fetchall()
        logger.info("SQLite characters table indexes: %s", indexes)
    except sqlite3.Error as e:
        logger.error(f"SQLite log_table_schema error: {e}")

async def fetch_characters(character_ids: list) -> list:
    """Fetch character details for a list of character IDs."""
    character_ids = [str(id) for id in character_ids]
    if not character_ids:
        return []

    try:
        conn = connect()
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in character_ids)
        query = f'''
            SELECT anime, channel_message_id, character_id, event, event_emoji, image, name, rarity, uploader_id, uploader_name
            FROM characters
            WHERE character_id IN ({placeholders})
        '''
        cursor.execute(query, character_ids)
        rows = cursor.fetchall()

        return [
            {
                'anime': row[0],
                'channel_message_id': row[1],
                'character_id': row[2],
                'event': row[3],
                'event_emoji': row[4],
                'image': row[5],
                'name': row[6],
                'rarity': row[7],
                'uploader_id': row[8],
                'uploader_name': row[9]
            }
            for row in rows
        ]
    except sqlite3.Error as e:
        logger.error(f"SQLite fetch_characters error: {e}")
        return []

async def get_random_character(rarity: str, require_no_event: bool = True) -> dict:
    """Get a random character with the specified rarity, optionally excluding events."""
    try:
        conn = connect()
        cursor = conn.cursor()

        query = '''
            SELECT anime, channel_message_id, character_id, event, event_emoji, image, name, rarity, uploader_id, uploader_name
            FROM characters
            WHERE rarity = ?
        '''
        params = [rarity]
        if require_no_event:
            query += ' AND event IS NULL'

        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"Queried rarity: {rarity}{' with event IS NULL' if require_no_event else ''}, found {len(rows)} characters")

        if rows:
            char = random.choice(rows)
            return {
                'anime': char[0],
                'channel_message_id': char[1],
                'character_id': char[2],
                'event': char[3],
                'event_emoji': char[4],
                'image': char[5],
                'name': char[6],
                'rarity': char[7],
                'uploader_id': char[8],
                'uploader_name': char[9]
            }
        return None
    except sqlite3.Error as e:
        logger.error(f"SQLite get_random_character error: {e}")
        return None

async def count_characters(anime: str, character_ids: list = None) -> int:
    """Count characters for a given anime, optionally filtered by character IDs."""
    try:
        conn = connect()
        cursor = conn.cursor()

        if character_ids:
            character_ids = [str(id) for id in character_ids]
            placeholders = ','.join('?' for _ in character_ids)
            query = f'''
                SELECT COUNT(*)
                FROM characters
                WHERE character_id IN ({placeholders}) AND anime = ?
            '''
            cursor.execute(query, character_ids + [anime])
        else:
            query = 'SELECT COUNT(*) FROM characters WHERE anime = ?'
            cursor.execute(query, (anime,))

        count = cursor.fetchone()[0]
        return count
    except sqlite3.Error as e:
        logger.error(f"SQLite count_characters error: {e}")
        return 0

async def get_distinct_values(column: str) -> list:
    """Get distinct values for a specified column in the characters table."""
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute(f'SELECT DISTINCT {column} FROM characters')
        values = [row[0] for row in cursor.fetchall()]
        return values
    except sqlite3.Error as e:
        logger.error(f"SQLite get_distinct_values error: {e}")
        return []

async def search_characters(query: str = None) -> list:
    """Search characters by name or anime, or return all characters if no query."""
    try:
        conn = connect()
        cursor = conn.cursor()

        if query:
            like_query = f'%{query}%'
            query_sql = '''
                SELECT anime, channel_message_id, character_id, event, event_emoji, image, name, rarity, uploader_id, uploader_name
                FROM characters
                WHERE name LIKE ? OR anime LIKE ?
            '''
            cursor.execute(query_sql, (like_query, like_query))
        else:
            query_sql = '''
                SELECT anime, channel_message_id, character_id, event, event_emoji, image, name, rarity, uploader_id, uploader_name
                FROM characters
            '''
            cursor.execute(query_sql)

        rows = cursor.fetchall()
        return [
            {
                'anime': row[0],
                'channel_message_id': row[1],
                'character_id': row[2],
                'event': row[3],
                'event_emoji': row[4],
                'image': row[5],
                'name': row[6],
                'rarity': row[7],
                'uploader_id': row[8],
                'uploader_name': row[9]
            }
            for row in rows
        ]
    except sqlite3.Error as e:
        logger.error(f"SQLite search_characters error: {e}")
        return []

async def search_user_characters(character_ids: list, query: str = None) -> list:
    """Search a user's characters by query across name, anime, character_id, rarity, or event."""
    character_ids = [str(id) for id in character_ids]
    if not character_ids:
        return []

    try:
        conn = connect()
        cursor = conn.cursor()

        placeholders = ','.join('?' for _ in character_ids)
        if query:
            like_query = f'%{query}%'
            query_sql = f'''
                SELECT anime, channel_message_id, character_id, event, event_emoji, image, name, rarity, uploader_id, uploader_name
                FROM characters
                WHERE character_id IN ({placeholders})
                AND (
                    name LIKE ? OR
                    anime LIKE ? OR
                    character_id LIKE ? OR
                    rarity LIKE ? OR
                    event LIKE ?
                )
            '''
            cursor.execute(query_sql, character_ids + [like_query] * 5)
        else:
            query_sql = f'''
                SELECT anime, channel_message_id, character_id, event, event_emoji, image, name, rarity, uploader_id, uploader_name
                FROM characters
                WHERE character_id IN ({placeholders})
            '''
            cursor.execute(query_sql, character_ids)

        rows = cursor.fetchall()
        return [
            {
                'anime': row[0],
                'channel_message_id': row[1],
                'character_id': row[2],
                'event': row[3],
                'event_emoji': row[4],
                'image': row[5],
                'name': row[6],
                'rarity': row[7],
                'uploader_id': row[8],
                'uploader_name': row[9]
            }
            for row in rows
        ]
    except sqlite3.Error as e:
        logger.error(f"SQLite search_user_characters error: {e}")
        return []




async def fetch_random_characters(count: int) -> list:
    """Fetch a random set of character details."""
    if count <= 0:
        return []

    try:
        conn = connect()
        cursor = conn.cursor()
        query = f'''
           _message_id, character_id, event, event_emoji, image, name, rarity, uploader_id, uploader_name
            FROM characters
            ORDER BY RANDOM() LIMIT ?
        '''
        cursor.execute(query, (count,))
        rows = cursor.fetchall()

        return [
            {
                'anime': row[0],
                'channel_message_id': row[1],
                'character_id': row[2],
                'event': row[3],
                'event_emoji': row[4],
                'image': row[5],
                'name': row[6],
                'rarity': row[7],
                'uploader_id': row[8],
                'uploader_name': row[9]
            }
            for row in rows
        ]
    except sqlite3.Error as e:
        logger.error(f"SQLite fetch_random_characters error: {e}")
        return []


async def get_characters_by_rarity(rarity: str, limit: int = None) -> list:
    """Fetch all characters of a specific rarity with their full data.
    
    Args:
        rarity: The rarity to filter by (e.g., 'SSR', 'SR', 'R')
        limit: Optional maximum number of characters to return
        
    Returns:
        List of character dictionaries with all their data
    """
    try:
        conn = connect()
        cursor = conn.cursor()

        query = '''
            SELECT anime, channel_message_id, character_id, event, event_emoji, image, name, rarity, uploader_id, uploader_name
            FROM characters
            WHERE rarity = ?
        '''
        params = [rarity]
        
        if limit is not None:
            query += ' LIMIT ?'
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [
            {
                'anime': row[0],
                'channel_message_id': row[1],
                'character_id': row[2],
                'event': row[3],
                'event_emoji': row[4],
                'image': row[5],
                'name': row[6],
                'rarity': row[7],
                'uploader_id': row[8],
                'uploader_name': row[9]
            }
            for row in rows
        ]
    except sqlite3.Error as e:
        logger.error(f"SQLite get_characters_by_rarity error: {e}")
        return []
