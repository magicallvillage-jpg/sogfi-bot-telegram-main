import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

# Source and Target connection strings
src_uri = "mongodb+srv://Theseize:Theseize@theseize.z1x5nvz.mongodb.net/?retryWrites=true&w=majority&appName=Theseize"
tgt_uri = "mongodb+srv://karinuzumaki0007:rwro5SJzPU2js4Eg@cluster0.aczm0tm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

async def migrate_data():
    src_client = AsyncIOMotorClient(src_uri)
    tgt_client = AsyncIOMotorClient(tgt_uri)

    src_db_names = await src_client.list_database_names()
    for db_name in src_db_names:
        if db_name in ("admin", "local", "config"):
            continue  # skip system databases
        src_db = src_client[db_name]
        tgt_db = tgt_client[db_name]
        coll_names = await src_db.list_collection_names()
        for coll_name in coll_names:
            src_coll = src_db[coll_name]
            tgt_coll = tgt_db[coll_name]
            cursor = src_coll.find({})
            docs = []
            async for doc in cursor:
                doc.pop("_id", None)  # remove _id to avoid duplicates, or keep as needed
                docs.append(doc)
                if len(docs) >= 1000:
                    await tgt_coll.insert_many(docs)
                    docs = []
            if docs:
                await tgt_coll.insert_many(docs)
    print("Migration complete.")
    src_client.close()
    tgt_client.close()

asyncio.run(migrate_data())
