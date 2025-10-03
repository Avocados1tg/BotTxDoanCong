import logging
import random
import os
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Voice
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

import yt_dlp

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    print("Lỗi: Không tìm thấy TELEGRAM_BOT_TOKEN.")
    exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# DB
DB_FILE = 'yt_music.db'
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS queues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    song_title TEXT,
    song_url TEXT,
    added_by INTEGER,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    played BOOLEAN DEFAULT FALSE
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    daily_bonus_claimed DATE DEFAULT NULL
)''')
conn.commit()

def get_queue(chat_id):
    cursor.execute("SELECT song_title, song_url FROM queues WHERE chat_id = ? AND played = FALSE ORDER BY added_at LIMIT 1", (chat_id,))
    row = cursor.fetchone()
    if row:
        return row[0], row[1]
    return None, None

def add_to_queue(chat_id, title, url, added_by):
    cursor.execute("INSERT INTO queues (chat_id, song_title, song_url, added_by) VALUES (?, ?, ?, ?)", (chat_id, title, url, added_by))
    conn.commit()

def mark_played(chat_id):
    cursor.execute("UPDATE queues SET played = TRUE WHERE chat_id = ? AND played = FALSE ORDER BY added_at LIMIT 1", (chat_id,))
    conn.commit()

def clear_queue(chat_id):
    cursor.execute("DELETE FROM queues WHERE chat_id = ?", (chat_id,))
    conn.commit()

def can_claim_bonus(user_id):
    cursor.execute("SELECT daily_bonus_claimed FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return True
    last_date = datetime.strptime(row[0], '%Y-%m-%d').date()
    today = datetime.now().date()
    return last_date < today

def claim_bonus(user_id):
    bonus_title = random.choice(['Happy - Pharrell Williams', 'Shape of You - Ed Sheeran', 'Despacito - Luis Fonsi'])
    bonus_url = f"https://www.youtube.com/results?search_query={bonus_title.replace(' ', '+')}"
    cursor.execute("INSERT OR REPLACE INTO users (user_id, daily_bonus_claimed) VALUES (?, ?)", (user_id, datetime.now().date().strftime('%Y-%m-%d')))
    conn.commit()
    return bonus_title, bonus_url

async def search_yt_music(query, max_results=5):
    # Thêm "nhạc Việt" nếu query tiếng Việt
    if any(char in 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ' for char in query):
        query += ' nhạc Việt'
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            results = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)['entries']
            songs = []
            for entry in results:
                song_id = entry['id']
                songs.append({
                    'title': entry['title'],
                    'url': f"https://www.youtube.com/watch?v={song_id}",
                    'duration': entry.get('duration', 0)
                })
            return songs
        except Exception as e:
            logging.error(f"YT search error: {e}")
            return []

async def download_preview(url, title):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'temp.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'ogg',
            'preferredquality': '64',
        }],
        'postprocessor_args': ['-ss', '0', '-t', '30'],
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            return file_path, title
        except Exception as e:
            logging.error(f"Download error: {e}")
            return None, None

async def play_next_song(context, chat_id):
    title, url = get_queue(chat_id)
    if not title:
        return  # Không queue thì dừng
    file_path, song_title = await download_preview(url, title)
    if file_path:
        try:
            with open(file_path, 'rb') as audio:
                await context.bot.send_voice(chat_id=chat_id, voice=audio, caption=f'🎵 **Đang chơi: {song_title}** (preview 30s)')
            os.remove(file_path)
            mark_played(chat_id)
            # Chỉ gọi next nếu còn queue
            next_title, _ = get_queue(chat_id)
            if next_title:
                asyncio.create_task(play_next_song(context, chat_id))
        except Exception as e:
            logging.error(f"Send voice error: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f'❌ **Lỗi play {song_title}!** Gửi link YT: {url}')
            mark_played(chat_id)
            if get_queue(chat_id):
                asyncio.create_task(play_next_song(context, chat_id))
    else:
        await context.bot.send_message(chat_id=chat_id, text=f'❌ **Lỗi download {title}!** Gửi link YT: {url}')
        mark_played(chat_id)
        if get_queue(chat_id):
            asyncio.create_task(play_next_song(context, chat_id))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    keyboard = get_main_keyboard()
    welcome_msg = """
🎵 **Bot Nghe Nhạc YT Siêu Chill!** 🎧

Chào anh! Bot search YT, queue bài hát, play preview 30s.
Gõ /music <tên bài> để bắt đầu, hoặc nút dưới.
Daily bonus: 1 bài random miễn phí/ngày!

Chọn nhé 😎
    """
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔍 Search YT", callback_data='music_search')],
        [InlineKeyboardButton("📋 Xem Queue", callback_data='music_queue')],
        [InlineKeyboardButton("⏭ Skip Bài", callback_data='music_skip')],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data='music_bonus')],
        [InlineKeyboardButton("🗑️ Clear Queue", callback_data='music_clear')],
        [InlineKeyboardButton("ℹ️ Hướng dẫn", callback_data='music_help')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if query.data == 'music_search':
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='music_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text='🔍 **Search bài hát:**\nGõ tên bài (ví dụ "Shape of You") sau tin này.', parse_mode='Markdown', reply_markup=reply_markup)
        context.user_data['waiting_search'] = True
        return

    if query.data == 'music_queue':
        queue = get_queue(chat_id)
        if not queue:
            msg = '📋 **Queue trống!**\nThêm bài hát đi 🎵'
        else:
            msg = '📋 **Queue hiện tại:**\n' + '\n'.join(f'• {title}' for title, _ in queue[:5]) + ('...\n(5+ bài)' if len(queue) > 5 else '')
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='music_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown', reply_markup=reply_markup)
        return

    if query.data == 'music_skip':
        title, _ = get_queue(chat_id)
        if title:
            mark_played(chat_id)
            await context.bot.send_message(chat_id=chat_id, text=f'⏭ **Skipped {title}!** Playing next...', reply_markup=get_menu_keyboard())
            asyncio.create_task(play_next_song(context, chat_id))
        else:
            await context.bot.send_message(chat_id=chat_id, text='⏭ **Không có bài nào để skip!**', reply_markup=get_menu_keyboard())
        return

    if query.data == 'music_bonus':
        if can_claim_bonus(user_id):
            bonus_title, bonus_url = claim_bonus(user_id)
            add_to_queue(chat_id, bonus_title, bonus_url, user_id)
            await context.bot.send_message(chat_id=chat_id, text=f'🎁 **Daily Bonus: {bonus_title}!** Added to queue.\nPlaying now...', reply_markup=get_menu_keyboard())
            asyncio.create_task(play_next_song(context, chat_id))
        else:
            await context.bot.send_message(chat_id=chat_id, text='🎁 **Daily bonus hôm nay đã nhận rồi!**\nMai quay lại nhé 😊', reply_markup=get_menu_keyboard())
        return

    if query.data == 'music_clear':
        clear_queue(chat_id)
        await context.bot.send_message(chat_id=chat_id, text='🗑️ **Queue cleared!**', reply_markup=get_menu_keyboard())
        return

    if query.data == 'music_help':
        msg = """
ℹ️ **Hướng dẫn nghe nhạc YT:**

• **Search:** Ấn 🔍 hoặc /music <tên bài> > Chọn > Add queue + play preview 30s.
• **Queue:** Xem danh sách bài chờ, play theo thứ tự.
• **Skip:** Bỏ bài hiện tại, play bài sau.
• **Daily:** Bonus 1 bài random miễn phí/ngày.
• **Clear:** Xóa queue.
• Lưu ý: Preview 30s (free), full nghe trên YT app. Không download full.

🔙 *Menu*
        """
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown', reply_markup=reply_markup)
        return

    if query.data == 'music_menu':
        keyboard = get_main_keyboard()
        await context.bot.send_message(chat_id=chat_id, text='🎵 **Menu Nhạc YT:**\nChọn để search, play, queue...', parse_mode='Markdown', reply_markup=keyboard)
        return

    if query.data.startswith('music_add_'):
        parts = query.data.split('_', 3)
        url = parts[2]
        title = parts[3].replace("_", " ") if len(parts) > 3 else 'Unknown'
        add_to_queue(chat_id, title, url, user_id)
        await context.bot.send_message(chat_id=chat_id, text=f'🎵 **Added to queue: {title}**\nPlaying preview 30s...', reply_markup=get_menu_keyboard())
        asyncio.create_task(play_next_song(context, chat_id))
        return

async def music_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Sử dụng /music <tên bài hát>')
        return
    query_text = ' '.join(context.args)
    songs = await search_yt_music(query_text, 5)
    if not songs:
        await update.message.reply_text('❌ Không tìm thấy! Thử từ khóa khác.')
        return
    keyboard = []
    for song in songs:
        callback = f'music_add_{song["url"]}_{song["title"].replace(" ", "_")}'
        keyboard.append([InlineKeyboardButton(f"{song['title'][:30]}... ({song['duration']}s)", callback_data=callback)])
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data='music_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = '🎵 **Kết quả search YT:**\nChọn bài để add queue (preview 30s).'
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_music_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'waiting_search' not in context.user_data:
        return
    query_text = update.message.text.strip()
    songs = await search_yt_music(query_text, 5)
    if not songs:
        await update.message.reply_text('❌ **Không tìm thấy bài hát!** Thử từ khóa khác.')
        return
    keyboard = []
    for song in songs:
        callback = f'music_add_{song["url"]}_{song["title"].replace(" ", "_")}'
        keyboard.append([InlineKeyboardButton(f"{song['title'][:30]}... ({song['duration']}s)", callback_data=callback)])
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data='music_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = '🎵 **Kết quả search YT:**\nChọn bài để add queue (preview 30s).'
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    context.user_data.pop('waiting_search', None)

def get_menu_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='music_menu')]]
    return InlineKeyboardMarkup(keyboard)

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("music", music_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_music_search))
    print("Bot nghe nhạc YT full đang chạy... Ctrl+C dừng.")
    application.run_polling()

if __name__ == '__main__':
    main()