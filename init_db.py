import asyncio
from db import collection, uploader_collection, counter_collection, user_collection

async def create_indexes():
    # Unique index on character_id for quick lookup and preventing duplicates
    await collection.create_index("character_id", unique=True)

    # Index for user_id to speed up uploader verification
    await uploader_collection.create_index("user_id", unique=True)

    # Index for character_id in user collection (array lookup)
    await user_collection.create_index("user_id", unique=True)
    await user_collection.create_index("characters")

    # Index for counters if needed
    await counter_collection.create_index("_id", unique=True)

if __name__ == "__main__":
    asyncio.run(create_indexes())
