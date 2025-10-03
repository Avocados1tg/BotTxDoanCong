import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Voice
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import yt_dlp

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_TOKEN_HERE')  # Thay token thật

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = """
🎵 **Bot Nghe Nhạc YT Đơn Giản!** 🎧

Chào anh! Gõ /music <tên bài> (ví dụ /music Despacito) để search YT.
Bot hiện 5 kết quả, ấn nút để nghe preview 30s voice.

Chỉ vậy thôi, chill nghe nhạc đi! 😎
    """
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def music_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Sử dụng /music <tên bài hát>')
        return
    query_text = ' '.join(context.args)
    songs = await search_yt_music(query_text, 5)
    if not songs:
        await update.message.reply_text('❌ Không tìm thấy! Thử từ khóa khác (ví dụ "Despacito official").')
        return
    keyboard = []
    for song in songs:
        callback = f'play_{song["url"]}_{song["title"].replace(" ", "_")}'
        keyboard.append([InlineKeyboardButton(f"{song['title'][:30]}... ({song['duration']}s)", callback_data=callback)])
    keyboard.append([InlineKeyboardButton("🔙 /start", callback_data='back_start')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = f'🎵 **Kết quả search "{query_text}":**\nChọn bài để nghe preview 30s.'
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def search_yt_music(query, max_results=5):
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if query.data == 'back_start':
        await start(update, context)
        return

    if query.data.startswith('play_'):
        parts = query.data.split('_', 3)
        url = parts[1]
        title = parts[3].replace("_", " ") if len(parts) > 3 else 'Unknown'
        await query.message.reply_text(f'🎵 **Đang tải preview {title}...** (30s)')
        file_path, song_title = await download_preview(url, title)
        if file_path:
            try:
                with open(file_path, 'rb') as audio:
                    await context.bot.send_voice(chat_id=chat_id, voice=audio, caption=f'🎵 **Nghe {song_title}** (preview 30s - full trên YT!)')
                os.remove(file_path)
            except Exception as e:
                logging.error(f"Send voice error: {e}")
                await context.bot.send_message(chat_id=chat_id, text=f'❌ **Lỗi play {song_title}!** Link YT: {url}')
        else:
            await context.bot.send_message(chat_id=chat_id, text=f'❌ **Lỗi download {title}!** Link YT: {url}')
        return

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

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("music", music_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    print("Bot nghe nhạc YT đơn giản đang chạy... Ctrl+C dừng.")
    application.run_polling()

if __name__ == '__main__':
    main()