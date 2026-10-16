# AS SHOP Telegram Bot
# Install: pip install pyTelegramBotAPI
# Add your BotFather token in BOT_TOKEN below.

import os
import sqlite3
import secrets
import string
import telebot
from telebot import types
from datetime import datetime

BOT_TOKEN = "8770604361:AAGnO3InuJrIDcczeob6mDhMHqUOvbPqjfI"
ADMIN_ID = 7079833447
DB_NAME = "as_shop.db"

if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
    raise SystemExit("ERROR: BOT_TOKEN-er jaygay BotFather token boshan.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.executescript('''
CREATE TABLE IF NOT EXISTS users (
 user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, balance REAL DEFAULT 0,
 referred_by INTEGER, referrals INTEGER DEFAULT 0, successful_orders INTEGER DEFAULT 0,
 created_at TEXT
);
CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, link TEXT, title TEXT);
CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, photo_file_id TEXT,
 description TEXT, price REAL, active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER, product_name TEXT,
 price REAL, status TEXT DEFAULT 'NEW', created_at TEXT, refunded INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS deposits (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, method TEXT, screenshot_file_id TEXT,
 status TEXT DEFAULT 'PENDING', created_at TEXT, commission_paid REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS offer_products (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, photo_file_id TEXT, description TEXT, price REAL,
 stock INTEGER DEFAULT 0, active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS redeem_codes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, max_users INTEGER, points REAL, channel_id TEXT,
 channel_link TEXT, channel_title TEXT, used_count INTEGER DEFAULT 0, active INTEGER DEFAULT 1, created_at TEXT
);
CREATE TABLE IF NOT EXISTS redeem_uses (
 id INTEGER PRIMARY KEY AUTOINCREMENT, redeem_id INTEGER, user_id INTEGER, created_at TEXT, UNIQUE(redeem_id,user_id)
);
''' )
# migrations for existing DB
def add_column(table, column, definition):
    try:
        cur.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
    except sqlite3.OperationalError:
        pass
add_column('users', 'points', 'REAL DEFAULT 0')
add_column('orders', 'customer_info', 'TEXT')
add_column('orders', 'is_offer', 'INTEGER DEFAULT 0')
add_column('products', 'info_prompt', 'TEXT')
conn.commit()

# Simple in-memory conversation state (resets if bot restarts)
states = {}

def get_setting(key, default=''):
    row = cur.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return row['value'] if row else default

def set_setting(key, value):
    cur.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', (key, str(value)))
    conn.commit()

def maintenance_on():
    return get_setting('maintenance', '0') == '1'

def maintenance_text():
    return get_setting('maintenance_text', '🛠️ Bot is currently under maintenance. Please try again later.')

def order_info_prompt():
    return get_setting('order_info_prompt', 'Order complete করার জন্য প্রয়োজনীয় তথ্য লিখুন:')

def is_admin(uid): return uid == ADMIN_ID

def money(value): return f"{float(value):.2f}".rstrip('0').rstrip('.')

def get_user(uid): return cur.execute('SELECT * FROM users WHERE user_id=?', (uid,)).fetchone()

def add_user(user, referrer=None):
    existing = get_user(user.id)
    if existing:
        cur.execute('UPDATE users SET username=?, first_name=? WHERE user_id=?',
                    (user.username or '', user.first_name or '', user.id))
        conn.commit(); return False
    valid_ref = referrer if referrer and referrer != user.id and get_user(referrer) else None
    cur.execute('INSERT INTO users(user_id,username,first_name,balance,referred_by,created_at) VALUES(?,?,?,?,?,?)',
                (user.id, user.username or '', user.first_name or '', 0, valid_ref, datetime.now().isoformat(timespec='seconds')))
    if valid_ref:
        cur.execute('UPDATE users SET referrals=referrals+1 WHERE user_id=?', (valid_ref,))
    conn.commit()
    if valid_ref:
        try:
            bot.send_message(valid_ref, '🎉 CONGRATULATIONS YOU GOT NEW REFAR!')
        except Exception: pass
    return True

def main_menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row('👤 PROFILE', '🔗 REFAR')
    kb.row('🛒 ORDER ITEAM', '🎁 OFFER ITEMS')
    kb.row('🎟 REDEEM POINT', '📊 STATUS')
    kb.row('💳 DEPOSIT', '🧾 DEPOSIT HISTORY')
    kb.row('🆘 SUPPORT')
    return kb

def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row('➕ ADD CHANNEL', '➖ REMOVE CHANNEL')
    kb.row('💰 ADD MONEY', '✂️ CUT MONEY')
    kb.row('📂 ADD CATEGORY', '🗑 CUT CATEGORY')
    kb.row('➕ ADD PRODUCT', '🗑 CUT PRODUCTS')
    kb.row('🎁 ADD OFFER', '🗑 REMOVE OFFER')
    kb.row('🎟 REDEEM CREATE')
    kb.row('🛠 MAINTENANCE', '📋 ORDER LIST')
    kb.row('📢 BROADCAST')
    kb.row('⬅️ USER PANEL')
    return kb

def joined(uid):
    rows = cur.execute('SELECT chat_id FROM channels').fetchall()
    for row in rows:
        try:
            member = bot.get_chat_member(row['chat_id'], uid)
            if member.status in ('left', 'kicked') or (member.status == 'restricted' and not member.is_member):
                return False
        except Exception:
            return False
    return True

def join_prompt(chat_id):
    rows = cur.execute('SELECT * FROM channels').fetchall()
    kb = types.InlineKeyboardMarkup()
    for row in rows:
        kb.add(types.InlineKeyboardButton('Join ' + (row['title'] or 'Channel'), url=row['link']))
    kb.add(types.InlineKeyboardButton('✅ Joined - Check', callback_data='check_join'))
    bot.send_message(chat_id, '🔒 আগে নিচের channel-গুলোতে join করুন, তারপর Check চাপুন।', reply_markup=kb)

def user_panel(message):
    if not joined(message.from_user.id):
        join_prompt(message.chat.id); return
    bot.send_message(message.chat.id, '🛍️ <b>WELCOME TO AS SHOP</b>\nনিচের menu থেকে option বেছে নিন।', reply_markup=main_menu(message.from_user.id))

def show_categories(chat_id):
    rows = cur.execute('SELECT * FROM categories ORDER BY name').fetchall()
    if not rows:
        bot.send_message(chat_id, 'এখনো কোনো category নেই।'); return
    kb = types.InlineKeyboardMarkup()
    for r in rows: kb.add(types.InlineKeyboardButton(r['name'], callback_data=f"cat:{r['id']}"))
    bot.send_message(chat_id, '📂 <b>SELECT CATEGORY</b>', reply_markup=kb)

def show_products(chat_id, cat_id):
    rows = cur.execute('SELECT * FROM products WHERE category_id=? AND active=1 ORDER BY id DESC', (cat_id,)).fetchall()
    if not rows:
        bot.send_message(chat_id, 'এই category-তে কোনো product নেই।'); return
    kb = types.InlineKeyboardMarkup()
    for r in rows:
        kb.add(types.InlineKeyboardButton(f"{r['name']} — ৳{money(r['price'])}", callback_data=f"prod:{r['id']}"))
    bot.send_message(chat_id, '🛒 <b>PRODUCT LIST</b>', reply_markup=kb)

def show_product(chat_id, product_id):
    p = cur.execute('SELECT p.*, c.name AS category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.id=? AND p.active=1', (product_id,)).fetchone()
    if not p:
        bot.send_message(chat_id, 'Product পাওয়া যায়নি।'); return
    text = f"<b>{p['name']}</b>\n📂 Category: {p['category'] or 'N/A'}\n\n{p['description']}\n\n💰 Price: ৳{money(p['price'])}"
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('✅ ORDER NOW', callback_data=f"order:{p['id']}"))
    try:
        if p['photo_file_id']: bot.send_photo(chat_id, p['photo_file_id'], caption=text, reply_markup=kb)
        else: bot.send_message(chat_id, text, reply_markup=kb)
    except Exception: bot.send_message(chat_id, text, reply_markup=kb)

def show_offer_items(chat_id):
    rows = cur.execute('SELECT * FROM offer_products WHERE active=1 ORDER BY id DESC').fetchall()
    if not rows:
        bot.send_message(chat_id, 'এখন কোনো OFFER ITEMS নেই।'); return
    kb = types.InlineKeyboardMarkup()
    for r in rows:
        stock = 'STOCK OUT' if int(r['stock']) <= 0 else f"Stock: {r['stock']}"
        kb.add(types.InlineKeyboardButton(f"{r['name']} — ৳{money(r['price'])} — {stock}", callback_data=f"offer:{r['id']}"))
    bot.send_message(chat_id, '🎁 <b>OFFER ITEMS</b>', reply_markup=kb)

def show_offer_product(chat_id, offer_id):
    p = cur.execute('SELECT * FROM offer_products WHERE id=? AND active=1', (offer_id,)).fetchone()
    if not p:
        bot.send_message(chat_id, 'Offer product পাওয়া যায়নি।'); return
    stock = 'STOCK OUT' if int(p['stock']) <= 0 else str(p['stock'])
    text = f"🎁 <b>{p['name']}</b>\n\n{p['description']}\n\n💰 Price: ৳{money(p['price'])}\n📦 Stock: {stock}"
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('✅ ORDER NOW', callback_data=f"offerorder:{p['id']}"))
    try:
        if p['photo_file_id']: bot.send_photo(chat_id, p['photo_file_id'], caption=text, reply_markup=kb)
        else: bot.send_message(chat_id, text, reply_markup=kb)
    except Exception: bot.send_message(chat_id, text, reply_markup=kb)

def order_card(order_id, chat_id=ADMIN_ID):
    o = cur.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
    if not o: return
    kb = types.InlineKeyboardMarkup()
    if o['status'] == 'NEW':
        kb.row(types.InlineKeyboardButton('✅ CONFIRM', callback_data=f'ordact:confirm:{order_id}'),
               types.InlineKeyboardButton('❌ CANCEL', callback_data=f'ordact:cancel:{order_id}'))
        kb.row(types.InlineKeyboardButton('💸 REFUND', callback_data=f'ordact:refund:{order_id}'))
    kb.row(types.InlineKeyboardButton('💬 Message User', callback_data=f'askuser:{order_id}'),
           types.InlineKeyboardButton('↩️ Reply to User', callback_data=f'replyuser:{order_id}'))
    text = (f"🧾 <b>ORDER #{o['id']}</b>\nUser ID: <code>{o['user_id']}</code>\n"
            f"Product: {o['product_name']}\nPrice: ৳{money(o['price'])}\nUser Info: {o['customer_info'] or 'N/A'}\nStatus: <b>{o['status']}</b>\nDate: {o['created_at']}")
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.message_handler(commands=['start'])
def start(message):
    states.pop(message.from_user.id, None)
    ref = None
    parts = message.text.split(maxsplit=1)
    redeem_code = None
    if len(parts) > 1 and parts[1].startswith('ref_'):
        try: ref = int(parts[1][4:])
        except ValueError: pass
    elif len(parts) > 1 and parts[1].startswith('redeem_'):
        redeem_code = parts[1][7:].upper()
    add_user(message.from_user, ref)
    if maintenance_on() and not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, maintenance_text(), reply_markup=types.ReplyKeyboardRemove()); return
    if redeem_code:
        if not joined(message.from_user.id): join_prompt(message.chat.id); return
        process_redeem(message.from_user.id, redeem_code); return
    user_panel(message)

@bot.message_handler(commands=['admin'])
def admin(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, '⛔ এই command শুধু admin-এর জন্য।'); return
    bot.send_message(message.chat.id, '⚙️ <b>AS SHOP ADMIN PANEL</b>', reply_markup=admin_menu())

def process_redeem(uid, code, call=None):
    r=cur.execute('SELECT * FROM redeem_codes WHERE code=? AND active=1',(code,)).fetchone()
    def alert(msg):
        if call: bot.answer_callback_query(call.id,msg,show_alert=True)
        else: bot.send_message(uid,msg)
    if not r or int(r['used_count']) >= int(r['max_users']): alert('❌ Redeem code invalid or limit finished.'); return
    if cur.execute('SELECT 1 FROM redeem_uses WHERE redeem_id=? AND user_id=?',(r['id'],uid)).fetchone(): alert('❌ আপনি এই code আগে redeem করেছেন।'); return
    if r['channel_id']:
        try:
            m=bot.get_chat_member(r['channel_id'],uid)
            if m.status in ('left','kicked') or (m.status=='restricted' and not m.is_member):
                kb=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('JOIN CHANNEL',url=r['channel_link']),types.InlineKeyboardButton('✅ REDEEM AGAIN',callback_data=f"redeem:{code}"))
                bot.send_message(uid,'🔒 Redeem করতে আগে required channel-এ join করুন।',reply_markup=kb); return
        except Exception:
            alert('❌ Channel join verify করা যাচ্ছে না।'); return
    try:
        cur.execute('INSERT INTO redeem_uses(redeem_id,user_id,created_at) VALUES(?,?,?)',(r['id'],uid,datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        cur.execute('UPDATE redeem_codes SET used_count=used_count+1 WHERE id=?',(r['id'],))
        cur.execute('UPDATE users SET points=COALESCE(points,0)+? WHERE user_id=?',(r['points'],uid)); conn.commit()
    except sqlite3.IntegrityError:
        alert('❌ আপনি এই code আগে redeem করেছেন।'); return
    if call: bot.answer_callback_query(call.id,'Redeem successful!')
    bot.send_message(uid,f"✅ REDEEM SUCCESSFUL!\n🎟 You got {money(r['points'])} points.",reply_markup=main_menu(uid))

@bot.callback_query_handler(func=lambda c: c.data == 'check_join')
def check_join_cb(call):
    if joined(call.from_user.id):
        bot.answer_callback_query(call.id, 'Join verified!')
        bot.send_message(call.message.chat.id, '✅ Join successful.', reply_markup=main_menu(call.from_user.id))
    else: bot.answer_callback_query(call.id, 'সব channel-এ join করুন।', show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith('cat:'))
def category_cb(call):
    if maintenance_on() and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, maintenance_text(), show_alert=True); return
    if not joined(call.from_user.id):
        bot.answer_callback_query(call.id, 'আগে channel join করুন।', show_alert=True); return
    show_products(call.message.chat.id, int(call.data.split(':')[1])); bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith('prod:'))
def product_cb(call):
    if maintenance_on() and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, maintenance_text(), show_alert=True); return
    if not joined(call.from_user.id):
        bot.answer_callback_query(call.id, 'আগে channel join করুন।', show_alert=True); return
    show_product(call.message.chat.id, int(call.data.split(':')[1])); bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith('order:'))
def order_cb(call):
    if maintenance_on() and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, maintenance_text(), show_alert=True); return
    uid = call.from_user.id
    if not joined(uid):
        bot.answer_callback_query(call.id, 'আগে channel join করুন।', show_alert=True); return
    pid = int(call.data.split(':')[1])
    p = cur.execute('SELECT * FROM products WHERE id=? AND active=1', (pid,)).fetchone()
    u = get_user(uid)
    if not p or not u:
        bot.answer_callback_query(call.id, 'Product পাওয়া যায়নি।', show_alert=True); return
    if float(u['balance']) < float(p['price']):
        bot.answer_callback_query(call.id, 'আপনার balance যথেষ্ট নয়।', show_alert=True)
        bot.send_message(uid, f"❌ পর্যাপ্ত balance নেই।\nPrice: ৳{money(p['price'])}\nBalance: ৳{money(u['balance'])}")
        return
    info_prompt = (p['info_prompt'] or '').strip() or order_info_prompt()
    states[uid] = {'step':'order_info', 'product_id':pid, 'product_name':p['name'], 'price':float(p['price']), 'is_offer':0, 'info_prompt':info_prompt}
    bot.answer_callback_query(call.id)
    bot.send_message(uid, info_prompt)

@bot.callback_query_handler(func=lambda c: c.data.startswith('offer:'))
def offer_product_cb(call):
    if maintenance_on() and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, maintenance_text(), show_alert=True); return
    if not joined(call.from_user.id):
        bot.answer_callback_query(call.id, 'আগে channel join করুন।', show_alert=True); return
    show_offer_product(call.message.chat.id, int(call.data.split(':')[1])); bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith('offerorder:'))
def offer_order_cb(call):
    if maintenance_on() and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, maintenance_text(), show_alert=True); return
    uid=call.from_user.id; oid=int(call.data.split(':')[1])
    p=cur.execute('SELECT * FROM offer_products WHERE id=? AND active=1',(oid,)).fetchone(); u=get_user(uid)
    if not p or int(p['stock']) <= 0:
        bot.answer_callback_query(call.id, 'STOCK OUT', show_alert=True); return
    if not u or float(u['balance']) < float(p['price']):
        bot.answer_callback_query(call.id, 'আপনার balance যথেষ্ট নয়।', show_alert=True); return
    states[uid]={'step':'order_info','product_id':oid,'product_name':p['name'],'price':float(p['price']),'is_offer':1}
    bot.answer_callback_query(call.id); bot.send_message(uid, order_info_prompt())

@bot.callback_query_handler(func=lambda c: c.data.startswith('userorderconfirm:'))
def user_order_confirm_cb(call):
    uid=call.from_user.id; s=states.get(uid,{})
    if s.get('step')!='order_confirm':
        bot.answer_callback_query(call.id,'এই order session শেষ হয়েছে।',show_alert=True); return
    if call.data.endswith(':no'):
        states.pop(uid,None); bot.answer_callback_query(call.id,'Canceled'); bot.send_message(uid,'❌ Order canceled.',reply_markup=main_menu(uid)); return
    u=get_user(uid)
    if not u or float(u['balance']) < float(s['price']):
        states.pop(uid,None); bot.answer_callback_query(call.id,'Balance যথেষ্ট নয়।',show_alert=True); return
    if s['is_offer']:
        p=cur.execute('SELECT * FROM offer_products WHERE id=? AND active=1',(s['product_id'],)).fetchone()
        if not p or int(p['stock']) <= 0:
            states.pop(uid,None); bot.answer_callback_query(call.id,'STOCK OUT',show_alert=True); return
        cur.execute('UPDATE offer_products SET stock=stock-1 WHERE id=? AND stock>0',(s['product_id'],))
        if cur.rowcount != 1:
            conn.rollback(); states.pop(uid,None); bot.answer_callback_query(call.id,'STOCK OUT',show_alert=True); return
    cur.execute('UPDATE users SET balance=balance-? WHERE user_id=?',(s['price'],uid))
    cur.execute('INSERT INTO orders(user_id,product_id,product_name,price,status,created_at,customer_info,is_offer) VALUES(?,?,?,?,?,?,?,?)',
                (uid,s['product_id'],s['product_name'],s['price'],'NEW',datetime.now().strftime('%Y-%m-%d %H:%M:%S'),s['customer_info'],s['is_offer']))
    order_id=cur.lastrowid; conn.commit(); states.pop(uid,None)
    bot.answer_callback_query(call.id,'Order confirmed!')
    bot.send_message(uid,f'✅ আপনার order #{order_id} admin-এর কাছে পাঠানো হয়েছে।',reply_markup=main_menu(uid))
    order_card(order_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith('redeem:'))
def redeem_cb(call):
    if maintenance_on() and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, maintenance_text(), show_alert=True); return
    uid=call.from_user.id; code=call.data.split(':',1)[1]
    process_redeem(uid, code, call)

@bot.callback_query_handler(func=lambda c: c.data.startswith('ordact:'))
def order_action(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, 'Admin only.', show_alert=True); return
    _, action, oid_s = call.data.split(':'); oid = int(oid_s)
    o = cur.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    if not o:
        bot.answer_callback_query(call.id, 'Order পাওয়া যায়নি।'); return
    if action == 'confirm' and o['status'] == 'NEW':
        cur.execute("UPDATE orders SET status='CONFIRMED' WHERE id=?", (oid,))
        cur.execute('UPDATE users SET successful_orders=successful_orders+1 WHERE user_id=?', (o['user_id'],))
        msg = '✅ YOUR ORDER CONFIRMED'
    elif action in ('cancel','refund') and o['status'] in ('NEW','CONFIRMED'):
        new_status = 'CANCELED' if action == 'cancel' else 'REFUNDED'
        if not o['refunded']:
            cur.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (o['price'], o['user_id']))
            if int(o['is_offer'] or 0) == 1:
                cur.execute('UPDATE offer_products SET stock=stock+1 WHERE id=?', (o['product_id'],))
        cur.execute('UPDATE orders SET status=?, refunded=1 WHERE id=?', (new_status, oid))
        msg = '❌ YOUR ORDER IS CANCELED' if action == 'cancel' else '💸 YOUR ORDER REFUNDED'
    else:
        bot.answer_callback_query(call.id, 'এই order-এ এই action করা যাবে না।', show_alert=True); return
    conn.commit()
    try: bot.send_message(o['user_id'], msg)
    except Exception: pass
    bot.answer_callback_query(call.id, 'Updated!')
    order_card(oid)

@bot.callback_query_handler(func=lambda c: c.data.startswith('askuser:') or c.data.startswith('replyuser:'))
def admin_message_prompt(call):
    if not is_admin(call.from_user.id): return
    mode, oid = call.data.split(':'); oid = int(oid)
    states[call.from_user.id] = {'step': 'admin_message', 'order_id': oid, 'mode': mode}
    bot.answer_callback_query(call.id)
    bot.send_message(ADMIN_ID, f"Order #{oid}-এর user-কে message লিখুন।")

@bot.callback_query_handler(func=lambda c: c.data.startswith('userreply:'))
def user_reply_prompt(call):
    oid = int(call.data.split(':')[1])
    o = cur.execute('SELECT * FROM orders WHERE id=? AND user_id=?', (oid, call.from_user.id)).fetchone()
    if not o:
        bot.answer_callback_query(call.id, 'Order পাওয়া যায়নি।', show_alert=True); return
    states[call.from_user.id] = {'step': 'user_reply', 'order_id': oid}
    bot.answer_callback_query(call.id)
    bot.send_message(call.from_user.id, 'Admin-কে আপনার message লিখুন:')

@bot.message_handler(func=lambda m: m.from_user.id in states, content_types=['text','photo','document'])
def handle_state(message):
    uid = message.from_user.id
    if (message.text or '').split(maxsplit=1)[0] == '/start':
        states.pop(uid, None); return start(message)
    s = states.get(uid, {}); step = s.get('step')
    if (message.text or '').strip() == '❌ CANCEL DEPOSIT' and step in ('deposit_amount', 'deposit_method', 'deposit_screenshot'):
        states.pop(uid, None)
        bot.send_message(uid, '❌ Deposit process canceled.', reply_markup=main_menu(uid))
        return
    if step == 'deposit_amount':
        try:
            amount = float((message.text or '').strip())
            if amount <= 0 or amount > 10000000: raise ValueError()
        except Exception:
            bot.reply_to(message, 'সঠিক amount লিখুন। উদাহরণ: 100'); return
        states[uid] = {'step': 'deposit_method', 'amount': amount}
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton('NAGAD', callback_data='dep_method:NAGAD'),
               types.InlineKeyboardButton('BKASH', callback_data='dep_method:BKASH'))
        bot.send_message(uid, f'আপনার deposit amount: ৳{money(amount)}\nপেমেন্ট method নির্বাচন করুন:', reply_markup=kb)
        return
    if step == 'deposit_screenshot':
        if not message.photo:
            bot.reply_to(message, 'দয়া করে Send Money-এর screenshot ছবি হিসেবে পাঠান।'); return
        amount = float(s['amount']); method = s['method']; photo_id = message.photo[-1].file_id
        cur.execute('INSERT INTO deposits(user_id,amount,method,screenshot_file_id,status,created_at) VALUES(?,?,?,?,?,?)',
                    (uid, amount, method, photo_id, 'PENDING', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        dep_id = cur.lastrowid; conn.commit(); states.pop(uid, None)
        bot.send_message(uid, '✅ DEPOSIT DETAILS SUCCESSFULLY SENT TO ADMIN. PLEASE WAIT SOME TIME.', reply_markup=main_menu(uid))
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton('✅ CONFIRM', callback_data=f'depact:confirm:{dep_id}'),
               types.InlineKeyboardButton('❌ CANCEL', callback_data=f'depact:cancel:{dep_id}'))
        caption = (f'💳 <b>NEW DEPOSIT #{dep_id}</b>\nUser ID: <code>{uid}</code>\n'
                   f'Amount: ৳{money(amount)}\nMethod: {method}\nStatus: PENDING\n'
                   f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        try: bot.send_photo(ADMIN_ID, photo_id, caption=caption, reply_markup=kb)
        except Exception as e:
            bot.send_message(ADMIN_ID, caption + '\n⚠️ Screenshot could not be forwarded automatically.')
        return
    if step == 'admin_message' and is_admin(uid):
        o = cur.execute('SELECT * FROM orders WHERE id=?', (s['order_id'],)).fetchone()
        if o:
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('💬 CLICK TO REPLY', callback_data=f"userreply:{o['id']}"))
            try: bot.send_message(o['user_id'], f"📩 <b>Message from AS SHOP Admin (Order #{o['id']})</b>\n\n{message.text or '[media message]'}", reply_markup=kb)
            except Exception: bot.send_message(ADMIN_ID, 'User-কে message পাঠানো যায়নি।')
            bot.send_message(ADMIN_ID, 'Message পাঠানো হয়েছে।')
        states.pop(uid, None); return
    if step == 'user_reply':
        o = cur.execute('SELECT * FROM orders WHERE id=? AND user_id=?', (s['order_id'], uid)).fetchone()
        if o:
            bot.send_message(ADMIN_ID, f"💬 <b>User reply — Order #{o['id']}</b>\nUser ID: <code>{uid}</code>\n\n{message.text or '[media message]'}")
            bot.send_message(uid, '✅ আপনার message admin-কে পাঠানো হয়েছে।')
        states.pop(uid, None); return
    if step == 'order_info':
        info=(message.text or '').strip()
        if not info:
            bot.reply_to(message,'এই তথ্য না দিলে order confirm হবে না।'); return
        states[uid]={**s,'step':'order_confirm','customer_info':info}
        kb=types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton('✅ CONFIRM ORDER',callback_data='userorderconfirm:yes'),types.InlineKeyboardButton('❌ CANCEL',callback_data='userorderconfirm:no'))
        bot.send_message(uid,f"🧾 <b>CONFIRM YOUR ORDER</b>\nProduct: {s['product_name']}\nPrice: ৳{money(s['price'])}\nYour Info: {info}",reply_markup=kb); return
    if step == 'redeem_enter':
        code=(message.text or '').strip().upper(); states.pop(uid,None); process_redeem(uid,code); return
    if step == 'set_order_prompt' and is_admin(uid):
        text=(message.text or '').strip()
        if not text: bot.reply_to(message,'Text খালি রাখা যাবে না।'); return
        set_setting('order_info_prompt',text); states.pop(uid,None); bot.send_message(uid,'✅ Order last text updated.',reply_markup=admin_menu()); return
    if step == 'maintenance_text' and is_admin(uid):
        text=(message.text or '').strip()
        if not text: bot.reply_to(message,'Maintenance text লিখুন।'); return
        set_setting('maintenance_text',text); states.pop(uid,None); bot.send_message(uid,'✅ Maintenance text saved.',reply_markup=admin_menu()); return
    if step == 'redeem_users' and is_admin(uid):
        try: n=int((message.text or '').strip()); assert n>0
        except Exception: bot.reply_to(message,'কতজন user redeem করতে পারবে number দিন।'); return
        states[uid]={'step':'redeem_points','max_users':n}; bot.send_message(uid,'প্রতি user কত point পাবে?'); return
    if step == 'redeem_points' and is_admin(uid):
        try: pts=float((message.text or '').strip()); assert pts>0
        except Exception: bot.reply_to(message,'সঠিক point দিন।'); return
        states[uid]={'step':'redeem_channel','max_users':s['max_users'],'points':pts}
        kb=types.ReplyKeyboardMarkup(resize_keyboard=True,one_time_keyboard=True).add('⏭ NO CHANNEL')
        bot.send_message(uid,'Redeem-এর জন্য channel join লাগবে? Channel username/link দিন, অথবা ⏭ NO CHANNEL চাপুন।',reply_markup=kb); return
    if step == 'redeem_channel' and is_admin(uid):
        raw=(message.text or '').strip(); channel_id=channel_link=channel_title=''
        if raw != '⏭ NO CHANNEL':
            try:
                ref=raw
                if 't.me/' in raw:
                    tail=raw.split('t.me/',1)[1].strip('/')
                    if not tail.startswith('+') and not tail.startswith('joinchat'): ref='@'+tail.split('/')[0]
                ch=bot.get_chat(ref); channel_id=str(ch.id); channel_title=ch.title or 'Channel'; channel_link=raw
            except Exception:
                bot.reply_to(message,'❌ Channel verify হয়নি। Public channel username/link দিন এবং bot-কে admin করুন, অথবা ⏭ NO CHANNEL চাপুন।'); return
        code=''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(10))
        cur.execute('INSERT INTO redeem_codes(code,max_users,points,channel_id,channel_link,channel_title,created_at) VALUES(?,?,?,?,?,?,?)',
                    (code,s['max_users'],s['points'],channel_id,channel_link,channel_title,datetime.now().strftime('%Y-%m-%d %H:%M:%S'))); conn.commit(); states.pop(uid,None)
        me=bot.get_me(); link=f"https://t.me/{me.username}?start=redeem_{code}"
        bot.send_message(uid,f"✅ <b>REDEEM CREATED</b>\nCode: <code>{code}</code>\nUsers: {s['max_users']}\nPoint: {money(s['points'])}\nLink: <code>{link}</code>",reply_markup=admin_menu()); return
    if step == 'offer_photo' and is_admin(uid):
        photo=None
        if message.photo: photo=message.photo[-1].file_id
        elif message.document and (message.document.mime_type or '').startswith('image/'):
            photo=message.document.file_id
        elif (message.text or '').strip()!='⏭ SKIP PHOTO':
            bot.reply_to(message,'Photo পাঠান অথবা ⏭ SKIP PHOTO চাপুন।'); return
        states[uid]={'step':'offer_name','photo':photo}
        bot.send_message(uid,'Offer product name লিখুন:',reply_markup=types.ReplyKeyboardRemove()); return
    if step == 'offer_name' and is_admin(uid):
        name=(message.text or '').strip()
        if not name: bot.reply_to(message,'Product name required.'); return
        states[uid]={'step':'offer_desc','photo':s['photo'],'name':name}; bot.send_message(uid,'Offer product-এর text/description লিখুন:'); return
    if step == 'offer_desc' and is_admin(uid):
        desc=(message.text or '').strip()
        if not desc: bot.reply_to(message,'Text required.'); return
        states[uid]={'step':'offer_price','photo':s['photo'],'name':s['name'],'description':desc}; bot.send_message(uid,'Price কত?'); return
    if step == 'offer_price' and is_admin(uid):
        try: price=float((message.text or '').strip()); assert price>=0
        except Exception: bot.reply_to(message,'সঠিক price দিন।'); return
        states[uid]={'step':'offer_stock','photo':s['photo'],'name':s['name'],'description':s['description'],'price':price}; bot.send_message(uid,'কয়টা stock রাখবেন?'); return
    if step == 'offer_stock' and is_admin(uid):
        try: stock=int((message.text or '').strip()); assert stock>=0
        except Exception: bot.reply_to(message,'সঠিক stock number দিন।'); return
        cur.execute('INSERT INTO offer_products(name,photo_file_id,description,price,stock) VALUES(?,?,?,?,?)',(s['name'],s['photo'],s['description'],s['price'],stock)); conn.commit(); states.pop(uid,None)
        bot.send_message(uid,'✅ Offer product added successfully!',reply_markup=admin_menu()); return
    # Admin setup flows
    if not is_admin(uid): return
    if step == 'add_channel_link':
        link = (message.text or '').strip()
        try:
            chat_ref = link
            if 't.me/' in link:
                tail = link.split('t.me/',1)[1].strip('/')
                if not tail.startswith('+') and not tail.startswith('joinchat'): chat_ref = '@' + tail.split('/')[0]
            ch = bot.get_chat(chat_ref)
            cur.execute('INSERT INTO channels(chat_id,link,title) VALUES(?,?,?)', (str(ch.id), link, ch.title or 'Channel')); conn.commit()
            bot.reply_to(message, f"✅ Channel added: {ch.title}", reply_markup=admin_menu())
        except Exception as e: bot.reply_to(message, '❌ Channel add হয়নি। Public channel username/link দিন এবং bot-কে channel-এ admin করুন।')
        states.pop(uid, None); return
    if step == 'add_money' or step == 'cut_money':
        try:
            user_id, amount = message.text.replace(',', ' ').split()[:2]; user_id=int(user_id); amount=float(amount)
            if amount <= 0: raise ValueError()
            if not get_user(user_id): bot.reply_to(message, 'এই user আগে /start দেয়নি।'); states.pop(uid,None); return
            if step == 'add_money':
                cur.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (amount,user_id))
            else:
                cur.execute('UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=?', (amount,user_id))
            conn.commit(); bal=get_user(user_id)['balance']
            bot.reply_to(message, f"✅ Updated. User {user_id} balance: ৳{money(bal)}", reply_markup=admin_menu())
            try: bot.send_message(user_id, f"💰 আপনার balance update হয়েছে। Current balance: ৳{money(bal)}")
            except Exception: pass
        except Exception: bot.reply_to(message, 'Format: USER_ID AMOUNT\nExample: 123456789 100')
        states.pop(uid, None); return
    if step == 'add_category':
        name=(message.text or '').strip()
        if not name: bot.reply_to(message, 'Category name খালি রাখা যাবে না।'); return
        try: cur.execute('INSERT INTO categories(name) VALUES(?)',(name,)); conn.commit(); bot.reply_to(message, f'✅ Category added: {name}', reply_markup=admin_menu())
        except sqlite3.IntegrityError: bot.reply_to(message, 'এই category আগে থেকেই আছে।')
        states.pop(uid,None); return
    if step == 'add_product_name':
        states[uid]={'step':'add_product_photo','category_id':s['category_id'],'name':(message.text or '').strip()}
        kb=types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add('⏭ SKIP PHOTO')
        bot.send_message(uid, 'Product photo পাঠান অথবা Skip চাপুন।', reply_markup=kb); return
    if step == 'add_product_photo':
        photo_id = None
        if message.photo:
            photo_id = message.photo[-1].file_id
        elif message.document and (message.document.mime_type or '').startswith('image/'):
            photo_id = message.document.file_id
        elif (message.text or '').strip() != '⏭ SKIP PHOTO':
            bot.reply_to(message, 'Photo পাঠান অথবা ⏭ SKIP PHOTO চাপুন।'); return
        states[uid]={'step':'add_product_description','category_id':s['category_id'],'name':s['name'],'photo':photo_id}
        bot.send_message(uid, 'Product-এর description/text লিখুন:', reply_markup=types.ReplyKeyboardRemove()); return
    if step == 'add_product_description':
        desc=(message.text or '').strip()
        if not desc: bot.reply_to(message, 'Description দিতে হবে।'); return
        states[uid]={'step':'add_product_price','category_id':s['category_id'],'name':s['name'],'photo':s['photo'],'description':desc}
        bot.send_message(uid, 'Product price কত টাকা? শুধু number দিন।'); return
    if step == 'add_product_price':
        try: price=float((message.text or '').strip()); assert price >= 0
        except Exception: bot.reply_to(message, 'সঠিক price দিন, যেমন 100'); return
        states[uid]={'step':'add_product_info_prompt','category_id':s['category_id'],'name':s['name'],'photo':s['photo'],'description':s['description'],'price':price}
        bot.send_message(uid, 'এই product order করার সময় user-এর কাছ থেকে ঠিকানা/তথ্য চাওয়ার জন্য যে text দেখাবে সেটি লিখুন:'); return
    if step == 'add_product_info_prompt':
        info_prompt=(message.text or '').strip()
        if not info_prompt: bot.reply_to(message, 'এই info text খালি রাখা যাবে না।'); return
        cur.execute('INSERT INTO products(category_id,name,photo_file_id,description,price,info_prompt) VALUES(?,?,?,?,?,?)',
                    (s['category_id'],s['name'],s['photo'],s['description'],s['price'],info_prompt)); conn.commit()
        states.pop(uid,None); bot.send_message(uid, '✅ Product added successfully!', reply_markup=admin_menu()); return
    if step == 'broadcast':
        users=cur.execute('SELECT user_id FROM users').fetchall(); sent=0
        for u in users:
            try:
                if message.text: bot.send_message(u['user_id'], message.text)
                elif message.photo: bot.send_photo(u['user_id'], message.photo[-1].file_id, caption=message.caption or '')
                elif message.document: bot.send_document(u['user_id'], message.document.file_id, caption=message.caption or '')
                elif message.video: bot.send_video(u['user_id'], message.video.file_id, caption=message.caption or '')
                sent += 1
            except Exception: pass
        states.pop(uid,None); bot.send_message(uid, f'📢 Broadcast done. Sent: {sent}/{len(users)}', reply_markup=admin_menu()); return
    if step == 'remove_channel_select': return
    if step == 'cut_category_select': return
    if step == 'cut_product_select': return

@bot.message_handler(func=lambda m: True, content_types=['text','photo','document','video'])
def menu_handler(message):
    uid=message.from_user.id; txt=(message.text or '').strip()
    if txt == '/start': return
    if txt == '/admin': return
    if maintenance_on() and not is_admin(uid):
        bot.send_message(uid, maintenance_text(), reply_markup=types.ReplyKeyboardRemove()); return
    if txt == '⬅️ USER PANEL':
        if is_admin(uid): user_panel(message)
        return
    if txt == '👤 PROFILE':
        if not joined(uid): join_prompt(uid); return
        u=get_user(uid)
        if not u: add_user(message.from_user); u=get_user(uid)
        bot.send_message(uid, f"👤 <b>YOUR PROFILE</b>\n🆔 ID: <code>{uid}</code>\n💰 Balance: ৳{money(u['balance'])}\n🎟 Points: {money(u['points'] or 0)}\n👥 Total Referrals: {u['referrals']}\n✅ Successful Orders: {u['successful_orders']}", reply_markup=main_menu(uid)); return
    if txt == '🔗 REFAR':
        if not joined(uid): join_prompt(uid); return
        me=bot.get_me(); link=f"https://t.me/{me.username}?start=ref_{uid}"
        bot.send_message(uid, f"EARN 5% DEPOSIT BONUS FROM YOUR REFAR.\n\nREFAR LINK ↓\n<code>{link}</code>", reply_markup=main_menu(uid)); return
    if txt == '🛒 ORDER ITEAM':
        if not joined(uid): join_prompt(uid); return
        show_categories(uid); return
    if txt == '🎁 OFFER ITEMS':
        if not joined(uid): join_prompt(uid); return
        show_offer_items(uid); return
    if txt == '🎟 REDEEM POINT':
        if not joined(uid): join_prompt(uid); return
        states[uid]={'step':'redeem_enter'}; bot.send_message(uid,'🎟 Redeem code লিখুন:'); return
    if txt == '📊 STATUS':
        if not joined(uid): join_prompt(uid); return
        users=cur.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
        completed=cur.execute("SELECT COUNT(*) n FROM orders WHERE status='CONFIRMED'").fetchone()['n']
        bot.send_message(uid, f"📊 <b>AS SHOP STATUS</b>\n👥 Total Users: {users}\n✅ Total Completed Orders: {completed}", reply_markup=main_menu(uid)); return
    if txt == '💳 DEPOSIT':
        if not joined(uid): join_prompt(uid); return
        states[uid]={'step':'deposit_amount'}
        cancel_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_kb.add('❌ CANCEL DEPOSIT')
        bot.send_message(uid, 'ENTER THE AMOUNT YOU WANT TO DEPOSIT (টাকার পরিমাণ লিখুন):', reply_markup=cancel_kb); return
    if txt == '🧾 DEPOSIT HISTORY':
        if not joined(uid): join_prompt(uid); return
        rows=cur.execute('SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 30',(uid,)).fetchall()
        if not rows: bot.send_message(uid, 'আপনার কোনো deposit history নেই।', reply_markup=main_menu(uid)); return
        lines=['🧾 <b>YOUR DEPOSIT HISTORY</b>']
        for d in rows:
            lines.append(f"\n#{d['id']} — ৳{money(d['amount'])} — {d['method']} — <b>{d['status']}</b> — {d['created_at']}")
        bot.send_message(uid, '\n'.join(lines))
        bot.send_message(uid, 'Menu:', reply_markup=main_menu(uid)); return
    if txt == '🆘 SUPPORT':
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton('CLICK HERE TO CONTACT', url='https://t.me/massageakatsukiceo_bot'))
        bot.send_message(uid, '🆘 <b>AS SHOP SUPPORT</b>\nContact support using the button below.', reply_markup=kb); return
    if not is_admin(uid): return
    if txt == '➕ ADD CHANNEL': states[uid]={'step':'add_channel_link'}; bot.send_message(uid, 'Channel link/username দিন (bot-কে channel admin করুন):'); return
    if txt == '➖ REMOVE CHANNEL':
        rows=cur.execute('SELECT * FROM channels').fetchall()
        if not rows: bot.send_message(uid,'কোনো channel যোগ করা নেই।'); return
        kb=types.InlineKeyboardMarkup()
        for r in rows: kb.add(types.InlineKeyboardButton('❌ '+(r['title'] or r['link']), callback_data=f"delch:{r['id']}"))
        bot.send_message(uid,'যে channel remove করবেন সেটি বাছুন:',reply_markup=kb); return
    if txt == '💰 ADD MONEY': states[uid]={'step':'add_money'}; bot.send_message(uid,'User chat ID এবং amount দিন。\nFormat: USER_ID AMOUNT\nExample: 123456789 100'); return
    if txt == '✂️ CUT MONEY': states[uid]={'step':'cut_money'}; bot.send_message(uid,'User chat ID এবং amount দিন。\nFormat: USER_ID AMOUNT\nExample: 123456789 50'); return
    if txt == '📂 ADD CATEGORY': states[uid]={'step':'add_category'}; bot.send_message(uid,'নতুন category name লিখুন:'); return
    if txt == '🗑 CUT CATEGORY':
        rows=cur.execute('SELECT * FROM categories').fetchall()
        if not rows: bot.send_message(uid,'কোনো category নেই।'); return
        kb=types.InlineKeyboardMarkup()
        for r in rows: kb.add(types.InlineKeyboardButton('❌ '+r['name'],callback_data=f'delcat:{r["id"]}'))
        bot.send_message(uid,'Remove করার category বাছুন:',reply_markup=kb); return
    if txt == '➕ ADD PRODUCT':
        rows=cur.execute('SELECT * FROM categories ORDER BY name').fetchall()
        if not rows: bot.send_message(uid,'আগে একটি category add করুন।'); return
        kb=types.InlineKeyboardMarkup()
        for r in rows: kb.add(types.InlineKeyboardButton(r['name'],callback_data=f'addprodcat:{r["id"]}'))
        bot.send_message(uid,'যে category-তে product add করবেন সেটি select করুন:',reply_markup=kb); return
    if txt == '🎁 ADD OFFER':
        states[uid]={'step':'offer_photo'}; kb=types.ReplyKeyboardMarkup(resize_keyboard=True,one_time_keyboard=True).add('⏭ SKIP PHOTO'); bot.send_message(uid,'Offer product PHOTO পাঠান (optional), অথবা Skip চাপুন:',reply_markup=kb); return
    if txt == '🗑 REMOVE OFFER':
        rows=cur.execute('SELECT * FROM offer_products WHERE active=1 ORDER BY id DESC').fetchall()
        if not rows: bot.send_message(uid,'কোনো active offer নেই।'); return
        kb=types.InlineKeyboardMarkup()
        for r in rows: kb.add(types.InlineKeyboardButton(f"❌ {r['name']} — ৳{money(r['price'])}",callback_data=f'deloffer:{r["id"]}'))
        bot.send_message(uid,'Remove করার offer বাছুন:',reply_markup=kb); return
    if txt == '🎟 REDEEM CREATE':
        states[uid]={'step':'redeem_users'}; bot.send_message(uid,'কতজন user এই redeem ব্যবহার করতে পারবে?'); return
    if txt == '🛠 MAINTENANCE':
        kb=types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton('🟢 ON',callback_data='maint:on'),types.InlineKeyboardButton('🔴 OFF',callback_data='maint:off'))
        kb.add(types.InlineKeyboardButton('✏️ SET TEXT',callback_data='maint:text'))
        status='ON' if maintenance_on() else 'OFF'; bot.send_message(uid,f'🛠 Maintenance: <b>{status}</b>\nText: {maintenance_text()}',reply_markup=kb); return
    if txt == '🗑 CUT PRODUCTS':
        rows=cur.execute('SELECT * FROM products WHERE active=1 ORDER BY id DESC').fetchall()
        if not rows: bot.send_message(uid,'কোনো active product নেই।'); return
        kb=types.InlineKeyboardMarkup()
        for r in rows: kb.add(types.InlineKeyboardButton(f"❌ {r['name']} — ৳{money(r['price'])}",callback_data=f'delprod:{r["id"]}'))
        bot.send_message(uid,'Remove করার product বাছুন:',reply_markup=kb); return
    if txt == '📋 ORDER LIST':
        kb=types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton('🆕 NEW ORDER',callback_data='orders:NEW'),types.InlineKeyboardButton('✅ CONFIRM ORDER',callback_data='orders:CONFIRMED'),types.InlineKeyboardButton('💸 REFUND ORDER',callback_data='orders:REFUNDED'),types.InlineKeyboardButton('❌ CANCEL ORDER',callback_data='orders:CANCELED'))
        bot.send_message(uid,'📋 Order list:',reply_markup=kb); return
    if txt == '📢 BROADCAST': states[uid]={'step':'broadcast'}; bot.send_message(uid,'সব user-কে পাঠানোর text/photo/document/video পাঠান:'); return

@bot.callback_query_handler(func=lambda c: c.data.startswith('maint:'))
def maintenance_cb(call):
    if not is_admin(call.from_user.id): return
    action=call.data.split(':')[1]
    if action=='on': set_setting('maintenance','1'); bot.answer_callback_query(call.id,'Maintenance ON')
    elif action=='off': set_setting('maintenance','0'); bot.answer_callback_query(call.id,'Maintenance OFF')
    else:
        states[ADMIN_ID]={'step':'maintenance_text'}; bot.answer_callback_query(call.id); bot.send_message(ADMIN_ID,'Maintenance-এর text লিখুন:')

@bot.callback_query_handler(func=lambda c: c.data.startswith('dep_method:'))
def deposit_method_cb(call):
    uid = call.from_user.id
    s = states.get(uid, {})
    if s.get('step') != 'deposit_method':
        bot.answer_callback_query(call.id, 'এই deposit session শেষ হয়েছে।', show_alert=True); return
    method = call.data.split(':',1)[1]
    states[uid] = {'step':'deposit_screenshot', 'amount':s['amount'], 'method':method}
    bot.answer_callback_query(call.id)
    cancel_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    cancel_kb.add('❌ CANCEL DEPOSIT')
    bot.send_message(uid, f'💳 {method} Send Money Number: <code>01326928894</code>\n\nটাকা পাঠিয়ে স্ক্রিনশট দিন (শুধু Send Money)।', parse_mode='HTML', reply_markup=cancel_kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('depact:'))
def deposit_action(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, 'Admin only.', show_alert=True); return
    _, action, dep_s = call.data.split(':'); dep_id = int(dep_s)
    d = cur.execute('SELECT * FROM deposits WHERE id=?', (dep_id,)).fetchone()
    if not d:
        bot.answer_callback_query(call.id, 'Deposit পাওয়া যায়নি।', show_alert=True); return
    if d['status'] != 'PENDING':
        bot.answer_callback_query(call.id, 'এই deposit আগে process করা হয়েছে।', show_alert=True); return
    if action == 'confirm':
        cur.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (d['amount'], d['user_id']))
        ref_user = get_user(d['user_id'])
        commission = 0.0
        referrer = ref_user['referred_by'] if ref_user else None
        if referrer:
            commission = round(float(d['amount']) * 0.05, 2)
            if commission > 0:
                cur.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (commission, referrer))
        cur.execute("UPDATE deposits SET status='CONFIRMED', commission_paid=? WHERE id=?", (commission, dep_id))
        conn.commit()
        try: bot.send_message(d['user_id'], f'✅ DEPOSIT MONEY ADDED: ৳{money(d["amount"])}')
        except Exception: pass
        if referrer and commission > 0:
            try: bot.send_message(referrer, f'🎉 YOU GOT 5% COMMISSION FROM YOUR REFERRAL USER’S DEPOSIT: ৳{money(commission)}')
            except Exception: pass
        bot.answer_callback_query(call.id, 'Deposit confirmed and balance updated.')
        suffix = f'\nReferral commission: ৳{money(commission)}' if commission else ''
        try: bot.edit_message_caption((call.message.caption or '') + f'\n\n✅ CONFIRMED{suffix}', call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='HTML')
        except Exception: pass
    elif action == 'cancel':
        cur.execute("UPDATE deposits SET status='CANCELED' WHERE id=?", (dep_id,)); conn.commit()
        try: bot.send_message(d['user_id'], f'❌ DEPOSIT CANCELED: ৳{money(d["amount"])}')
        except Exception: pass
        bot.answer_callback_query(call.id, 'Deposit canceled.')
        try: bot.edit_message_caption((call.message.caption or '') + '\n\n❌ CANCELED', call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='HTML')
        except Exception: pass
    else:
        bot.answer_callback_query(call.id, 'Invalid action.', show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith('delch:'))
def del_channel(call):
    if not is_admin(call.from_user.id): return
    cid=int(call.data.split(':')[1]); cur.execute('DELETE FROM channels WHERE id=?',(cid,)); conn.commit()
    bot.answer_callback_query(call.id,'Channel removed'); bot.edit_message_text('✅ Channel removed.',call.message.chat.id,call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith('delcat:'))
def del_category(call):
    if not is_admin(call.from_user.id): return
    cid=int(call.data.split(':')[1]); cur.execute('DELETE FROM categories WHERE id=?',(cid,)); conn.commit()
    bot.answer_callback_query(call.id,'Category removed'); bot.edit_message_text('✅ Category removed.',call.message.chat.id,call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith('addprodcat:'))
def add_product_category(call):
    if not is_admin(call.from_user.id): return
    cid=int(call.data.split(':')[1]); states[call.from_user.id]={'step':'add_product_name','category_id':cid}
    bot.answer_callback_query(call.id); bot.send_message(ADMIN_ID,'Product name লিখুন (এটি required):')

@bot.callback_query_handler(func=lambda c: c.data.startswith('delprod:'))
def delete_product(call):
    if not is_admin(call.from_user.id): return
    pid=int(call.data.split(':')[1]); cur.execute('UPDATE products SET active=0 WHERE id=?',(pid,)); conn.commit()
    bot.answer_callback_query(call.id,'Product removed'); bot.edit_message_text('✅ Product removed from shop.',call.message.chat.id,call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith('deloffer:'))
def delete_offer(call):
    if not is_admin(call.from_user.id): return
    oid=int(call.data.split(':')[1]); cur.execute('UPDATE offer_products SET active=0 WHERE id=?',(oid,)); conn.commit()
    bot.answer_callback_query(call.id,'Offer removed'); bot.edit_message_text('✅ Offer removed from shop.',call.message.chat.id,call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith('orders:'))
def orders_by_status(call):
    if not is_admin(call.from_user.id): return
    status=call.data.split(':')[1]
    rows=cur.execute('SELECT id FROM orders WHERE status=? ORDER BY id DESC LIMIT 30',(status,)).fetchall()
    bot.answer_callback_query(call.id)
    if not rows: bot.send_message(ADMIN_ID,'এই status-এ কোনো order নেই।'); return
    for r in rows: order_card(r['id'])

print('AS SHOP bot is running...')
bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)