import asyncio
import json
import os
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from datetime import datetime, time
import logging
from collections import defaultdict

# CONFIG (Railway sẽ set qua Environment Variables)
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Mặc định schedule (mỗi user override riêng)
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

client = TelegramClient(StringSession(), API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Storage cho mỗi user
user_data = defaultdict(lambda: {
    'schedule': DEFAULT_SCHEDULE.copy(),
    'completed': []
})

MAIN_MENU = [
    [Button.inline("📅 Hôm nay", b"today"), Button.inline("📋 Lịch cá nhân", b"list")],
    [Button.inline("➕ Thêm task", b"add_menu"), Button.inline("✅ Done", b"done_menu")],
    [Button.inline("⚙️ Cài đặt", b"settings"), Button.inline("🔄 Reset", b"reset")]
]

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("🤖 **Schedule Bot 24/7**\n\nChào mừng! Bot sẽ nhắc lịch **cá nhân hóa** theo giờ!", buttons=MAIN_MENU)

@client.on(events.CallbackQuery)
async def button_handler(event):
    data = event.data.decode()
    user_id = event.sender_id
    
    if data == "today":
        await show_today(event, user_id)
    elif data == "list":
        await show_schedule(event, user_id)
    elif data == "add_menu":
        await event.reply("Gửi: `/add 09:00 Task của bạn`", buttons=MAIN_MENU)
    elif data == "done_menu":
        await event.reply("Gửi: `/done 08:00`", buttons=MAIN_MENU)
    elif data == "settings":
        await event.reply("**/schedule - Xem lịch\n/add - Thêm\n/del 08:00 - Xóa**", buttons=MAIN_MENU)
    elif data == "reset":
        user_data[user_id]['completed'] = []
        await event.reply("🔄 **Reset done list!**", buttons=MAIN_MENU)
    
    await event.answer()

async def show_today(event, user_id):
    user_schedule = user_data[user_id]['schedule']
    now = datetime.now()
    today_tasks = {k: v for k, v in user_schedule.items() 
                   if time.fromisoformat(k) >= now.time()}
    
    if not today_tasks:
        await event.reply("✅ **Hôm nay hoàn thành hết!** 🎉", buttons=MAIN_MENU)
        return
    
    msg = "**📅 Còn lại hôm nay:**\n\n"
    for hour, tasks in today_tasks.items():
        status = "✅" if is_done(user_id, hour) else "⏳"
        msg += f"{status} **{hour}:** {', '.join(tasks)}\n"
    
    await event.reply(msg, buttons=MAIN_MENU)

async def show_schedule(event, user_id):
    user_schedule = user_data[user_id]['schedule']
    msg = "**📋 Lịch cá nhân:**\n\n"
    for hour, tasks in user_schedule.items():
        status = "✅" if is_done(user_id, hour) else "⏳"
        msg += f"{status} **{hour}:** {', '.join(tasks)}\n"
    await event.reply(msg, buttons=MAIN_MENU)

def is_done(user_id, hour):
    return hour in user_data[user_id]['completed']

# 🔥 COMMANDS
@client.on(events.NewMessage(pattern=r'/add\s+(\d{2}:\d{2})\s+(.*)'))
async def add_task(event):
    hour = event.pattern_match.group(1)
    task = event.pattern_match.group(2).strip()
    user_id = event.sender_id
    
    if hour not in user_data[user_id]['schedule']:
        user_data[user_id]['schedule'][hour] = []
    user_data[user_id]['schedule'][hour].append(task)
    
    await event.reply(f"✅ **Đã thêm:** `{hour}` - {task}", buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern=r'/done\s+(\d{2}:\d{2})'))
async def mark_done(event):
    hour = event.pattern_match.group(1)
    user_id = event.sender_id
    
    if hour not in user_data[user_id]['completed']:
        user_data[user_id]['completed'].append(hour)
    
    await event.reply(f"🎉 **Hoàn thành:** `{hour}`!", buttons=MAIN_MENU)

@client.on(events.NewMessage(pattern=r'/del\s+(\d{2}:\d{2})'))
async def delete_task(event):
    hour = event.pattern_match.group(1)
    user_id = event.sender_id
    
    if hour in user_data[user_id]['schedule']:
        del user_data[user_id]['schedule'][hour]
        await event.reply(f"🗑️ **Đã xóa:** `{hour}`", buttons=MAIN_MENU)
    else:
        await event.reply("❌ Không tìm thấy giờ này!")
@client.on(events.NewMessage(pattern='/reset'))
async def reset(event):
    user_id = event.sender_id
    user_data[user_id]['completed'] = []
    await event.reply("🔄 **Reset done list!**", buttons=MAIN_MENU)

# 🔥 AUTO REMINDER 24/7
async def reminder_loop():
    while True:
        now = datetime.now().strftime("%H:%M")
        for user_id, data in user_data.items():
            if now in data['schedule']:
                tasks = data['schedule'][now]
                msg = f"🚨🚨 **{now} - BẮT ĐẦU NGAY!** 🚨🚨\n\n"
                msg += "**" + " | ".join(tasks) + "**"
                msg += f"\n\n`/done {now}`"
                try:
                    await client.send_message(user_id, msg)
                except:
                    pass
        await asyncio.sleep(60)  # Check mỗi phút

# START
async def main():
    print("🤖 Schedule Bot 24/7 starting...")
    asyncio.create_task(reminder_loop())
    print("✅ Bot running! Deployed on Railway!")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())


