import os,re,sqlite3,telebot
from datetime import datetime
from zoneinfo import ZoneInfo
from telebot import types

BOT_TOKEN=os.getenv('BOT_TOKEN','8899751346:AAG1fgKqHlZmiM3PDJpMTGmzUik8z7ZvGdg')
ADMIN_ID=7079833447
DB='refar_file_bot.db'
bot=telebot.TeleBot(BOT_TOKEN,parse_mode='HTML')
db=sqlite3.connect(DB,check_same_thread=False)
db.execute('PRAGMA journal_mode=WAL')

db.executescript('''
CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,balance INTEGER DEFAULT 0,referred_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS refs(id INTEGER PRIMARY KEY AUTOINCREMENT,referrer INTEGER,referred INTEGER UNIQUE,coins INTEGER);
CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,price INTEGER,file_type TEXT,file_id TEXT);
CREATE TABLE IF NOT EXISTS channels(id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id TEXT UNIQUE,title TEXT,link TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,file_id INTEGER,file_name TEXT,price INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
INSERT OR IGNORE INTO settings(key,value) VALUES('ref_bonus','1');
''')
db.commit()
states={}

def admin(uid): return uid==ADMIN_ID
def setting(k,d=''):
    r=db.execute('SELECT value FROM settings WHERE key=?',(k,)).fetchone(); return r[0] if r else d
def set_setting(k,v):
    db.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)));db.commit()
def user(u):
    db.execute('INSERT INTO users(user_id,username,first_name) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name',(u.id,u.username or '',u.first_name or ''));db.commit()
def balance(uid):
    r=db.execute('SELECT balance FROM users WHERE user_id=?',(uid,)).fetchone();return r[0] if r else 0
def coins(uid,n): db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(n,uid));db.commit()
def refcount(uid): return db.execute('SELECT COUNT(*) FROM refs WHERE referrer=?',(uid,)).fetchone()[0]
def force_ok(uid):
    for cid,title,link in db.execute('SELECT chat_id,title,link FROM channels').fetchall():
        try:
            m=bot.get_chat_member(cid,uid)
            if m.status in ('left','kicked') or (m.status=='restricted' and not m.is_member): return False
        except Exception:return False
    return True
def force_msg(chat):
    kb=types.InlineKeyboardMarkup()
    for cid,title,link in db.execute('SELECT id,title,link FROM channels').fetchall(): kb.add(types.InlineKeyboardButton('📢 '+title,url=link))
    kb.add(types.InlineKeyboardButton('✅ CHECK JOIN',callback_data='joincheck'))
    bot.send_message(chat,'⚠️ <b>JOIN REQUIRED</b>\n\nপ্রথমে সব required channel-এ join করুন।',reply_markup=kb)
def main_kb():
    k=types.ReplyKeyboardMarkup(resize_keyboard=True);k.row('👤 PROFILE','🎟️ REFAR');k.row('📁 GET FILE','📊 STATUS');k.row('💰 BUY COIN');k.row('📢 UPDATE CHANNEL');return k
def admin_kb():
    k=types.ReplyKeyboardMarkup(resize_keyboard=True);k.row('➕ ADD CHANNEL','➖ REMOVE CHANNEL');k.row('🎁 ADD REFAR BONUS');k.row('💰 ADD COIN','✂️ CUT COIN');k.row('📁 ADD FILE','🗑️ CUT FILE');k.row('📢 BROADCAST');k.row('⚙️ SET UPDATE/LOG CHANNEL');k.row('🔙 USER PANEL');return k

def panel(chat):bot.send_message(chat,'🏠 <b>USER PANEL</b>\n\nChoose an option:',reply_markup=main_kb())

