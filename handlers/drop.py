import datetime
from db import db

drop_rates_collection = db["drop_rates"]



DEFAULT_DROP_RATES = {
    '1': 30,
    '2': 20,
    '3': 25,
    '4': 8,
    '5': 7,
    '6': 5,
    '7': 3,
    '8': 2
}

async def init_default_drop_rates():
    if await drop_rates_collection.count_documents({}) == 0:
        await drop_rates_collection.insert_one({
            "rates": DEFAULT_DROP_RATES,
            "last_updated": datetime.datetime.utcnow()
        })

async def get_current_drop_rates():
    doc = await drop_rates_collection.find_one({})
    if doc:
        return {int(k): v for k, v in doc['rates'].items()}
    return {int(k): v for k, v in DEFAULT_DROP_RATES.items()}

async def update_drop_rates(new_rates):
    str_rates = {str(k): v for k, v in new_rates.items()}
    await drop_rates_collection.update_one(
        {},
        {"$set": {"rates": str_rates, "last_updated": datetime.datetime.utcnow()}},
        upsert=True
    )

async def set_single_drop_rate(rarity, new_rate):
    current_rates = await get_current_drop_rates()
    current_rates[rarity] = new_rate
    await update_drop_rates(current_rates)
