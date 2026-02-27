import asyncio
import json
import os
import logging
import sys
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from datetime import datetime, time
import sqlite3
from collections import defaultdict
# Logging Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# CONFIG
API_ID = int(os.getenv('API_ID', '30475514'))
API_HASH = os.getenv('API_HASH', '80fd530f75c492058515eb956c1d66e1')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8236006228:AAE5_axnMNh85f1wzfMd5IFI8ed12MCCZ9M')
DB_PATH = os.getenv('DB_PATH', 'user_data.db')
DEFAULT_SCHEDULE = {
    "06:00": ["☕ Uống nước ấm", "📱 Check tin tức"],
    "08:00": ["💻 Làm việc/Task 1 (2h)", "☕ Nghỉ 10p"],
    "12:30": ["🍜 Ăn trưa", "😴 Nghỉ 20p"],
    "13:30": ["💻 Task 2 (3h)", "📱 Check email"],
    "18:00": ["🍽️ Ăn tối", "📖 Đọc sách 30p"],
    "20:00": ["💻 Side project", "🎯 Review ngày"],
    "22:00": ["🛀 Tắm", "📱 No screen time"],
    "23:00": ["😴 Ngủ đúng giờ"]
}
client = TelegramClient(StringSession(), API_ID, API_HASH)
MAIN_MENU = [
    [Button.inline("📅 Hôm nay", b"today"), Button.inline("📋 Lịch cá nhân", b"list")],
    [Button.inline("➕ Thêm task", b"add_menu"), Button.inline("✅ Done", b"done_menu")],
    [Button.inline("🗑️ Xóa task", b"del_menu"), Button.inline("🔄 Reset", b"reset")],
    [Button.inline("📖 Help", b"help")]
]
HELP_TEXT = """
**🤖 Schedule Bot 24/7 - HƯỚNG DẪN**
📅 **Xem lịch:**
• `/schedule` - Lịch đầy đủ
• 📅 **Hôm nay** - Còn lại hôm nay
➕ **Thêm task:**
• `/add 09:00 Học bài`
• `/add 14:30 Ăn kem`
🗑️ **Xóa task:**
• `/del 09:00` - Xóa slot 09:00
✅ **Hoàn thành:**
• `/done 09:00`
🔄 **Reset:**
• `/reset` - Reset done list
⏰ **Bot tự nhắc đúng giờ 24/7!**
👇 **Ví dụ copy paste:**
/add 07:00 Chạy bộ /del 08:00
/done 12:30



"""
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            schedule TEXT,
            completed TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ Database OK")
def load_user_data(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT schedule, completed FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'schedule': json.loads(row[0]) if row[0] else DEFAULT_SCHEDULE,
            'completed': json.loads(row[1]) if row[1] else []
        }
    else:
        save_user_data(user_id, {'schedule': DEFAULT_SCHEDULE, 'completed': []})
        return {'schedule': DEFAULT_SCHEDULE, 'completed': []}