@bot.message_handler(commands=['start'])
def start(m):
    user(m.from_user)
    if len(m.text.split())>1:
        x=m.text.split()[1]
        if x.startswith('ref_'):
            try:
                rid=int(x[4:])
                if rid!=m.from_user.id and db.execute('SELECT 1 FROM users WHERE user_id=?',(rid,)).fetchone() and not db.execute('SELECT 1 FROM refs WHERE referred=?',(m.from_user.id,)).fetchone():
                    b=int(setting('ref_bonus','1'));db.execute('UPDATE users SET referred_by=? WHERE user_id=?',(rid,m.from_user.id));db.execute('INSERT INTO refs(referrer,referred,coins) VALUES(?,?,?)',(rid,m.from_user.id,b));coins(rid,b)
                    try:
                        bot.send_message(rid,'🎉 <b>CONGRATULATIONS YOU GOT NEW REFAR!</b>')
                    except Exception: pass
            except Exception:pass
    if not force_ok(m.from_user.id): force_msg(m.chat.id);return
    panel(m.chat.id)

@bot.message_handler(commands=['admin'])
def adm(m):
    if admin(m.from_user.id):bot.send_message(m.chat.id,'🛡️ <b>ADMIN PANEL</b>',reply_markup=admin_kb())
    else:bot.reply_to(m,'❌ Not authorized.')

@bot.callback_query_handler(func=lambda c:c.data=='joincheck')
def joincheck(c):
    if force_ok(c.from_user.id): bot.answer_callback_query(c.id,'Join verified!');panel(c.message.chat.id)
    else:bot.answer_callback_query(c.id,'Join all channels first.',show_alert=True)

@bot.message_handler(func=lambda m:m.text=='📢 UPDATE CHANNEL')
def update_channel(m):
    if not force_ok(m.from_user.id): force_msg(m.chat.id); return
    link=setting('update_channel_link','')
    if link:
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton('📢 OPEN UPDATE CHANNEL',url=link))
        bot.send_message(m.chat.id,'📢 <b>UPDATE CHANNEL</b>\n\nসকল আপডেট ও লগ দেখতে নিচের বাটনে ক্লিক করুন।',reply_markup=kb)
    else:
        bot.send_message(m.chat.id,'⚠️ Update channel এখনো সেট করা হয়নি।')

@bot.message_handler(func=lambda m:admin(m.from_user.id) and m.text=='⚙️ SET UPDATE/LOG CHANNEL')
def set_log_channel(m):
    states[m.from_user.id]=['logchannel']
    bot.send_message(m.chat.id,'Update/log channel-এর @username অথবা public link পাঠান। Bot-কে channel-এ admin করে post করার permission দিন।')

@bot.message_handler(func=lambda m:m.text=='👤 PROFILE')
def profile(m):
    if not force_ok(m.from_user.id):force_msg(m.chat.id);return
    bot.send_message(m.chat.id,f'👤 <b>PROFILE</b>\n════════════════\n🆔 <code>{m.from_user.id}</code>\n💰 Balance: <b>{balance(m.from_user.id)} COIN</b>\n👥 Total Refar: <b>{refcount(m.from_user.id)}</b>')

@bot.message_handler(func=lambda m:m.text=='🎟️ REFAR')
def refer(m):
    if not force_ok(m.from_user.id):force_msg(m.chat.id);return
    me=bot.get_me();link=f'https://t.me/{me.username}?start=ref_{m.from_user.id}';b=setting('ref_bonus','1')
    bot.send_message(m.chat.id,f'🎟️ <b>REFAR AND EARN COIN</b>\n\n💰 <b>PER REFAR {b} COIN</b>\n\nYOUR REFAR LINK ↓\n<code>{link}</code>')

@bot.message_handler(func=lambda m:m.text=='📁 GET FILE')
def getfiles(m):
    if not force_ok(m.from_user.id):force_msg(m.chat.id);return
    rows=db.execute('SELECT id,name,price FROM files ORDER BY id DESC').fetchall();kb=types.InlineKeyboardMarkup()
    for fid,n,p in rows:kb.add(types.InlineKeyboardButton(f'📄 {n} — {p} COIN',callback_data=f'buy:{fid}'))
    bot.send_message(m.chat.id,'📁 <b>GET FILE</b>\n\n'+('Select a file:' if rows else 'No file available.'),reply_markup=kb if rows else None)

