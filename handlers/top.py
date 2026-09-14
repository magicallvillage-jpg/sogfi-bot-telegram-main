from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from db import user_collection, group_collection
import html
import re

def truncate_name(name, limit=10):
    if not name:
        return ""
    rtl_chars = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u0590-\u05FF\uFE70-\uFEFF]')
    is_rtl = bool(rtl_chars.search(name))
    words = name.split()
    if len(words) <= limit:
        return name
    truncated = ' '.join(words[:limit])
    return f"{truncated} …" if not is_rtl else f"… {truncated}"

def format_number(value):
    try:
        return f"{int(value):,}"
    except Exception:
        try:
            return f"{float(value):,}"
        except Exception:
            return "0"

def extract_numeric(value):
    try:
        return int(value)
    except Exception:
        try:
            return float(value)
        except Exception:
            return 0

def format_caption_header(title):
    return f"<b>{title}</b>\n{'━'*25}\n\n"

def format_leaderboard_entry(rank, name, value):
    emoji = ["🥇", "🥈", "🥉"][rank-1] if rank <= 3 else f"{rank}."
    return f"{emoji} ⤞ <b>{name}</b> ⤐ <b>{format_number(value)}</b>\n"

def format_leaderboard_entry_with_unique(rank, name, total_value, unique_value):
    emoji = ["🥇", "🥈", "🥉"][rank-1] if rank <= 3 else f"{rank}."
    return (
        f"{emoji} ⤞ <b>{name}</b> ⤐ <b>{format_number(total_value)}</b> (<code>{format_number(unique_value)}</code>)\n"
    )

async def generate_global_users_caption():
    pipeline = [
        {"$addFields": {
            "total_chars": {
                "$sum": {
                    "$map": {
                        "input": {"$objectToArray": "$characters"},
                        "as": "char",
                        "in": "$$char.v"
                    }
                }
            },
            "unique_chars": {"$size": {"$ifNull": [{"$objectToArray": "$characters"}, []]}}
        }},
        {"$sort": {"total_chars": -1}},
        {"$limit": 10}
    ]
    top_users = await user_collection.aggregate(pipeline).to_list(length=10)
    caption = format_caption_header("Top 10 Collectors (Total with Unique)")
    if top_users:
        for rank, user in enumerate(top_users, start=1):
            first_name = html.escape(user.get("first_name", "Unknown"))
            username = user.get("username", None)
            total_chars = extract_numeric(user.get("total_chars", 0))
            unique_chars = extract_numeric(user.get("unique_chars", 0))
            truncated_name = truncate_name(first_name)
            markdown_name = (
                f"<a href='https://t.me/{username}'>{truncated_name}</a>"
                if username else truncated_name
            )
            caption += format_leaderboard_entry_with_unique(rank, markdown_name, total_chars, unique_chars)
    else:
        caption += "No data available for Top Collectors."
    return caption

async def generate_top_groups_caption():
    top_groups = await group_collection.find(
        {}, {"group_name": 1, "group_id": 1, "total_characters": 1}
    ).sort("total_characters", -1).limit(10).to_list(length=10)
    caption = format_caption_header("Top 10 Groups")
    if top_groups:
        for rank, group in enumerate(top_groups, start=1):
            group_name = html.escape(group.get("group_name", "Unknown"))
            total_count = extract_numeric(group.get("total_characters", 0))
            truncated_group_name = truncate_name(group_name)
            caption += format_leaderboard_entry(rank, truncated_group_name, total_count)
    else:
        caption += "No data available for Top Groups."
    return caption

async def generate_top_active_users_caption(chat_id):
    group_data = await group_collection.find_one({"group_id": chat_id})
    if not group_data or "user_stats" not in group_data:
        return format_caption_header("Most Active Users in This Group") + "No data available for Most Active Users in This Group."
    user_stats = group_data["user_stats"]
    sorted_users = sorted(
        user_stats.items(), 
        key=lambda x: extract_numeric(x[1].get("character_count", 0)),
        reverse=True
    )[:10]
    caption = format_caption_header("Most Active Users in This Group")
    for rank, (user_id, user_info) in enumerate(sorted_users, start=1):
        first_name = html.escape(user_info.get("name", "Unknown"))
        character_count = extract_numeric(user_info.get("character_count", 0))
        truncated_name = truncate_name(first_name)
        caption += format_leaderboard_entry(rank, truncated_name, character_count)
    return caption

async def leaderboard(update, context):
    try:
        chat_id = update.effective_chat.id
        invoker_id = update.effective_user.id
        caption = await generate_global_users_caption()
        image_url = "https://files.catbox.moe/mpfkbd.jpg"
        buttons = [
            [InlineKeyboardButton("Group Collectors", callback_data=f"toggle_active_{chat_id}:{invoker_id}")],
            [InlineKeyboardButton("Top Groups", callback_data=f"toggle_groups:{invoker_id}")],
            [InlineKeyboardButton("✅ Global Collectors", callback_data=f"toggle_users:{invoker_id}")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_photo(
            photo=image_url,
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception as e:
        await update.message.reply_text(
            f"An error occurred: {html.escape(str(e))}",
            parse_mode="HTML",
        )

async def leaderboard_callback_handler(update, context):
    query = update.callback_query
    try:
        data = query.data
        if ":" in data:
            action, invoker_id_str = data.rsplit(":", 1)
            invoker_id = int(invoker_id_str)
        else:
            action = data
            invoker_id = None
        user_id = query.from_user.id
        chat_id = query.message.chat_id
        current_caption = query.message.caption or ""
        image_url = "https://files.catbox.moe/mpfkbd.jpg"
        # Show alert as popup if not original invoker
        if invoker_id and user_id != invoker_id:
            await query.answer("itss not your commanded by you", show_alert=True)
            return
        await query.answer()
        if action == "toggle_groups":
            if "Top 10 Groups" in current_caption:
                return
            caption = await generate_top_groups_caption()
            buttons = [
                [InlineKeyboardButton("Group Collectors", callback_data=f"toggle_active_{chat_id}:{invoker_id}")],
                [InlineKeyboardButton("✅ Top Groups", callback_data=f"toggle_groups:{invoker_id}")],
                [InlineKeyboardButton("Global Collectors", callback_data=f"toggle_users:{invoker_id}")],
            ]
        elif action == "toggle_users":
            if "Global Collectors" in current_caption:
                return
            caption = await generate_global_users_caption()
            buttons = [
                [InlineKeyboardButton("Group Collectors", callback_data=f"toggle_active_{chat_id}:{invoker_id}")],
                [InlineKeyboardButton("Top Groups", callback_data=f"toggle_groups:{invoker_id}")],
                [InlineKeyboardButton("✅ Global Collectors", callback_data=f"toggle_users:{invoker_id}")],
            ]
        elif action.startswith("toggle_active_"):
            if "Most Active Users in This Group" in current_caption:
                return
            caption = await generate_top_active_users_caption(chat_id)
            buttons = [
                [InlineKeyboardButton("✅ Group Collectors", callback_data=f"toggle_active_{chat_id}:{invoker_id}")],
                [InlineKeyboardButton("Top Groups", callback_data=f"toggle_groups:{invoker_id}")],
                [InlineKeyboardButton("Global Collectors", callback_data=f"toggle_users:{invoker_id}")],
            ]
        else:
            return
        await query.message.edit_media(
            media={
                "type": "photo",
                "media": image_url,
                "caption": caption,
                "parse_mode": "HTML"
            },
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            await query.message.edit_caption(
                f"An error occurred: {html.escape(str(e))}",
                parse_mode="HTML",
            )