def save_user_data(user_id, data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, schedule, completed) 
        VALUES (?, ?, ?)
    ''', (user_id, json.dumps(data['schedule']), json.dumps(data['completed'])))
    conn.commit()
    conn.close()
@client.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.reply(HELP_TEXT, buttons=MAIN_MENU)
@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "🤖 **Schedule Bot 24/7** ✅ Railway OK!\n\n"
        "📱 Bot nhắc lịch **cá nhân 24/24**!\n"
        "📖 **/help** hoặc nhấn **Help** 👇",
        buttons=MAIN_MENU
    )
@client.on(events.CallbackQuery)
async def button_handler(event):
    data = event.data.decode()
    user_id = event.sender_id
    
    if data == "help":
        await event.edit(HELP_TEXT, buttons=MAIN_MENU)
        return
    
    try:
        if data == "today":
            await show_today(event, user_id)
        elif data == "list":
            await show_schedule(event, user_id)
        elif data == "add_menu":
            await event.reply("➕ **Thêm task:**\n```\n/add 09:00 Học bài\n```", buttons=MAIN_MENU)
        elif data == "done_menu":
            await event.reply("✅ **Đánh dấu hoàn thành:**\n```\n/done 08:00\n```", buttons=MAIN_MENU)
        elif data == "del_menu":
            await event.reply("🗑️ **Xóa task:**\n```\n/del 08:00\n```\n(Xóa toàn bộ slot 08:00)", buttons=MAIN_MENU)
        elif data == "reset":
            user_data = load_user_data(user_id)
            user_data['completed'] = []
            save_user_data(user_id, user_data)
            await event.reply("🔄 **Reset done list OK!**", buttons=MAIN_MENU)
        await event.answer()
    except Exception as e:
        logger.error(f"Button error: {e}")
        await event.answer("❌ Thử lại!")
async def show_today(event, user_id):
    data = load_user_data(user_id)
    now = datetime.now()
    today_tasks = {k: v for k, v in data['schedule'].items() 
                   if time.fromisoformat(k) >= now.time()}
    
    if not today_tasks:
        await event.reply("✅ **Hôm nay hoàn thành!** 🎉", buttons=MAIN_MENU)
        return
    
    msg = "**📅 Còn lại hôm nay:**\n\n"
    for hour, tasks in today_tasks.items():
        status = "✅" if hour in data['completed'] else "⏳"
        msg += f"{status} **{hour}:** {', '.join(tasks)}\n"
    
    await event.reply(msg, buttons=MAIN_MENU)
async def show_schedule(event, user_id):
    data = load_user_data(user_id)
    msg = "**📋 Lịch cá nhân:**\n\n"
    for hour, tasks in data['schedule'].items():
        status = "✅" if hour in data['completed'] else "⏳"
        msg += f"{status} **{hour}:** {', '.join(tasks)}\n"
    await event.reply(msg, buttons=MAIN_MENU)
@client.on(events.NewMessage(pattern=r'/add\s+(\d{2}:\d{2})\s+(.*)'))
async def add_task(event):
    hour = event.pattern_match.group(1)
    task = event.pattern_match.group(2).strip()
    user_id = event.sender_id
    
    data = load_user_data(user_id)
    if hour not in data['schedule']:
        data['schedule'][hour] = []
    data['schedule'][hour].append(task)
    save_user_data(user_id, data)
    
    await event.reply(f"✅ **Thêm OK:** `{hour}` - {task}", buttons=MAIN_MENU)
@client.on(events.NewMessage(pattern=r'/done\s+(\d{2}:\d{2})'))
async def mark_done(event):
    hour = event.pattern_match.group(1)
    user_id = event.sender_id
    
    data = load_user_data(user_id)
    if hour not in data['completed']:
        data['completed'].append(hour)
        save_user_data(user_id, data)
    
    await event.reply(f"🎉 **Done:** `{hour}`!", buttons=MAIN_MENU)
@client.on(events.NewMessage(pattern=r'/del\s+(\d{2}:\d{2})'))
async def delete_task(event):
    hour = event.pattern_match.group(1)
    user_id = event.sender_id
    
    data = load_user_data(user_id)
    if hour in data['schedule']:
        del data['schedule'][hour]
        save_user_data(user_id, data)
        await event.reply(f"🗑️ **Xóa OK:** `{hour}`", buttons=MAIN_MENU)
    else:
        await event.reply("❌ Không tìm thấy!", buttons=MAIN_MENU)
@client.on(events.NewMessage(pattern=r'/schedule'))
async def show_schedule_cmd(event):
    await show_schedule(event, event.sender_id)
@client.on(events.NewMessage(pattern='/reset'))
async def reset(event):
    user_id = event.sender_id
    data = load_user_data(user_id)
    data['completed'] = []
    save_user_data(user_id, data)
    await event.reply("🔄 **Reset OK!**", buttons=MAIN_MENU)
async def reminder_loop():
    logger.info("🚀 Reminder started!")
    while True:
        try:
            now_str = datetime.now().strftime("%H:%M")
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, schedule FROM users')
            
            for row in cursor.fetchall():
                user_id, schedule_json = row
                schedule = json.loads(schedule_json)
                
                if now_str in schedule:
                    tasks = schedule[now_str]
                    msg = f"🚨 **{now_str} - BẮT ĐẦU NGAY!** 🚨\n\n"
                    msg += "**" + " | ".join(tasks) + "**"
                    msg += f"\n\n`/done {now_str}`"
                    
                    try:
                        await client.send_message(user_id, msg)
                        logger.info(f"✅ Reminder {now_str} -> {user_id}")
                    except Exception as e:
                        logger.error(f"Send failed {user_id}: {e}")
            
            conn.close()
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Reminder error: {e}")
            await asyncio.sleep(60)
async def main():
    init_db()
    await client.start(bot_token=BOT_TOKEN)
    
    logger.info("🤖 Bot STARTED on Railway!")
    
    asyncio.create_task(reminder_loop())
    await client.run_until_disconnected()
if __name__ == '__main__':
    asyncio.run(main())
