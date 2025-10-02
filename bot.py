import logging
import random
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Thay bằng token thật từ BotFather
TOKEN = 'YOUR_TOKEN_HERE'

# Lưu dữ liệu user (tạm, reset khi restart)
user_scores = defaultdict(lambda: {'wins': 0, 'losses': 0, 'balance': 100})  # 100 điểm khởi đầu
user_history = defaultdict(list)  # Lịch sử 5 ván

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🎲 *Chơi Tài Xỉu*", callback_data='play')],
        [InlineKeyboardButton("📊 *Điểm số của tôi*", callback_data='score')],
        [InlineKeyboardButton("📜 *Lịch sử chơi*", callback_data='history')],
        [InlineKeyboardButton("🏆 *Top người chơi*", callback_data='top')],
        [InlineKeyboardButton("ℹ️ *Hướng dẫn*", callback_data='help')],
        [InlineKeyboardButton("🔄 *Reset điểm*", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_msg = f"""
🎉 **Chào mừng đến Bot Tài Xỉu Siêu Vui!** 🎲

Chọn nút dưới để khám phá. Cân bằng khởi đầu: *100 điểm giả* (chỉ vui thôi nhé! 😊)
    """
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == 'play':
        # Hỏi mức cược với emoji
        keyboard = [
            [InlineKeyboardButton("💵 *10 điểm*", callback_data='bet_10')],
            [InlineKeyboardButton("💎 *20 điểm*", callback_data='bet_20')],
            [InlineKeyboardButton("💰 *50 điểm*", callback_data='bet_50')],
            [InlineKeyboardButton("🔙 *Menu chính*", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('💰 **Chọn mức cược điểm giả của bạn:**\n*(Càng cao càng hồi hộp!)*', parse_mode='Markdown', reply_markup=reply_markup)
        return

    elif query.data.startswith('bet_'):
        bet = int(query.data.split('_')[1])
        balance = user_scores[user_id]['balance']
        if balance < bet:
            keyboard = get_menu_keyboard()
            await query.edit_message_text(f'❌ **Không đủ điểm!**\nCân bằng hiện tại: *{balance} điểm*\nHãy cược ít hơn nhé! 😅', parse_mode='Markdown', reply_markup=keyboard)
            return
        context.user_data['bet'] = bet
        keyboard = [
            [InlineKeyboardButton("💰 **TÀI (11-17)**", callback_data='tai')],
            [InlineKeyboardButton("💸 **XỈU (4-10)**", callback_data='xiu')],
            [InlineKeyboardButton("🔙 *Menu chính*", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f'🤔 **Cược {bet} điểm rồi!**\n*Bạn đoán Tài hay Xỉu?* 🎲', parse_mode='Markdown', reply_markup=reply_markup)
        return

    elif query.data in ['tai', 'xiu']:
        bet = context.user_data.get('bet', 10)
        # Lắc xúc xắc với animation text
        await query.edit_message_text('🎲 **Đang lắc...** 🎲🎲🎲\n*Chờ tí nhé!*')
        # Giả lập delay (thực tế dùng asyncio.sleep nếu cần)
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        dice3 = random.randint(1, 6)
        total = dice1 + dice2 + dice3
        result = "TÀI 💰" if total >= 11 else "XỈU 💸"
        user_guess = "TÀI" if query.data == 'tai' else "XỈU"

        # Kết quả
        win = user_guess == result.replace(" 💰", "").replace(" 💸", "")
        if win:
            user_scores[user_id]['wins'] += 1
            user_scores[user_id]['balance'] += bet * 2  # Thắng gấp đôi vui hơn
            status = "🎉 **Bạn thắng lớn!** +{bet*2} điểm"
        else:
            user_scores[user_id]['losses'] += 1
            user_scores[user_id]['balance'] -= bet
            status = "😢 **Bạn thua rồi...** -{bet} điểm"

        # Lưu lịch sử
        history_entry = f"*{dice1}*+*{dice2}*+*{dice3}*=**{total}** ({result}) - {status}"
        user_history[user_id].append(history_entry)
        if len(user_history[user_id]) > 5:
            user_history[user_id].pop(0)

        balance_new = user_scores[user_id]['balance']
        message = f"""
🎲 **Kết quả lắc xúc xắc:** 🎲

*dice1* + *dice2* + *dice3* = **{total}** ({result})

{status}

💰 **Cân bằng mới:** *{balance_new} điểm*

Chơi tiếp hay về menu?
        """
        keyboard = [
            [InlineKeyboardButton("🎲 *Chơi lại ngay*", callback_data='play')],
            [InlineKeyboardButton("🔙 *Menu chính*", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'score':
        score = user_scores[user_id]
        message = f"""
📊 **Điểm số cá nhân của bạn:**

• **Thắng:** {score['wins']} ván
• **Thua:** {score['losses']} ván
• **Cân bằng:** *{score['balance']} điểm*

Tỷ lệ thắng: *{score['wins'] / (score['wins'] + score['losses'] + 1) * 100:.1f}%* (nếu có ván)

🔙 *Menu chính*
        """
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'history':
        hist = user_history[user_id]
        if not hist:
            message = "📜 **Chưa có lịch sử chơi nào!**\nHãy thử ván đầu tiên đi 🎲\n\n🔙 *Menu chính*"
        else:
            hist_text = '\n'.join(f"• {h}" for h in hist[-5:])
            message = f"📜 **Lịch sử 5 ván gần nhất:**\n\n{hist_text}\n\n🔙 *Menu chính*"
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'top':
        # Top 3 giả (dựa trên wins, chỉ demo – thực tế dùng DB)
        top_users = sorted(user_scores.items(), key=lambda x: x[1]['wins'], reverse=True)[:3]
        if not top_users:
            message = "🏆 **Chưa có top nào!**\nBạn là số 1 đầu tiên? Chơi đi! 🎲\n\n🔙 *Menu chính*"
        else:
            top_text = '\n'.join(f"{i+1}. User {uid}: {score['wins']} thắng" for i, (uid, score) in enumerate(top_users))
            message = f"🏆 **Top 3 người chơi (dựa trên thắng):**\n\n{top_text}\n\n🔙 *Menu chính*"
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'help':
        message = """
ℹ️ **Hướng dẫn chơi Tài Xỉu:**

• Chọn *mức cược* (10/20/50 điểm giả).
• Đố *Tài* (tổng 11-17) hoặc *Xỉu* (4-10).
• Bot *lắc 3 xúc xắc* ngẫu nhiên (1-6 mỗi cái).
• **Thắng:** + gấp đôi cược. **Thua:** - cược.
• Xem *điểm số*, *lịch sử*, *top* để khoe bạn bè.
• Chỉ vui giải trí, không cược thật! 😊

🔙 *Menu chính*
        """
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'reset':
        user_scores[user_id] = {'wins': 0, 'losses': 0, 'balance': 100}
        user_history[user_id] = []
        message = "🔄 **Điểm số đã reset!**\nCân bằng mới: *100 điểm*\nChơi lại từ đầu nhé! 🎲\n\n🔙 *Menu chính*"
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'menu':
        keyboard = [
            [InlineKeyboardButton("🎲 *Chơi Tài Xỉu*", callback_data='play')],
            [InlineKeyboardButton("📊 *Điểm số của tôi*", callback_data='score')],
            [InlineKeyboardButton("📜 *Lịch sử chơi*", callback_data='history')],
            [InlineKeyboardButton("🏆 *Top người chơi*", callback_data='top')],
            [InlineKeyboardButton("ℹ️ *Hướng dẫn*", callback_data='help')],
            [InlineKeyboardButton("🔄 *Reset điểm*", callback_data='reset')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('🎉 **Menu chính - Chọn nhé!** 🎲', parse_mode='Markdown', reply_markup=reply_markup)

def get_menu_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 *Menu chính*", callback_data='menu')]]
    return InlineKeyboardMarkup(keyboard)

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    print("Bot Tài Xỉu đẹp lung linh đang chạy... Nhấn Ctrl+C để dừng.")
    application.run_polling()

if __name__ == '__main__':
    main()