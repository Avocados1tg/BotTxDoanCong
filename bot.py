import logging
import os
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Lấy token từ biến môi trường (Railway)
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError('BOT_TOKEN không được set! Hãy thêm vào biến môi trường.')

# Bật logging để debug (tùy chọn)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Tùy chỉnh: Danh sách emoji Dice
DICE_EMOJIS = ['🎲', '🎯']

# Tùy chỉnh: URL hoặc file_id GIF animation
CUSTOM_GIF_URL = 'https://media.tenor.com/5oN8f0y3y0AAAAAC/dice-roll.gif'

# Balance mặc định
DEFAULT_BALANCE = 10000.0  # 10.000 VND (float để hỗ trợ thập phân)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'balance' not in context.user_data:
        context.user_data['balance'] = DEFAULT_BALANCE
    await update.message.reply_text(f'Chào mừng! Bot TX với nút bấm và tiền ảo VND (Số dư: {int(context.user_data["balance"])} VND).\nGõ /play để chơi (tỷ lệ 1:0.9). /balance xem tiền. /reset reset tiền.')

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balance = context.user_data.get('balance', DEFAULT_BALANCE)
    await update.message.reply_text(f'Số dư hiện tại: {int(balance)} VND 💰')

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['balance'] = DEFAULT_BALANCE
    await update.message.reply_text(f'Đã reset số dư về {int(DEFAULT_BALANCE)} VND!')

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'balance' not in context.user_data:
        context.user_data['balance'] = DEFAULT_BALANCE
    balance = context.user_data['balance']
    if balance <= 0:
        await update.message.reply_text('Hết tiền rồi! Gõ /reset để chơi tiếp.')
        return
    
    # Tạo nút bấm cho Tài/Xỉu
    keyboard = [
        [InlineKeyboardButton("Tài 💰", callback_data='bet_tai')],
        [InlineKeyboardButton("Xỉu 🎲", callback_data='bet_xiu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Chọn cược của bạn:', reply_markup=reply_markup)
    context.user_data['waiting_bet'] = True

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if context.user_data.get('waiting_bet'):
        bet = 'tài' if query.data == 'bet_tai' else 'xỉu'
        context.user_data['bet'] = bet
        balance = context.user_data['balance']
        await query.edit_message_text(f'Bây giờ gõ số tiền cược (VND, ví dụ: 1000). Số dư hiện tại: {int(balance)} VND')
        # Chờ message tiếp theo cho cược
        context.user_data['waiting_amount'] = True
        del context.user_data['waiting_bet']

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_amount'):
        try:
            amount = float(update.message.text.strip())
            balance = context.user_data['balance']
            if amount <= 0 or amount > balance:
                await update.message.reply_text(f'Cược không hợp lệ! Phải từ 1 đến {int(balance)} VND.')
                return
            bet = context.user_data['bet']
            
            # Trừ tiền cược trước
            context.user_data['balance'] -= amount
            
            # Bắt đầu animation
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VIDEO)
            
            try:
                await context.bot.send_animation(
                    chat_id=update.effective_chat.id,
                    animation=CUSTOM_GIF_URL,
                    caption='Đang lắc xúc xắc... ⏳'
                )
                use_dice = False
            except Exception:
                use_dice = True
            
            if use_dice:
                dice_values = []
                for _ in range(3):
                    emoji = random.choice(DICE_EMOJIS)
                    dice_msg = await context.bot.send_dice(
                        chat_id=update.effective_chat.id,
                        emoji=emoji
                    )
                    await asyncio.sleep(0.5)
                    dice_values.append(dice_msg.dice.value)
            else:
                dice_values = [random.randint(1, 6) for _ in range(3)]
            
            total = sum(dice_values)
            result = 'Tài' if total >= 11 else 'Xỉu'
            win = (bet == result.lower())
            
            message = f'🎲 Xúc xắc: {dice_values[0]}, {dice_values[1]}, {dice_values[2]}\nTổng: {total}\nKết quả: {result}\n'
            if win:
                win_amount = amount * 0.9
                context.user_data['balance'] += amount + win_amount  # + gốc + thắng (1:0.9)
                message += f'Bạn thắng! +{int(win_amount)} VND\nSố dư mới: {int(context.user_data["balance"])} VND 🎉\nChơi tiếp /play'
            else:
                message += f'Bạn thua! -{int(amount)} VND\nSố dư mới: {int(context.user_data["balance"])} VND 😔\nThử lại /play'
            
            await update.message.reply_text(message)
            del context.user_data['waiting_amount']
            del context.user_data['bet']
        except ValueError:
            await update.message.reply_text('Sai! Gõ số hợp lệ cho tiền cược (ví dụ: 1000).')

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('play', play))
    application.add_handler(CommandHandler('balance', balance))
    application.add_handler(CommandHandler('reset', reset))
    application.add_handler(CallbackQueryHandler(button_callback, pattern='^bet_'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print('Bot đang chạy với nút bấm, tiền ảo VND và tỷ lệ 1:0.9...')
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()