@bot.callback_query_handler(func=lambda c:c.data.startswith('buy:'))
def buy(c):
    if not force_ok(c.from_user.id):bot.answer_callback_query(c.id,'Join required channels first.',show_alert=True);return
    fid=int(c.data.split(':')[1]);r=db.execute('SELECT name,price,file_type,file_id FROM files WHERE id=?',(fid,)).fetchone()
    if not r:bot.answer_callback_query(c.id,'File not found.',show_alert=True);return
    name,p,ft,fileid=r
    if balance(c.from_user.id)<p:bot.answer_callback_query(c.id,f'Need {p} COIN.',show_alert=True);return
    coins(c.from_user.id,-p)
    try:
        cap=f'✅ <b>FILE PURCHASED</b>\n\n📄 {name}\n💰 Price: {p} COIN'
        if ft=='document':bot.send_document(c.message.chat.id,fileid,caption=cap)
        elif ft=='video':bot.send_video(c.message.chat.id,fileid,caption=cap)
        elif ft=='photo':bot.send_photo(c.message.chat.id,fileid,caption=cap)
        elif ft=='audio':bot.send_audio(c.message.chat.id,fileid,caption=cap)
        # Record purchase and send a log to the configured update channel.
        db.execute('INSERT INTO purchases(user_id,file_id,file_name,price) VALUES(?,?,?,?)',
                   (c.from_user.id,fid,name,p)); db.commit()
        order_id=db.execute('SELECT last_insert_rowid()').fetchone()[0]
        now=datetime.now(ZoneInfo('Asia/Dhaka')).strftime('%d-%m-%Y %I:%M:%S %p')
        uname='@'+c.from_user.username if c.from_user.username else 'No username'
        log_channel=setting('update_channel_id','')
        if log_channel:
            try:
                bot.send_message(int(log_channel),
                    f'🎉 <b>NEW FILE SUCCESSFULLY REDEEMED ✅</b>\n\n'
                    f'🤖 <b>FILE INFORMATION</b>\n\n'
                    f'NAME: {name}\nORDER ID: {order_id}\nCOIN PRICE: {p} COIN\nTIME: {now}\n\n'
                    f'👤 <b>CLIENT INFO</b>\n\nUsername: {uname}\nID: <code>{c.from_user.id}</code>\n\n'
                    f'STATUS: SUCCESSFUL ✅\n\nBOT = @asfileshare404_bot')
            except Exception: pass
        bot.answer_callback_query(c.id,'Purchase successful!')
    except Exception:
        coins(c.from_user.id,p);bot.answer_callback_query(c.id,'Send failed. Coin refunded.',show_alert=True)

@bot.message_handler(func=lambda m:m.text=='📊 STATUS')
def status(m):
    if not force_ok(m.from_user.id):force_msg(m.chat.id);return
    u=db.execute('SELECT COUNT(*) FROM users').fetchone()[0];f=db.execute('SELECT COUNT(*) FROM files').fetchone()[0]
    bot.send_message(m.chat.id,f'📊 <b>STATUS</b>\n\n👥 Total Users: <b>{u}</b>\n📁 Total Files: <b>{f}</b>')

@bot.message_handler(func=lambda m:m.text=='💰 BUY COIN')
def buycoin(m):
    if not force_ok(m.from_user.id):force_msg(m.chat.id);return
    bot.send_message(m.chat.id,'💰 <b>BUY COIN</b>\n\nCLICK HERE TO BUY COIN\n@AS_ITACHI2026')

@bot.message_handler(func=lambda m:admin(m.from_user.id) and m.text=='➕ ADD CHANNEL')
def ac(m):states[m.from_user.id]=['channel'];bot.send_message(m.chat.id,'Send channel username/link. Example: @mychannel or https://t.me/mychannel')

