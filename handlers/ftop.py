import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from db import user_collection, collection as character_collection

async def elixir_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Get all Elixir character IDs first
        elixir_chars = await character_collection.find(
            {"rarity": "🍭 Elixir"},
            {"character_id": 1}
        ).to_list(length=None)
        
        if not elixir_chars:
            await update.message.reply_text("No Elixir characters exist in the database yet.")
            return

        elixir_char_ids = [str(char["character_id"]) for char in elixir_chars]

        # Find users who have any of these characters
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {f"characters.{char_id}": {"$exists": True}}
                        for char_id in elixir_char_ids
                    ]
                }
            },
            {
                "$project": {
                    "user_id": 1,
                    "first_name": 1,
                    "username": 1,
                    "unique_elixir": {
                        "$size": {
                            "$filter": {
                                "input": [
                                    {
                                        "$cond": [
                                            {"$gt": [{"$ifNull": [f"$characters.{char_id}", 0]}, 0]},
                                            char_id,
                                            None
                                        ]
                                    }
                                    for char_id in elixir_char_ids
                                ],
                                "cond": {"$ne": ["$$this", None]}
                            }
                        }
                    }
                }
            },
            {"$sort": {"unique_elixir": -1}},
            {"$limit": 10}
        ]

        top_users = await user_collection.aggregate(pipeline).to_list(length=10)

        if not top_users:
            await update.message.reply_text("No users have collected characters yet.")
            return

        # Prepare the leaderboard message
        leaderboard_text = "ꕥ <b>Top 10 👾 Fragments Users</b>\n\n"
        
        for rank, user in enumerate(top_users, 1):
            user_id = user.get("user_id")
            first_name = html.escape(user.get("first_name", "Unknown"))
            username = user.get("username")
            count = user.get("unique_elixir", 0)

            # Create user mention
            if username:
                user_mention = f'<a href="https://t.me/{username}">{first_name}</a>'
            else:
                user_mention = first_name

            # Add rank emoji for top 3
            rank_emoji = ["🥇", "🥈", "🥉"][rank-1] if rank <= 3 else f"{rank}."
            
            # Add user to leaderboard text
            leaderboard_text += f"{rank_emoji} {user_mention} ⟶ <b>{count}</b>\n"

        # Use the specific image URL
        photo_url = "https://graph.org/file/757dcc59965cda8f8507a-e351e7e58757bc8bbd.jpg"
        
        try:
            await update.message.reply_photo(
                photo=photo_url,
                caption=leaderboard_text,
                parse_mode='HTML'
            )
                
        except Exception:
            # Fallback if can't access photo URL
            await update.message.reply_html(
                leaderboard_text,
                disable_web_page_preview=True
            )

    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")
