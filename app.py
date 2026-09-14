
import logging
import asyncio
import random
import os
import nest_asyncio
import datetime

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    filters,
)
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.error import RetryAfter

from config import BOT_TOKEN
from db import collection, uploader_collection, user_collection, group_settings
from db_sqlite import create_indexes as create_sqlite_indexes, close_connection as close_sqlite
from handlers.spawn import handle_group_messages
from handlers.drops import set_drop_rate, show_drop_rates, init_default_drop_rates
from handlers.fragments import fragments
from handlers.take import take_character
from handlers.inline import inlinequery
from handlers.admin import set_spawn, stats, kill_user
from handlers.harem import show_harem, paginate_harem, delete_harem_message
from handlers.cdelete import cdelete_command
from handlers.rmarket import set_market
from handlers.sorts import sorts, handle_sort_selection, handle_rarity_selection
from handlers.eval import evaluate, execute, clear
from handlers.gift import gift_character, confirm_gift, give_character
from handlers.rarities import top_rarities
from handlers.ckill import ckill_command
from handlers.aegive import aegive, aeremove
from handlers.top import leaderboard, leaderboard_callback_handler
from handlers.ban import unbanbot_command, banbot_command
from handlers.trade import initiate_trade, confirm_trade, cancel_trade
from handlers.rarity import rarity_stats
from handlers.ftop import elixir_leaderboard
from handlers.fav import fav_character, fav_callback
from handlers.detect import detect_character
from handlers.event import set_event
from handlers.transfer import transfer_handler
from handlers.match import match, button_callback
from handlers.drop import get_current_drop_rates, set_single_drop_rate
from handlers.broadcast import broadcast
from handlers.dart import throw_dart
from handlers.market import market_command
from handlers.Wallpaper import wallpaper_command, wallpaper_callback, handle_wallpaper_image
from handlers.exchange import exchange_command
from handlers.setsell import setsell, removesell, mysell, handle_pagination

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_IMAGES = [
    "https://files.catbox.moe/kudu87.jpg",
    "https://files.catbox.moe/up82nn.jpg",
    "https://files.catbox.moe/6aosij.jpg",
]

NOTIFICATION_GROUP_ID = -1002655715837

application = None

class FloodState:
    until = None

async def clear_update_queue(app):
    try:
        q = getattr(app, "update_queue", None)
        if q is None:
            return
        while not q.empty():
            try:
                _ = q.get_nowait()
            except Exception:
                break
    except Exception as e:
        logger.exception(e)

async def telegram_send_with_handling(app, method_coro, *args, **kwargs):
    try:
        if FloodState.until and datetime.datetime.utcnow() < FloodState.until:
            return None
        return await method_coro(*args, **kwargs)
    except RetryAfter as e:
        wait = int(getattr(e, "retry_after", getattr(e, "timeout", 60)))
        FloodState.until = datetime.datetime.utcnow() + datetime.timedelta(seconds=wait)
        if app is not None:
            await clear_update_queue(app)
        try:
            await asyncio.sleep(min(wait, 5))
        except Exception:
            pass
        return None
    except Exception as e:
        logger.exception(e)
        return None

async def send_notification_to_group(context, message):
    try:
        app = application or getattr(context, "application", None)
        await telegram_send_with_handling(
            app,
            context.bot.send_message,
            chat_id=NOTIFICATION_GROUP_ID,
            text=message,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(e)

async def set_bot_commands(app):
    try:
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("setspawn", "Set spawn settings"),
            BotCommand("take", "Take a character"),
            BotCommand("gift", "Gift a character"),
            BotCommand("trade", "Initiate a trade"),
            BotCommand("top", "View top users"),
            BotCommand("harem", "Display your harem"),
            BotCommand("sorts", "Set harem sorting options"),
            BotCommand("arise", "Set your favorite character"),
            BotCommand("detect", "Detect for a character"),
            BotCommand("mysell", "List of your added p2p characters"),
            BotCommand("setsell", "Add your character in p2p"),
            BotCommand("removesell", "Remove character from p2p sell"),
            BotCommand("rarity", "Check your Rarity statistics"),
            BotCommand("match", "Find characters matching text"),
        ]
        await app.bot.set_my_commands(commands)
    except Exception as e:
        logger.error(e)

