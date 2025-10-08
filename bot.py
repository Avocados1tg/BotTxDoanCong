import logging
import os
import asyncio
import random
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Lấy token từ biến môi trường (Railway)
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError('BOT_TOKEN không được set! Hãy thêm vào biến môi trường.')

# Bật logging để debug (tùy chọn)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Tùy chỉnh: Danh sách emoji Dice (thêm/bớt tùy ý)
DICE_EMOJIS = ['🎲', '🎯']  # '🏀' value chỉ 1-5, tránh dùng nếu muốn 1-6 đầy đủ

# Tùy chỉnh: URL hoặc file_id GIF animation (thay bằng file_id thật để ổn định)
CUSTOM_GIF_URL = 'https://media.tenor.com/5oN8f0y3y0AAAAAC/dice-roll.gif'  # Ví dụ URL; tốt hơn dùng file_id

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Chào mừng! Bot TX với animation Dice nâng cao!\nGõ /play để bắt đầu. 🎲')

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hãy chọn cược: "Tài" hoặc "Xỉu" (gõ chính xác nhé)!')
    context.user_data['waiting_bet'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_bet'):
        bet = update.message.text.strip().lower()
        if bet in ['tài', 'xỉu']:
            # Bắt đầu chat action "đang ghi animation"
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VIDEO)
            
            # Tùy chọn: Gửi custom GIF trước (nâng cao)
            try:
                await context.bot.send_animation(
                    chat_id=update.effective_chat.id,
                    animation=CUSTOM_GIF_URL,  # Hoặc file_id: 'file_id_here'
                    caption='Đang lắc xúc xắc tùy chỉnh... ⏳'
                )
                use_dice = False  # Nếu dùng GIF, random value thủ công
            except Exception:
                await update.message.reply_text('Fallback về Dice built-in...')
                use_dice = True
            
            if use_dice:
                # Gửi 3 Dice animation nâng cao
                dice_values = []
                for i in range(3):
                    emoji = random.choice(DICE_EMOJIS)
                    dice_msg = await context.bot.send_dice(
                        chat_id=update.effective_chat.id,
                        emoji=emoji
                    )
                    await asyncio.sleep(0.5)  # Delay ngắn cho mượt
                    dice_values.append(dice_msg.dice.value)
            else:
                # Random thủ công nếu dùng GIF (3 xúc xắc 1-6)
                dice_values = [random.randint(1, 6) for _ in range(3)]
            
            # Tính tổng
            total = sum(dice_values)
            result = 'Tài' if total >= 11 else 'Xỉu'
            win = (bet == result.lower())
            
            # Message kết quả (bỏ bộ ba)
            message = f'🎲 Xúc xắc: {dice_values[0]}, {dice_values[1]}, {dice_values[2]}\nTổng: {total}\nKết quả: {result}\n'
            if win:
                message += 'Bạn thắng! 🎉 Chơi tiếp /play'
            else:
                message += 'Bạn thua! 😔 Thử lại /play'
            
            await update.message.reply_text(message)
            del context.user_data['waiting_bet']
        else:
            await update.message.reply_text('Sai rồi! Hãy gõ "Tài" hoặc "Xỉu" thôi.')

def main():
    # Tạo application
    application = Application.builder().token(TOKEN).build()
    
    # Thêm handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('play', play))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Chạy bot
    print('Bot đang chạy với animation Dice nâng cao (bỏ bộ ba)...')
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()