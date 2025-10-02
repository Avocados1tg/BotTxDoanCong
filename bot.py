import logging
import random
import os
import asyncio  # Thêm để delay animation
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Lấy token từ env
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    print("Lỗi: Không tìm thấy TELEGRAM_BOT_TOKEN. Đặt vào Railway!")
    exit(1)

# Dữ liệu user
user_scores = defaultdict(lambda: {'wins': 0, 'losses': 0, 'balance': 100})
user_history = defaultdict(list)

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🎲 Chơi Tài Xỉu", callback_data='play')],
        [InlineKeyboardButton("📊 Điểm số", callback_data='score')],
        [InlineKeyboardButton("📜 Lịch sử", callback_data='history')],
        [InlineKeyboardButton("🏆 Top chơi", callback_data='top')],
        [InlineKeyboardButton("ℹ️ Hướng dẫn", callback_data='help')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_msg = """
🔥 **Bot Tài Xỉu Siêu Đẹp!** 🎲

Chào anh! Cân bằng khởi đầu: **100 điểm giả** 💰
Chọn nút để chơi, chỉ vui thôi nhé! 😎
    """
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == 'play':
        keyboard = [
            [InlineKeyboardButton("💵 10 điểm", callback_data='bet_10'), InlineKeyboardButton("💎 20 điểm", callback_data='bet_20')],
            [InlineKeyboardButton("💰 50 điểm", callback_data='bet_50')],
            [InlineKeyboardButton("🔙 Menu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('💰 **Chọn mức cược:**\n*(Càng lớn càng kịch tính!)* 🎰', parse_mode='Markdown', reply_markup=reply_markup)
        return

    elif query.data.startswith('bet_'):
        bet = int(query.data.split('_')[1])
        balance = user_scores[user_id]['balance']
        if balance < bet:
            keyboard = get_menu_keyboard()
            await query.edit_message_text(f'❌ **Hết tiền rồi!** 😱\nCòn *{balance} điểm*. Cược nhỏ hơn đi!', parse_mode='Markdown', reply_markup=keyboard)
            return
        context.user_data['bet'] = bet
        keyboard = [
            [InlineKeyboardButton("💰 TÀI", callback_data='tai'), InlineKeyboardButton("💸 XỈU", callback_data='xiu')],
            [InlineKeyboardButton("🔙 Menu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f'🤔 **Cược {bet} điểm!**\n*Đoán Tài hay Xỉu?* 🎲', parse_mode='Markdown', reply_markup=reply_markup)
        return

    elif query.data in ['tai', 'xiu']:
        bet = context.user_data.get('bet', 10)
        # Gửi loading
        loading_msg = await query.message.reply_text('🎲 **Đang lắc xúc xắc...** 🌀')
        await asyncio.sleep(2)  # Delay cho animation

        # Gửi 3 xúc xắc thật (animation!)
        dice_msg1 = await context.bot.send_dice(chat_id=query.message.chat_id, emoji='🎲')
        dice_msg2 = await context.bot.send_dice(chat_id=query.message.chat_id, emoji='🎲')
        dice_msg3 = await context.bot.send_dice(chat_id=query.message.chat_id, emoji='🎲')
        dice1 = dice_msg1.dice.value
        dice2 = dice_msg2.dice.value
        dice3 = dice_msg3.dice.value
        total = dice1 + dice2 + dice3
        result = "TÀI 💰" if total >= 11 else "XỈU 💸"
        user_guess = "TÀI" if query.data == 'tai' else "XỈU"

        win = user_guess == result.replace(" 💰", "").replace(" 💸", "")
        if win:
            user_scores[user_id]['wins'] += 1
            user_scores[user_id]['balance'] += bet * 2
            status_emoji = "🎉"
            status_text = f"**Thắng lớn!** +{bet * 2} điểm 💥"
        else:
            user_scores[user_id]['losses'] += 1
            user_scores[user_id]['balance'] -= bet
            status_emoji = "😢"
            status_text = f"**Thua tiếc!** -{bet} điểm 💔"

        # Lưu lịch sử
        history_entry = f"{dice1}+{dice2}+{dice3}={total} ({result}) - {status_text}"
        user_history[user_id].append(history_entry)
        if len(user_history[user_id]) > 5:
            user_history[user_id].pop(0)

        balance_new = user_scores[user_id]['balance']
        message = f"""
{status_emoji} **Kết quả ván chơi!** {status_emoji}

🎲 **{dice1} + {dice2} + {dice3} = {total}** ({result})

{status_text}

💰 **Cân bằng:** *{balance_new} điểm*

Chơi tiếp?
        """
        keyboard = [
            [InlineKeyboardButton("🎲 Chơi lại", callback_data='play')],
            [InlineKeyboardButton("🔙 Menu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await loading_msg.delete()  # Xóa loading
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'score':
        score = user_scores[user_id]
        win_rate = (score['wins'] / (score['wins'] + score['losses'] + 1)) * 100 if (score['wins'] + score['losses']) > 0 else 0
        message = f"""
📊 **Điểm số của bạn:** 🔥

• **Thắng:** {score['wins']} ván
• **Thua:** {score['losses']} ván
• **Tỷ lệ thắng:** *{win_rate:.1f}%*
• **Cân bằng:** *{score['balance']} điểm* 💰

🔙 *Menu*
        """
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'history':
        hist = user_history[user_id]
        if not hist:
            message = "📜 **Chưa chơi ván nào!**\nThử ngay đi 🎲\n\n🔙 *Menu*"
        else:
            hist_text = '\n'.join(f"• {h}" for h in hist[-5:])
            message = f"📜 **5 ván gần nhất:** 📋\n\n{hist_text}\n\n🔙 *Menu*"
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'top':
        top_users = sorted(user_scores.items(), key=lambda x: x[1]['wins'], reverse=True)[:3]
        if not top_users:
            message = "🏆 **Top trống!**\nAnh là số 1? Chơi đi! 🎲\n\n🔙 *Menu*"
        else:
            top_text = '\n'.join(f"{i+1}. User {uid}: **{score['wins']} thắng**" for i, (uid, score) in enumerate(top_users))
            message = f"🏆 **Top 3 cao thủ:** 👑\n\n{top_text}\n\n🔙 *Menu*"
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'help':
        message = """
ℹ️ **Hướng dẫn nhanh:** 🎯

• **Chơi:** Cược điểm giả > Đoán Tài/Xỉu.
• **Xúc xắc:** Bot lăn thật (animation 🎲 x3).
• **Thắng:** + gấp đôi cược. Thua: - cược.
• **Điểm:** Giả, reset khi cần.
• Vui thôi, không cược thật! ⚠️

🔙 *Menu*
        """
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'reset':
        user_scores[user_id] = {'wins': 0, 'losses': 0, 'balance': 100}
        user_history[user_id] = []
        message = "🔄 **Reset thành công!** ✅\nCân bằng mới: *100 điểm*\nChơi lại thôi! 🎲\n\n🔙 *Menu*"
        keyboard = get_menu_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    elif query.data == 'menu':
        keyboard = [
            [InlineKeyboardButton("🎲 Chơi Tài Xỉu", callback_data='play')],
            [InlineKeyboardButton("📊 Điểm số", callback_data='score')],
            [InlineKeyboardButton("📜 Lịch sử", callback_data='history')],
            [InlineKeyboardButton("🏆 Top chơi", callback_data='top')],
            [InlineKeyboardButton("ℹ️ Hướng dẫn", callback_data='help')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('🔥 **Menu chính - Sẵn sàng chơi?** 🎰', parse_mode='Markdown', reply_markup=reply_markup)

def get_menu_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='menu')]]
    return InlineKeyboardMarkup(keyboard)

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    print("Bot Tài Xỉu đẹp + animation đang chạy... Ctrl+C dừng.")
    application.run_polling()

if __name__ == '__main__':
    main()