async def start(update, context):
    random_image = random.choice(BOT_IMAGES)
    keyboard = [
        [InlineKeyboardButton("𝖧𝖾𝗅𝗉", callback_data="help")],
        [
            InlineKeyboardButton("𝖴𝗉𝖽𝖺𝗍𝖾𝗌", url="https://t.me/taker_official_channel"),
            InlineKeyboardButton("𝖲𝗎𝗉𝗉𝗈𝗋𝗍", url="https://t.me/takers_official_group"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_message = (
        "𝖳𝖺𝗄𝖾𝗋𝗌 𝖡𝗈𝗍!\n\n"
        "𝖠𝗇𝗂𝗆𝖾 𝖼𝗁𝖺𝗋𝖺𝖼𝗍𝖾𝗋 𝖼𝗈𝗅𝗅𝖾𝖼𝗍𝗂𝗈𝗇 𝗀𝖺𝗆𝖾 𝖻𝗈𝗍!\n\n"
        "𝖡𝗈𝗍 𝗌𝗉𝖺𝗐𝗇𝗌 𝖼𝗁𝖺𝗋𝖺𝖼𝗍𝖾𝗋𝗌 𝗂𝗇 𝗀𝗋𝗈𝗎𝗉𝗌 𝖺𝖿𝗍𝖾𝗋 100 𝗆𝖾𝗌𝗌𝖺𝗀𝖾𝗌.\n"
        "𝖦𝗎𝖾𝗌𝗌 𝗇𝖺𝗆𝖾𝗌 𝗍𝗈 𝖼𝗅𝖺𝗂𝗆 𝖼𝗁𝖺𝗋𝖺𝖼𝗍𝖾𝗋𝗌 𝖺𝗇𝖽 𝖻𝗎𝗂𝗅𝖽 𝗒𝗈𝗎𝗋 𝖼𝗈𝗅𝗅𝖾𝖼𝗍𝗂𝗈𝗇.\n"
        "𝖳𝗋𝖺𝖽𝖾, 𝗀𝗂𝖿𝗍, 𝖺𝗇𝖽 𝗆𝗈𝗋𝖾!"
    )
    app = application or getattr(context, "application", None)
    await telegram_send_with_handling(
        app,
        context.bot.send_photo,
        chat_id=update.effective_chat.id,
        photo=random_image,
        caption=welcome_message,
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    user = update.effective_user
    user_info = (
        f"*New User Started Bot*\n"
        f"User ID: {user.id}\n"
        f"Username: @{user.username if user.username else 'None'}\n"
        f"Chat ID: {update.effective_chat.id}"
    )
    await send_notification_to_group(context, user_info)

async def handle_new_chat_members(update, context):
    bot_id = context.bot.id
    new_members = update.message.new_chat_members
    if any(member.id == bot_id for member in new_members):
        chat = update.effective_chat
        group_info = (
            f"*Bot Added to Group*\n"
            f"Group Name: {chat.title}\n"
            f"Group ID: {chat.id}"
        )
        await send_notification_to_group(context, group_info)

async def help_callback(update, context):
    query = update.callback_query
    await query.answer()
    app = application or getattr(context, "application", None)
    if query.data == "help":
        help_message = (
            "*𝖧𝖾𝗅𝗉 𝖬𝖾𝗇𝗎*\n\n"
            "- /start: 𝖵𝗂𝖾𝗐 𝗍𝗁𝖾 𝗆𝖺𝗂𝗇 𝗆𝖾𝗇𝗎\n"
            "- /take: 𝖢𝗅𝖺𝗂𝗆 𝖺 𝖼𝗁𝖺𝗋𝖺𝖼𝗍𝖾𝗋\n"
            "- /harem: 𝖢𝗁𝖾𝖼𝗄 𝗒𝗈𝗎𝗋 𝖼𝗈𝗅𝗅𝖾𝖼𝗍𝗂𝗈𝗇\n"
            "- /trade: 𝖳𝗋𝖺𝖽𝖾 𝖼𝗁𝖺𝗋𝖺𝖼𝗍𝖾𝗋𝗌\n"
            "- /top: 𝖲𝖾𝖾 𝗍𝗁𝖾 𝗅𝖾𝖺𝖽𝖾𝗋𝖻𝗈𝖺𝗋𝖽\n"
        )
        current_image = query.message.photo[-1].file_id if query.message.photo else random.choice(BOT_IMAGES)
        await telegram_send_with_handling(
            app,
            query.edit_message_media,
            media=InputMediaPhoto(media=current_image, caption=help_message, parse_mode="Markdown"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("𝖡𝖺𝖼𝗄", callback_data="back_to_start")]]),
        )
    elif query.data == "back_to_start":
        await start(update, context)

async def create_indexes():
    try:
        await collection.create_index("character_id", unique=True, sparse=True)
        await user_collection.create_index("user_id", unique=True, sparse=True)
        await group_settings.create_index("group_id", unique=True, sparse=True)
        await create_sqlite_indexes()
    except Exception as e:
        logger.error(e)

def build_application():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(set_bot_commands)
        .build()
    )
    app.add_handler(CommandHandler("start", start, block=False))
    app.add_handler(CommandHandler("setspawn", set_spawn, block=False))
    app.add_handler(CommandHandler("take", take_character, block=False))
    app.add_handler(CommandHandler("gift", gift_character, block=False))
    app.add_handler(CommandHandler("trade", initiate_trade, block=False))
    app.add_handler(CommandHandler("top", leaderboard, block=False))
    app.add_handler(CallbackQueryHandler(leaderboard_callback_handler, pattern=r"toggle_.*", block=False))
    app.add_handler(CommandHandler("harem", show_harem, block=False))
    app.add_handler(CallbackQueryHandler(paginate_harem, pattern=r"^page_", block=False))
    app.add_handler(CallbackQueryHandler(delete_harem_message, pattern=r"^delete_", block=False))
    app.add_handler(CommandHandler("sorts", sorts, block=False))
    app.add_handler(CallbackQueryHandler(handle_sort_selection, pattern=r"^sort_", block=False))
    app.add_handler(CallbackQueryHandler(handle_rarity_selection, pattern=r"^rarity_", block=False))
    app.add_handler(CallbackQueryHandler(confirm_gift, pattern=r"confirm_gift:\w+", block=False))
    app.add_handler(CallbackQueryHandler(confirm_trade, pattern=r"confirm_trade:\w+", block=False))
    app.add_handler(CommandHandler(["arise", "fav"], fav_character, block=False))
    app.add_handler(CallbackQueryHandler(fav_callback, pattern="^fav_", block=False))
    app.add_handler(CommandHandler("detect", detect_character, block=False))
    app.add_handler(CommandHandler("rarity", rarity_stats, block=False))
    app.add_handler(CommandHandler("setevent", set_event, block=False))
    app.add_handler(CommandHandler("banbot", banbot_command, block=False))
    app.add_handler(CallbackQueryHandler(handle_pagination, pattern="^mysell_", block=False))
    app.add_handler(CommandHandler("mysell", mysell, block=False))
    app.add_handler(CommandHandler("setsell", setsell, block=False))
    app.add_handler(CommandHandler("removesell", removesell, block=False))
    app.add_handler(CommandHandler("unbanbot", unbanbot_command, block=False))
    app.add_handler(CommandHandler("match", match))
    app.add_handler(CallbackQueryHandler(button_callback, pattern=r"match_clear_\d+", block=False))
    app.add_handler(CommandHandler("give", give_character, block=False))
    app.add_handler(CommandHandler("rarities", top_rarities, block=False))
    app.add_handler(CommandHandler("kill", kill_user, block=False))
    app.add_handler(CommandHandler("exchange", exchange_command, block=False))
    app.add_handler(CallbackQueryHandler(help_callback, pattern="help", block=False))
    app.add_handler(CallbackQueryHandler(help_callback, pattern="back_to_start", block=False))
    app.add_handler(CallbackQueryHandler(cancel_trade, pattern="^cancel_trade", block=False))
    app.add_handler(CommandHandler("stats", stats, block=False))
    app.add_handler(CommandHandler("fragments", fragments, block=False))
    app.add_handler(CommandHandler("market", market_command, block=False))
    app.add_handler(CommandHandler("wallpaper", wallpaper_command, block=False))
    app.add_handler(CallbackQueryHandler(wallpaper_callback, pattern="^(confirm|cancel)_wallpaper_", block=False))
    app.add_handler(MessageHandler(filters.PHOTO, handle_wallpaper_image, block=False))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members, block=False))
    app.add_handler(transfer_handler)
    app.add_handler(CommandHandler(["e", "ev", "eva", "eval"], evaluate, block=False))
    app.add_handler(CommandHandler(["x", "ex", "exe", "exec", "py"], execute, block=False))
    app.add_handler(CommandHandler("clearlocals", clear, block=False))
    app.add_handler(CommandHandler("ckill", ckill_command, block=False))
    app.add_handler(CommandHandler("cdelete", cdelete_command, block=False))
    app.add_handler(CommandHandler("droprates", show_drop_rates, block=False))
    app.add_handler(CommandHandler("droprate", set_drop_rate, block=False))
    app.add_handler(CommandHandler("broadcast", broadcast, block=False))
    app.add_handler(CommandHandler("ftop", elixir_leaderboard, block=False))
    app.add_handler(InlineQueryHandler(inlinequery, block=False))
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, handle_group_messages, block=False))
    return app

async def main():
    global application
    application = build_application()
    await create_indexes()
    await application.run_polling(drop_pending_updates=True)
    close_sqlite()

nest_asyncio.apply()

if __name__ == "__main__":
    asyncio.run(init_default_drop_rates())
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logger.error(e)
