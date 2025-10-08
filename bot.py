import logging
import os
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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

# Tạo menu chính (ReplyKeyboard)
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🎲 Chơi")],
        [KeyboardButton("💰 Số dư")],
        [KeyboardButton("🔄 Reset")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'balance' not in context.user_data:
        context.user_data['balance'] = DEFAULT_BALANCE
    reply_markup = get_main_keyboard()
    await update.message.reply_text(
        f'Chào mừng! Bot TX với nút bấm dễ dùng (tỷ lệ 1:0.9).\nSố dư: {int(context.user_data["balance"])} VND 💰\nBấm nút dưới để chơi!',
        reply_markup=reply_markup
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balance = context.user_data.get('balance', DEFAULT_BALANCE)
    reply_markup = get_main_keyboard()
    await update.message.reply_text(f'Số dư hiện tại: {int(balance)} VND 💰', reply_markup=reply_markup)

async def reset_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['balance'] = DEFAULT_BALANCE
    reply_markup = get_main_keyboard()
    await update.message.reply_text(f'Đã reset số dư về {int(DEFAULT_BALANCE)} VND! 🎉', reply_markup=reply_markup)

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'balance' not in context.user_data:
        context.user_data['balance'] = DEFAULT_BALANCE
    balance = context.user_data['balance']
    if balance <= 0:
        reply_markup = get_main_keyboard()
        await update.message.reply_text('Hết tiền rồi! Bấm 🔄 Reset để chơi tiếp.', reply_markup=reply_markup)
        return
    
    # Tạo nút Inline cho Tài/Xỉu
    keyboard = [
        [InlineKeyboardButton("Tài 💰", callback_data='bet_tai')],
        [InlineKeyboardButton("Xỉu 🎲", callback_data='bet_xiu')]
    ]
    reply_markup_inline = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Chọn cược của bạn:', reply_markup=reply_markup_inline)
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
    text = update.message.text.strip()
    
    # Xử lý nút menu chính
    if text == "🎲 Chơi":
        await play(update, context)
    elif text == "💰 Số dư":
        await balance(update, context)
    elif text == "🔄 Reset":
        await reset_balance(update, context)
    
    # Xử lý tiền cược (nếu đang chờ)
    elif context.user_data.get('waiting_amount'):
        try:
            amount = float(update.message.text.strip())
            balance = context.user_data['balance']
            if amount <= 0 or amount > balance:
                reply_markup = get_main_keyboard()
                await update.message.reply_text(f'Cược không hợp lệ! Phải từ 1 đến {int(balance)} VND.', reply_markup=reply_markup)
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
            reply_markup = get_main_keyboard()
            if win:
                win_amount = amount * 0.9
                context.user_data['balance'] += amount + win_amount  # + gốc + thắng (1:0.9)
                message += f'Bạn thắng! +{int(win_amount)} VND\nSố dư mới: {int(context.user_data["balance"])} VND 🎉'
            else:
                message += f'Bạn thua! -{int(amount)} VND\nSố dư mới: {int(context.user_data["balance"])} VND 😔'
            message += '\nBấm nút dưới để tiếp tục!'
            
            await update.message.reply_text(message, reply_markup=reply_markup)
            del context.user_data['waiting_amount']
            del context.user_data['bet']
        except ValueError:
            reply_markup = get_main_keyboard()
            await update.message.reply_text('Sai! Gõ số hợp lệ cho tiền cược (ví dụ: 1000).', reply_markup=reply_markup)

def main():
    application = Application.builder().token(TOKEN).build()
    
    # Command handlers (vẫn giữ cho tương thích)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_callback, pattern='^bet_'))
    
    # Message handler cho nút và text
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print('Bot đang chạy với menu nút bấm đầy đủ...')
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()