import asyncio
import json
import os
import logging
import sys
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from datetime import datetime, time, timedelta
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
    [Button.inline("📅 Hôm nay", b"today"), Button.inline("📋 Lịch tuần", b"week")],
    [Button.inline("➕ Thêm task", b"add_date"), Button.inline("✅ Done", b"done_menu")],
    [Button.inline("🗑️ Xóa", b"del_menu"), Button.inline("🔄 Reset", b"reset")],
    [Button.inline("📖 Help", b"help")]
]

HELP_TEXT = """
**🤖 Schedule Bot - LỊCH TUẦN**

📅 **Xem:**
• `/schedule` - Tuần này
• 📅 Hôm nay / 📋 Tuần

➕ **Thêm task:**
• `/add 2024-02-28 09:00 Học bài`
• Hoặc nhấn ➕ → Chọn ngày

🗑️ **Xóa:** `/del 2024-02-28 09:00`

✅ **Done:** `/done 2024-02-28 09:00`

🔄 **Reset:** `/reset_all`

⏰ **Nhắc 24/7 theo ngày!**
"""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            schedules TEXT,
            completed TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ Database OK")

def load_user_data(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT schedules, completed FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'schedules': json.loads(row[0]) if row[0] else {},
            'completed': json.loads(row[1]) if row[1] else []
        }
    else:
        save_user_data(user_id, {'schedules': {}, 'completed': []})
        return {'schedules': {}, 'completed': []}

