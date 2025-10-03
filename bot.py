import logging
import random
import os
import sqlite3
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    print("Lỗi: Không tìm thấy TELEGRAM_BOT_TOKEN. Đặt vào Railway!")
    exit(1)

# DB setup
DB_FILE = 'taixiu.db'
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, balance INTEGER DEFAULT 100, last_bonus DATE DEFAULT NULL)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS history (user_id INTEGER, entry TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS group_votes (group_id INTEGER, total INTEGER, votes_tai INTEGER DEFAULT 0, votes_xiu INTEGER DEFAULT 0, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

def get_user_data(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return {'wins': row[1], 'losses': row[2], 'balance': row[3], 'last_bonus': row[4]}
    else:
        cursor.execute("INSERT INTO users (user_id, wins, losses, balance, last_bonus) VALUES (?, 0, 0, 100, NULL)", (user_id,))
        conn.commit()
        return {'wins': 0, 'losses': 0, 'balance': 100, 'last_bonus': None}

def update_user_data(user_id, data):
    cursor.execute("UPDATE users SET wins = ?, losses = ?, balance = ?, last_bonus = ? WHERE user_id = ?", (data['wins'], data['losses'], data['balance'], data['last_bonus'], user_id))
    conn.commit()

def add_history(user_id, entry):
    cursor.execute("INSERT INTO history (user_id, entry) VALUES (?, ?)", (user_id, entry))
    conn.commit()

def get_history(user_id, limit=5):
    cursor.execute("SELECT entry FROM history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
    return [row[0] for row in cursor.fetchall()]

def get_top_users(limit=3):
    cursor.execute("SELECT user_id, wins FROM users ORDER BY wins DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def can_claim_bonus(user_id):
    data = get_user_data(user_id)
    if not data['last_bonus']:
        return True
    last_date = datetime.strptime(data['last_bonus'], '%Y-%m-%d').date()
    today = datetime.now().date()
    return last_date < today

def claim_bonus(user_id):
    bonus = random.randint(10, 50)
    data = get_user_data(user_id)
    data['balance'] += bonus
    data['last_bonus'] = datetime.now().date().strftime('%Y-%m-%d')
    update_user_data(user_id, data)
    return bonus

def add_group_roll(group_id, total):
    cursor.execute("INSERT OR REPLACE INTO group_votes (group_id, total, votes_tai, votes_xiu, timestamp) VALUES (?, ?, 0, 0, ?)", (group_id, total, datetime.now()))
    conn.commit()

def vote_group(group_id, vote_type):
    cursor.execute("UPDATE group_votes SET " + ("votes_tai = votes_tai + 1" if vote_type == 'tai' else "votes_xiu = votes_xiu + 1") + " WHERE group_id = ? AND timestamp > datetime('now', '-1 minute')", (group_id,))
    conn.commit()

def get_group_vote(group_id):
    cursor.execute("SELECT * FROM group_votes WHERE group_id = ? AND timestamp > datetime('now', '-1 minute') ORDER BY timestamp DESC LIMIT 1", (group_id,))
    row = cursor.fetchone()
    if row:
        return {'total': row[1], 'votes_tai': row[2], 'votes_xiu': row[3]}
    return None

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user_data(user_id)
    keyboard = get_main_keyboard()
    welcome_msg = """
🔥 **Bot Tài Xỉu Full Tính Năng!** 🎲

Chào anh! Cân bằng: **100 điểm giả** 💰
Tài 11-18, Xỉu 3-10. Cược tùy chỉnh, daily, group, share...
Chọn nút chơi 😎
    """
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎲 Chơi Tài Xỉu", callback_data='play')],
        [InlineKeyboardButton("⚔️ Thách đấu bạn", callback_data='challenge')],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data='bonus')],
        [InlineKeyboardButton("📊 Điểm số", callback_data='score')],
        [InlineKeyboardButton("📜 Lịch sử", callback_data='history')],
        [InlineKeyboardButton("🏆 Top chơi", callback_data='top')],
        [InlineKeyboardButton("🌐 Roll Group", callback_data='group_roll')],
        [InlineKeyboardButton("ℹ️ Hướng dẫn", callback_data='help')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if query.data == 'play':
        keyboard = [
            [InlineKeyboardButton("💵 10 điểm", callback_data='bet_10'), InlineKeyboardButton("💎 20 điểm", callback_data='bet_20')],
            [InlineKeyboardButton("💰 50 điểm", callback_data='bet_50')],
            [InlineKeyboardButton("💳 Nhập tiền tùy chỉnh", callback_data='custom_bet')],
            [InlineKeyboardButton("🔙 Menu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text='💰 **Chọn mức cược:**\n*(Hoặc nhập tùy chỉnh!)* 🎰', parse_mode='Markdown', reply_markup=reply_markup)
        return

    elif query.data.startswith('bet_'):
        bet = int(query.data.split('_')[1])
        data = get_user_data(user_id)
        if data['balance'] < bet:
            keyboard = get_menu_keyboard()
            await context.bot.send_message(chat_id=chat_id, text=f'❌ **Hết tiền rồi!** 😱\nCòn *{data["balance"]} điểm*. Cược nhỏ hơn đi!', parse_mode='Markdown', reply_markup=keyboard)
            return
        context.user_data['bet'] = bet
        context.user_data['waiting_guess'] = True
        keyboard = [
            [InlineKeyboardButton("💰 TÀI (11-18)", callback_data='tai')],
            [InlineKeyboardButton("💸 XỈU (3-10)", callback_data='xiu')],
            [InlineKeyboardButton("🔙 Menu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text=f'🤔 **Cược {bet} điểm!**\n*Đoán Tài hay Xỉu?* (Tài 11-18, Xỉu 3-10) 🎲', parse_mode='Markdown', reply_markup=reply_markup)
        return

    elif query.data == 'custom_bet':
        context.user_data['waiting_bet'] = True
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text='💳 **Nhập số tiền cược tùy chỉnh:**\n(Gõ số, ví dụ: 30. Phải <= cân bằng hiện tại)', parse_mode='Markdown', reply_markup=reply_markup)
        return

    elif query.data in ['tai', 'xiu']:
        bet = context.user_data.get('bet', 10)
        data = get_user_data(user_id)
        # Gửi ảnh xúc xắc (thay URL thật nếu có)
        await context.bot.send_photo(chat_id=chat_id, photo="https://i.imgur.com/custom3dice.jpg", caption="🎲 **Xúc xắc đang lăn...** 🌀")
        # Animation dice
        dice_msg1 = await context.bot.send_dice(chat_id=chat_id, emoji='🎲')
        dice_msg2 = await context.bot.send_dice(chat_id=chat_id, emoji='🎲')
        dice_msg3 = await context.bot.send_dice(chat_id=chat_id, emoji='🎲')
        await asyncio.sleep(1)
        dice1 = dice_msg1.dice.value
        dice2 = dice_msg2.dice.value
        dice3 = dice_msg3.dice.value
        total = dice1 + dice2 + dice3
        result = "TÀI 💰" if total >= 11 else "XỈU 💸"  # Quy tắc mới: Tài 11-18, Xỉu 3-10
        user_guess = "TÀI" if query.data == 'tai' else "XỈU"

        win = user_guess == result.replace(" 💰", "").replace(" 💸", "")
        if win:
            data['wins'] += 1
            data['balance'] += bet * 2
            status_emoji = "🎉"
            status_text = f"**Thắng lớn!** +{bet * 2} điểm 💥"
        else:
            data['losses'] += 1
            data['balance'] -= bet
            status_emoji = "😢"
            status_text = f"**Thua tiếc!** -{bet} điểm 💔"

        update_user_data(user_id, data)
        history_entry = f"{dice1}+{dice2}+{dice3}={total} ({result}) - {status_text}"
        add_history(user_id, history_entry)

        balance_new = data['balance']
        result_msg = f"""
{status_emoji} **Kết quả ván chơi!** {status_emoji}

**🎲{dice1} 🎲{dice2} 🎲{dice3} = {total} ({result})**

{status_text}

💰 **Cân bằng:** *{balance_new} điểm*

Chơi tiếp?
        """
        keyboard = [
            [InlineKeyboardButton("🎲 Chơi lại", callback_data='play')],
            [InlineKeyboardButton("📤 Share kết quả", callback_data='share')],
            [InlineKeyboardButton("🔙 Menu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text=result_msg, parse_mode='Markdown', reply_markup=reply_markup)
        context.user_data.pop('bet', None)
        return

    # Các phần khác (bonus, group_roll, vote, share, score, history, top, challenge, help, reset, menu) giữ nguyên như code trước
    # ... (code cho các phần này giống code trước, dùng send_message)

    # Handle custom bet input
async def handle_custom_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.message.chat_id
    if 'waiting_bet' not in context.user_data:
        return  # Chỉ handle khi đang chờ
    try:
        bet = int(update.message.text.strip())
        data = get_user_data(user_id)
        if bet <= 0 or bet > data['balance']:
            keyboard = get_menu_keyboard()
            await update.message.reply_text(f'❌ **Số tiền không hợp lệ!** 😱\nPhải 1-{data["balance"]} điểm. Thử lại hoặc menu.', parse_mode='Markdown', reply_markup=keyboard)
            return
        context.user_data['bet'] = bet
        context.user_data['waiting_guess'] = True
        context.user_data['waiting_bet'] = False  # Reset flag
        keyboard = [
            [InlineKeyboardButton("💰 TÀI (11-18)", callback_data='tai')],
            [InlineKeyboardButton("💸 XỈU (3-10)", callback_data='xiu')],
            [InlineKeyboardButton("🔙 Menu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f'🤔 **Cược {bet} điểm tùy chỉnh!**\n*Đoán Tài hay Xỉu?* (Tài 11-18, Xỉu 3-10) 🎲', parse_mode='Markdown', reply_markup=reply_markup)
    except ValueError:
        keyboard = get_menu_keyboard()
        await update.message.reply_text('❌ **Phải gõ số nguyên!** 😅\nVí dụ: 30. Thử lại hoặc menu.', parse_mode='Markdown', reply_markup=keyboard)

def get_menu_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='menu')]]
    return InlineKeyboardMarkup(keyboard)

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_bet))  # Handle gõ số cược
    print("Bot Tài Xỉu full + tùy chỉnh cược + quy tắc mới đang chạy... Ctrl+C dừng.")
    application.run_polling()

if __name__ == '__main__':
    main()