@bot.message_handler(func=lambda m:admin(m.from_user.id) and m.text=='➖ REMOVE CHANNEL')
def rc(m):
    rows=db.execute('SELECT id,title FROM channels').fetchall();kb=types.InlineKeyboardMarkup()
    for i,t in rows:kb.add(types.InlineKeyboardButton('🗑️ '+t,callback_data=f'delch:{i}'))
    bot.send_message(m.chat.id,'Select channel to remove:',reply_markup=kb if rows else None)

@bot.callback_query_handler(func=lambda c:c.data.startswith('delch:'))
def delch(c):
    if not admin(c.from_user.id):return
    db.execute('DELETE FROM channels WHERE id=?',(int(c.data.split(':')[1]),));db.commit();bot.answer_callback_query(c.id,'Removed.');bot.edit_message_text('✅ Channel removed.',c.message.chat.id,c.message.message_id)

@bot.message_handler(func=lambda m:admin(m.from_user.id) and m.text=='🎁 ADD REFAR BONUS')
def arb(m):states[m.from_user.id]=['bonus'];bot.send_message(m.chat.id,'Send PER REFAR bonus coin number:')

@bot.message_handler(func=lambda m:admin(m.from_user.id) and m.text in ('💰 ADD COIN','✂️ CUT COIN'))
def coinop(m):states[m.from_user.id]=['addcoin' if m.text=='💰 ADD COIN' else 'cutcoin'];bot.send_message(m.chat.id,'Send: USER_ID | COIN')

@bot.message_handler(func=lambda m:admin(m.from_user.id) and m.text=='📁 ADD FILE')
def af(m):states[m.from_user.id]=['fname'];bot.send_message(m.chat.id,'Step 1: Send file name:')

@bot.message_handler(func=lambda m:admin(m.from_user.id) and m.text=='🗑️ CUT FILE')
def cf(m):
    rows=db.execute('SELECT id,name,price FROM files').fetchall();kb=types.InlineKeyboardMarkup()
    for i,n,p in rows:kb.add(types.InlineKeyboardButton(f'🗑️ {n} — {p}',callback_data=f'delf:{i}'))
    bot.send_message(m.chat.id,'Select file:',reply_markup=kb if rows else None)

@bot.callback_query_handler(func=lambda c:c.data.startswith('delf:'))
def delf(c):
    if not admin(c.from_user.id):return
    db.execute('DELETE FROM files WHERE id=?',(int(c.data.split(':')[1]),));db.commit();bot.answer_callback_query(c.id,'Deleted.');bot.edit_message_text('✅ File removed.',c.message.chat.id,c.message.message_id)

@bot.message_handler(func=lambda m:admin(m.from_user.id) and m.text=='📢 BROADCAST')
def bc(m):states[m.from_user.id]=['broadcast'];bot.send_message(m.chat.id,'Send text/photo/video/document/audio to broadcast:')

@bot.message_handler(func=lambda m:admin(m.from_user.id) and m.text=='🔙 USER PANEL')
def up(m):states.pop(m.from_user.id,None);panel(m.chat.id)