def save_user_data(user_id, data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, schedules, completed) 
        VALUES (?, ?, ?)
    ''', (user_id, json.dumps(data['schedules']), json.dumps(data['completed'])))
    conn.commit()
    conn.close()

def get_date_key(date_obj):
    return date_obj.strftime("%Y-%m-%d")

@client.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.reply(HELP_TEXT, buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "🤖 **Schedule Bot TUẦN** ✅\n\n"
        "📅 Lên lịch **cả tuần**!\n"
        "📖 **/help** để xem hướng dẫn",
        buttons=MAIN_MENU
    )

@client.on(events.CallbackQuery)
async def button_handler(event):
    data = event.data.decode()
    user_id = event.sender_id
    
    if data == "help":
        await event.edit(HELP_TEXT, buttons=MAIN_MENU)
        return
    elif data == "add_date":
        await event.edit(
            "**➕ THÊM TASK THEO NGÀY:**\n\n"
            "`/add YYYY-MM-DD HH:MM Task`\n\n"
            "**Ví dụ:**\n"
            "• `/add 2024-02-28 09:00 Họp team`\n"
            "• `/add 2024-03-01 14:00 Gym`\n\n"
            "**Chọn ngày:**\n"
            f"📅 {get_date_key(datetime.now())} (hôm nay)\n"
            f"📅 {get_date_key(datetime.now() + timedelta(days=1))}",
            buttons=MAIN_MENU
        )
        return
    
    try:
        if data == "today":
            await show_today(event, user_id)
        elif data == "week":
            await show_week(event, user_id)
        elif data == "done_menu":
            await event.reply("✅ **Done:**\n`/done YYYY-MM-DD HH:MM`", buttons=MAIN_MENU)
        elif data == "del_menu":
            await event.reply("🗑️ **Xóa:**\n`/del YYYY-MM-DD HH:MM`", buttons=MAIN_MENU)
        elif data == "reset":
            data_user = load_user_data(user_id)
            data_user['completed'] = []
            save_user_data(user_id, data_user)
            await event.reply("🔄 **Reset done list!**", buttons=MAIN_MENU)
        await event.answer()
    except Exception as e:
        logger.error(f"Button error: {e}")

async def show_today(event, user_id):
    data = load_user_data(user_id)
    today_key = get_date_key(datetime.now())
    today_tasks = data['schedules'].get(today_key, {})
    
    now = datetime.now()
    remaining = {k: v for k, v in today_tasks.items() 
                 if time.fromisoformat(k) >= now.time()}
    
    if not remaining:
        await event.reply("✅ **Hôm nay hoàn thành!** 🎉", buttons=MAIN_MENU)
        return
    
    msg = f"**📅 {today_key} Còn lại:**\n\n"
    for hour, tasks in remaining.items():
        status = "✅" if f"{today_key} {hour}" in data['completed'] else "⏳"
        msg += f"{status} **{hour}:** {', '.join(tasks)}\n"
    
    await event.reply(msg, buttons=MAIN_MENU)

async def show_week(event, user_id):
    data = load_user_data(user_id)
    msg = "**📋 Lịch tuần này:**\n\n"
    
    for i in range(7):
        date_key = get_date_key(datetime.now() + timedelta(days=i))
        day_tasks = data['schedules'].get(date_key, {})
        
        if day_tasks:
            msg += f"**📅 {date_key}:**\n"
            for hour, tasks in day_tasks.items():
                status = "✅" if f"{date_key} {hour}" in data['completed'] else "⏳"
                msg += f"  {status} **{hour}:** {', '.join(tasks)}\n"
            msg += "\n"
    
    if not msg.strip():
        msg = "📭 **Chưa có lịch tuần nào!**"
    
    await event.reply(msg, buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern=r'/add\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(.*)'))
async def add_task(event):
    date_str = event.pattern_match.group(1)
    hour = event.pattern_match.group(2)
    task = event.pattern_match.group(3).strip()
    user_id = event.sender_id
    
    data = load_user_data(user_id)
    date_key = date_str
    
    if date_key not in data['schedules']:
        data['schedules'][date_key] = {}
    if hour not in data['schedules'][date_key]:
        data['schedules'][date_key][hour] = []
    
    data['schedules'][date_key][hour].append(task)
    save_user_data(user_id, data)
    
    await event.reply(f"✅ **Thêm OK:** `{date_str} {hour}` - {task}", buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern=r'/done\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})'))
async def mark_done(event):
    date_str = event.pattern_match.group(1)
    hour = event.pattern_match.group(2)
    key = f"{date_str} {hour}"
    user_id = event.sender_id
    
    data = load_user_data(user_id)
    if key not in data['completed']:
        data['completed'].append(key)
        save_user_data(user_id, data)
    
    await event.reply(f"🎉 **Done:** `{key}`!", buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern=r'/del\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})'))
async def delete_task(event):
    date_str = event.pattern_match.group(1)
    hour = event.pattern_match.group(2)
    user_id = event.sender_id
    
    data = load_user_data(user_id)
    date_key = date_str
    
    if date_key in data['schedules'] and hour in data['schedules'][date_key]:
        del data['schedules'][date_key][hour]
        if not data['schedules'][date_key]:
            del data['schedules'][date_key]
        save_user_data(user_id, data)
        await event.reply(f"🗑️ **Xóa OK:** `{date_str} {hour}`", buttons=MAIN_MENU)
    else:
        await event.reply("❌ Không tìm thấy!", buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern=r'/schedule'))
async def show_schedule_cmd(event):
    await show_week(event, event.sender_id)

@client.on(events.NewMessage(pattern='/reset'))
async def reset(event):
    user_id = event.sender_id
    data = load_user_data(user_id)
    data['completed'] = []
    save_user_data(user_id, data)
    await event.reply("🔄 **Reset done list!**", buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern='/reset_all'))
async def reset_all(event):
    user_id = event.sender_id
    save_user_data(user_id, {'schedules': {}, 'completed': []})
    await event.reply("🔄 **RESET TOÀN BỘ → TRỐNG!** 🎉", buttons=MAIN_MENU)

async def reminder_loop():
    logger.info("🚀 Reminder tuần started!")
    while True:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            date_key = get_date_key(datetime.now())
            time_key = datetime.now().strftime("%H:%M")
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, schedules FROM users')
            
            for row in cursor.fetchall():
                user_id, schedules_json = row
                schedules = json.loads(schedules_json)
                
                if date_key in schedules and time_key in schedules[date_key]:
                    tasks = schedules[date_key][time_key]
                    msg = f"🚨 **{time_key} - BẮT ĐẦU NGAY!** 🚨\n\n"
                    msg += "**" + " | ".join(tasks) + "**"
                    msg += f"\n\n`/done {date_key} {time_key}`"
                    
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
    
    logger.info("🤖 Schedule Bot TUẦN STARTED!")
    
    asyncio.create_task(reminder_loop())
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
