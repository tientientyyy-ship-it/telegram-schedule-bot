import asyncio
import json
import os
import logging
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from datetime import datetime, time
from collections import defaultdict
import aiosqlite
import signal
import sys

# Logging cho Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# CONFIG từ Railway Environment Variables
API_ID = int(os.getenv('API_ID', '30475514'))
API_HASH = os.getenv('API_HASH', '80fd530f75c492058515eb956c1d66e1')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8236006228:AAE5_axnMNh85f1wzfMd5IFI8ed12MCCZ9M')
DB_PATH = os.getenv('DB_PATH', 'user_data.db')

# DEFAULT SCHEDULE
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
    [Button.inline("⚙️ Cài đặt", b"settings"), Button.inline("🔄 Reset", b"reset")]
]

# Database
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                schedule TEXT,
                completed TEXT
            )
        ''')
        await db.commit()
        logger.info("✅ Database initialized")

async def load_user_data(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT schedule, completed FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    'schedule': json.loads(row[0]) if row[0] else DEFAULT_SCHEDULE,
                    'completed': json.loads(row[1]) if row[1] else []
                }
            else:
                # Insert default
                await db.execute('INSERT INTO users (user_id, schedule, completed) VALUES (?, ?, ?)',
                               (user_id, json.dumps(DEFAULT_SCHEDULE), json.dumps([])))
                await db.commit()
                return {'schedule': DEFAULT_SCHEDULE, 'completed': []}

async def save_user_data(user_id, data):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE users SET schedule = ?, completed = ? WHERE user_id = ?
        ''', (json.dumps(data['schedule']), json.dumps(data['completed']), user_id))
        await db.commit()

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("🤖 **Schedule Bot 24/7** (Railway Deployed)\n\nChào mừng! Bot nhắc lịch **24/24**!", buttons=MAIN_MENU)

@client.on(events.CallbackQuery)
async def button_handler(event):
    data = event.data.decode()
    user_id = event.sender_id
    
    try:
        if data == "today":
            await show_today(event, user_id)
        elif data == "list":
            await show_schedule(event, user_id)
        elif data == "add_menu":
            await event.reply("📝 **Thêm task:**\n`/add 09:00 Task mới`", buttons=MAIN_MENU)
        elif data == "done_menu":
            await event.reply("✅ **Đánh dấu hoàn thành:**\n`/done 08:00`", buttons=MAIN_MENU)
        elif data == "settings":
            await event.reply("⚙️ **Commands:**\n`/schedule` - Xem lịch\n`/add` - Thêm\n`/del 08:00` - Xóa\n`/reset` - Reset", buttons=MAIN_MENU)
        elif data == "reset":
            data = await load_user_data(user_id)
            data['completed'] = []
            await save_user_data(user_id, data)
            await event.reply("🔄 **Reset done list!**", buttons=MAIN_MENU)
        await event.answer()
    except Exception as e:
        logger.error(f"Button error: {e}")
        await event.answer("❌ Lỗi, thử lại!")

async def show_today(event, user_id):
    data = await load_user_data(user_id)
    now = datetime.now()
    today_tasks = {k: v for k, v in data['schedule'].items() 
                   if time.fromisoformat(k) >= now.time()}
    
    if not today_tasks:
        await event.reply("✅ **Hôm nay hoàn thành hết!** 🎉", buttons=MAIN_MENU)
        return
    
    msg = "**📅 Còn lại hôm nay:**\n\n"
    for hour, tasks in today_tasks.items():
        status = "✅" if hour in data['completed'] else "⏳"
        msg += f"{status} **{hour}:** {', '.join(tasks)}\n"
    
    await event.reply(msg, buttons=MAIN_MENU)

async def show_schedule(event, user_id):
    data = await load_user_data(user_id)
    msg = "**📋 Lịch cá nhân:**\n\n"
    for hour, tasks in data['schedule'].items():
        status = "✅" if hour in data['completed'] else "⏳"
        msg += f"{status} **{hour}:** {', '.join(tasks)}\n"
    await event.reply(msg, buttons=MAIN_MENU)

# COMMANDS
@client.on(events.NewMessage(pattern=r'/add\s+(\d{2}:\d{2})\s+(.*)'))
async def add_task(event):
    hour = event.pattern_match.group(1)
    task = event.pattern_match.group(2).strip()
    user_id = event.sender_id
    
    data = await load_user_data(user_id)
    if hour not in data['schedule']:
        data['schedule'][hour] = []
    data['schedule'][hour].append(task)
    await save_user_data(user_id, data)
    
    await event.reply(f"✅ **Đã thêm:** `{hour}` - {task}", buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern=r'/done\s+(\d{2}:\d{2})'))
async def mark_done(event):
    hour = event.pattern_match.group(1)
    user_id = event.sender_id
    
    data = await load_user_data(user_id)
    if hour not in data['completed']:
        data['completed'].append(hour)
        await save_user_data(user_id, data)
    
    await event.reply(f"🎉 **Hoàn thành:** `{hour}`!", buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern=r'/del\s+(\d{2}:\d{2})'))
async def delete_task(event):
    hour = event.pattern_match.group(1)
    user_id = event.sender_id
    
    data = await load_user_data(user_id)
    if hour in data['schedule']:
        del data['schedule'][hour]
        await save_user_data(user_id, data)
        await event.reply(f"🗑️ **Đã xóa:** `{hour}`", buttons=MAIN_MENU)
    else:
        await event.reply("❌ Không tìm thấy giờ này!", buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern=r'/schedule'))
async def show_schedule_cmd(event):
    await show_schedule(event, event.sender_id)

@client.on(events.NewMessage(pattern='/reset'))
async def reset(event):
    user_id = event.sender_id
    data = await load_user_data(user_id)
    data['completed'] = []
    await save_user_data(user_id, data)
    await event.reply("🔄 **Reset done list!**", buttons=MAIN_MENU)

# 🔥 REMINDER LOOP 24/7 - CHÍNH XÁC TỚI PHÚT
async def reminder_loop():
    logger.info("🚀 Reminder loop started!")
    while True:
        try:
            now_str = datetime.now().strftime("%H:%M")
            logger.info(f"Checking reminders at {now_str}")
            
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute('SELECT user_id, schedule FROM users') as cursor:
                    async for row in cursor:
                        user_id, schedule_json = row
                        schedule = json.loads(schedule_json)
                        
                        if now_str in schedule:
                            tasks = schedule[now_str]
                            msg = f"🚨🚨 **{now_str} - BẮT ĐẦU NGAY!** 🚨🚨\n\n"
                            msg += "**" + " | ".join(tasks) + "**"
                            msg += f"\n\n`/done {now_str}` để đánh dấu"
                            
                            try:
                                await client.send_message(user_id, msg)
                                logger.info(f"✅ Sent reminder to {user_id} at {now_str}")
                            except Exception as e:
                                logger.error(f"❌ Failed to send to {user_id}: {e}")
            
            # Sleep chính xác 60s
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Reminder loop error: {e}")
            await asyncio.sleep(60)

def signal_handler(sig, frame):
    logger.info("🛑 Shutting down gracefully...")
    asyncio.create_task(client.disconnect())
    sys.exit(0)

# MAIN
async def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await init_db()
    await client.start(bot_token=BOT_TOKEN)
    
    logger.info("🤖 Schedule Bot 24/7 started on Railway!")
    logger.info(f"📊 Bot ID: {client.tl.me.id}")
    
    # Start reminder loop
    asyncio.create_task(reminder_loop())
    
    # Keep alive
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