@bot.message_handler(content_types=['text','document','video','photo','audio'])
def state_handler(m):
    if not admin(m.from_user.id):return
    s=states.get(m.from_user.id)
    if not s:return
    st=s[0]
    if st=='logchannel':
        raw=(m.text or '').strip()
        x=re.search(r'(?:https?://)?t\.me/([A-Za-z0-9_]+)',raw)
        username='@'+x.group(1) if x else raw
        try:
            ch=bot.get_chat(username)
            link=raw if raw.startswith('http') else (f'https://t.me/{ch.username}' if getattr(ch,'username',None) else '')
            if not link: raise ValueError('A public channel link is required.')
            # Verify that the bot can post in this channel.
            bot.send_message(ch.id,'✅ <b>Update/log channel connected.</b>')
            set_setting('update_channel_id',str(ch.id))
            set_setting('update_channel_link',link)
            bot.send_message(m.chat.id,'✅ Update/log channel সেট হয়েছে। এখন file purchase ও referral log এখানে যাবে।')
            states.pop(m.from_user.id,None)
        except Exception:
            bot.send_message(m.chat.id,'❌ Channel সেট করা যায়নি। Public channel username/link দিন এবং bot-কে admin করে post permission দিন।')
    elif st=='channel':
        link=m.text.strip();x=re.search(r'(?:https?://)?t\.me/([A-Za-z0-9_]+)',link);username='@'+x.group(1) if x else link
        try:
            ch=bot.get_chat(username);db.execute('INSERT OR REPLACE INTO channels(chat_id,title,link) VALUES(?,?,?)',(str(ch.id),ch.title or username,link));db.commit();bot.send_message(m.chat.id,'✅ Channel added.');states.pop(m.from_user.id)
        except Exception:bot.send_message(m.chat.id,'❌ Could not add channel. Make sure bot is in the channel and the link is valid.')
    elif st=='bonus':
        try:set_setting('ref_bonus',int(m.text.strip()));bot.send_message(m.chat.id,'✅ Referral bonus updated.');states.pop(m.from_user.id)
        except:bot.send_message(m.chat.id,'❌ Send a number.')
    elif st in ('addcoin','cutcoin'):
        try:
            uid,n=[x.strip() for x in m.text.split('|')];uid=int(uid);n=int(n);n=-abs(n) if st=='cutcoin' else abs(n)
            if not db.execute('SELECT 1 FROM users WHERE user_id=?',(uid,)).fetchone():bot.send_message(m.chat.id,'❌ User not found.');return
            coins(uid,n);bot.send_message(m.chat.id,f'✅ Balance changed by <b>{n}</b>. New balance: <b>{balance(uid)}</b>');states.pop(m.from_user.id)
        except:bot.send_message(m.chat.id,'❌ Format: USER_ID | COIN')
    elif st=='fname':
        if not m.text:return
        states[m.from_user.id]=['fprice',m.text.strip()];bot.send_message(m.chat.id,'Step 2: Send file price in COIN:')
    elif st=='fprice':
        try:
            p=int(m.text.strip());states[m.from_user.id]=['fupload',s[1],p];bot.send_message(m.chat.id,'Step 3: Send the file as Telegram document (recommended).')
        except:bot.send_message(m.chat.id,'❌ Price must be a number.')
    elif st=='fupload':
        ft=None;fid=None
        if m.document:ft,fid='document',m.document.file_id
        elif m.video:ft,fid='video',m.video.file_id
        elif m.photo:ft,fid='photo',m.photo[-1].file_id
        elif m.audio:ft,fid='audio',m.audio.file_id
        if not fid:bot.send_message(m.chat.id,'❌ Send a document/file.');return
        db.execute('INSERT INTO files(name,price,file_type,file_id) VALUES(?,?,?,?)',(s[1],s[2],ft,fid));db.commit();bot.send_message(m.chat.id,f'✅ File added: <b>{s[1]}</b> — {s[2]} COIN');states.pop(m.from_user.id)
    elif st=='broadcast':
        rows=db.execute('SELECT user_id FROM users').fetchall();sent=0
        for (uid,) in rows:
            try:
                if m.text:bot.send_message(uid,m.text)
                elif m.document:bot.send_document(uid,m.document.file_id,caption=m.caption or '')
                elif m.video:bot.send_video(uid,m.video.file_id,caption=m.caption or '')
                elif m.photo:bot.send_photo(uid,m.photo[-1].file_id,caption=m.caption or '')
                elif m.audio:bot.send_audio(uid,m.audio.file_id,caption=m.caption or '')
                sent+=1
            except Exception:pass
        bot.send_message(m.chat.id,f'📢 Broadcast sent: <b>{sent}</b>');states.pop(m.from_user.id)

print('Bot is running...')
bot.infinity_polling(skip_pending=True)
