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

# Tùy chỉnh: Danh sách emoji Dice (mở rộng: random 3 loại)
DICE_EMOJIS = ['🎲', '⚽', '🏀']

# Tùy chỉnh: GIF animation mới (lắc 3 dice classic từ Giphy - khác với cái cũ)
CUSTOM_GIF_URL = 'https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif'

# Sticker win/lose (placeholder - thay bằng file_id thật!)
WIN_STICKER = 'CAACAgIAAxkBAAIB...win_celebration_file_id'  # Ví dụ sticker thắng
LOSE_STICKER = 'CAACAgIAAxkBAAIB...sad_lose_file_id'  # Ví dụ sticker thua

# Balance mặc định
DEFAULT_BALANCE = 100000.0  # 100.000 VND

# Preset amounts cho nút cược
PRESET_AMOUNTS = [1000, 5000, 10000, 50000]  # Thêm/bớt tùy ý

# Tạo menu chính (ReplyKeyboard)
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🎲 Chơi")],
        [KeyboardButton("💰 Số dư")],
        [KeyboardButton("🔄 Reset")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# Tạo nút preset cược dựa trên balance
def get_amount_keyboard(balance):
    keyboard = []
    for amt in PRESET_AMOUNTS:
        if amt <= balance:
            keyboard.append([InlineKeyboardButton(f"{amt:,} VND", callback_data=f'amount_{amt}')])
    keyboard.append([InlineKeyboardButton("All-in 💥", callback_data='amount_all')])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['balance'] = DEFAULT_BALANCE  # Force set để tránh 0
    logging.info(f'Init balance cho user {update.effective_user.id}: {context.user_data["balance"]}')
    reply_markup = get_main_keyboard()
    await update.message.reply_text(
        f'Chào mừng! Bot TX với animation tùy chỉnh đầy đủ (tỷ lệ 1:0.9).\nSố dư: {int(context.user_data["balance"]):,} VND 💰\nBấm nút dưới để chơi!',
        reply_markup=reply_markup
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'balance' not in context.user_data:
        context.user_data['balance'] = DEFAULT_BALANCE  # Fix nếu thiếu
    balance = context.user_data['balance']
    logging.info(f'Check balance cho user {update.effective_user.id}: {balance}')
    reply_markup = get_main_keyboard()
    await update.message.reply_text(f'Số dư hiện tại: {int(balance):,} VND 💰', reply_markup=reply_markup)

async def reset_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['balance'] = DEFAULT_BALANCE  # Force set
    logging.info(f'Reset balance cho user {update.effective_user.id}: {context.user_data["balance"]}')
    reply_markup = get_main_keyboard()
    await update.message.reply_text(f'Đã reset số dư về {int(DEFAULT_BALANCE):,} VND! 🎉', reply_markup=reply_markup)

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'balance' not in context.user_data:
        context.user_data['balance'] = DEFAULT_BALANCE
    balance = context.user_data['balance']
    logging.info(f'Play check balance cho user {update.effective_user.id}: {balance}')
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
    await update.message.reply_text('Chọn cược của bạn:', reply_markup=reply_markup_inline)  # Không cần ReplyKeyboard ở đây, sẽ có ở bước sau

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('bet_'):
        # Xử lý chọn Tài/Xỉu
        bet = 'tài' if query.data == 'bet_tai' else 'xỉu'
        context.user_data['bet'] = bet
        balance = context.user_data['balance']
        amount_keyboard = get_amount_keyboard(balance)
        reply_markup_main = get_main_keyboard()  # Thêm nút dưới cho message edit
        await query.edit_message_text(
            f'Bạn chọn {bet.title()}. Chọn số tiền cược sẵn:\nSố dư: {int(balance):,} VND',
            reply_markup=amount_keyboard  # Inline trên
            # ReplyKeyboard dưới sẽ tự hiện nếu đã set trước đó, nhưng để chắc, có thể gửi message riêng nếu cần
        )
        # Gửi message riêng với ReplyKeyboard để đảm bảo nút dưới hiện (fix theo ảnh)
        await query.message.reply_text('Bấm nút dưới để tiếp tục sau khi chọn cược!', reply_markup=reply_markup_main)
    
    elif query.data.startswith('amount_'):
        # Xử lý chọn amount
        if not context.user_data.get('bet'):
            await query.answer('Chưa chọn Tài/Xỉu! Bấm /play lại.')
            return
        
        bet = context.user_data['bet']
        balance = context.user_data['balance']
        
        if query.data == 'amount_all':
            amount = balance
        else:
            amount = float(query.data.split('_')[1])
        
        if amount > balance or amount <= 0:
            await query.answer('Số tiền không hợp lệ!')
            return
        
        # Trừ tiền cược trước
        context.user_data['balance'] -= amount
        logging.info(f'Cược {amount} cho user {query.from_user.id}, balance mới: {context.user_data["balance"]}')
        
        # Text animation: Loading message
        loading_msg = await context.bot.send_message(chat_id=query.message.chat_id, text='⏳ Đang lắc... Lắc lắc! 🎲')
        await asyncio.sleep(2)  # Chờ 2s cho hiệu ứng
        await loading_msg.delete()  # Xóa loading
        
        # Bắt đầu chat action
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.RECORD_VIDEO)
        
        # GIF tùy chỉnh mới
        try:
            await context.bot.send_animation(
                chat_id=query.message.chat_id,
                animation=CUSTOM_GIF_URL,
                caption='Đang lắc xúc xắc tùy chỉnh... ⏳'
            )
            use_dice = False
            logging.info('GIF mới gửi thành công')
        except Exception as e:
            logging.info(f'GIF lỗi: {e}, fallback Dice')
            use_dice = True
        
        if use_dice:
            # Dice animation với emoji random mở rộng
            dice_values = []
            num_dice = 3  # Số Dice (dễ chỉnh)
            for _ in range(num_dice):
                emoji = random.choice(DICE_EMOJIS)
                dice_msg = await context.bot.send_dice(
                    chat_id=query.message.chat_id,
                    emoji=emoji
                )
                await asyncio.sleep(0.5)  # Delay mượt
                dice_values.append(dice_msg.dice.value)
        else:
            # Random thủ công nếu dùng GIF
            dice_values = [random.randint(1, 6) for _ in range(3)]
        
        total = sum(dice_values)
        result = 'Tài' if total >= 11 else 'Xỉu'
        win = (bet == result.lower())
        
        message = f'🎲 Xúc xắc: {dice_values[0]}, {dice_values[1]}, {dice_values[2]}\nTổng: {total}\nKết quả: {result}\n'
        reply_markup = get_main_keyboard()
        if win:
            win_amount = amount * 0.9
            context.user_data['balance'] += amount + win_amount  # + gốc + thắng (1:0.9)
            message += f'Bạn thắng! +{int(win_amount):,} VND\nSố dư mới: {int(context.user_data["balance"]):,} VND 🎉'
            # Gửi sticker win
            try:
                await context.bot.send_sticker(chat_id=query.message.chat_id, sticker=WIN_STICKER)
            except Exception:
                logging.info('Sticker win lỗi, bỏ qua')
        else:
            message += f'Bạn thua! -{int(amount):,} VND\nSố dư mới: {int(context.user_data["balance"]):,} VND 😔'
            # Gửi sticker lose
            try:
                await context.bot.send_sticker(chat_id=query.message.chat_id, sticker=LOSE_STICKER)
            except Exception:
                logging.info('Sticker lose lỗi, bỏ qua')
        message += '\nBấm nút dưới để tiếp tục!'
        
        await query.message.reply_text(message, reply_markup=reply_markup)
        del context.user_data['bet']

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Xử lý nút menu chính
    if text == "🎲 Chơi":
        await play(update, context)
    elif text == "💰 Số dư":
        await balance(update, context)
    elif text == "🔄 Reset":
        await reset_balance(update, context)

def main():
    application = Application.builder().token(TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler('start', start))
    
    # Callback cho nút (bet_ và amount_)
    application.add_handler(CallbackQueryHandler(button_callback, pattern='^(bet_|amount_)'))
    
    # Message handler cho nút menu
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print('Bot đang chạy với fix balance, nút dưới đầy đủ và GIF mới...')
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()