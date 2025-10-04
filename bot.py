import telebot
import os
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Lấy token từ biến môi trường (environment variable) trên Railway
BOT_TOKEN = os.getenv('TOKEN')

# Kiểm tra nếu token không được set
if not BOT_TOKEN:
    raise ValueError("TOKEN chưa được thiết lập trong biến môi trường!")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    btn_play = InlineKeyboardButton("🎲 Chơi Tài Xỉu ngay!", callback_data="play")
    markup.add(btn_play)
    
    bot.reply_to(message, "Chào! Tôi là bot Tài Xỉu. Nhấn nút bên dưới để bắt đầu chơi! ✨", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "play")
def handle_play_callback(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Thêm animation loading
    bot.send_chat_action(chat_id, 'typing')
    loading_msg = bot.send_message(chat_id, "Đang lắc xúc xắc... ⏳🎲")
    time.sleep(2)  # Đợi animation loading
    
    # Xóa loading message để sạch chat
    bot.delete_message(chat_id, loading_msg.message_id)
    
    # Gửi xúc xắc 1 với animation và delay
    bot.send_chat_action(chat_id, 'upload_photo')
    msg1 = bot.send_dice(chat_id, emoji='🎲')
    value1 = msg1.dice.value
    time.sleep(1)
    
    # Gửi xúc xắc 2 với animation và delay
    bot.send_chat_action(chat_id, 'upload_photo')
    msg2 = bot.send_dice(chat_id, emoji='🎲')
    value2 = msg2.dice.value
    time.sleep(1)
    
    # Gửi xúc xắc 3 với animation và delay
    bot.send_chat_action(chat_id, 'upload_photo')
    msg3 = bot.send_dice(chat_id, emoji='🎲')
    value3 = msg3.dice.value
    time.sleep(1)
    
    total = value1 + value2 + value3
    
    # Check for triple (all same) first
    if value1 == value2 == value3:
        result = "Xổ ba - Người chơi ăn gấp đôi! 🎉💰"
    # Determine result: Tài (11-18), Xỉu (3-10)
    elif total >= 11:
        result = "Tài! 🔥"
    else:
        result = "Xỉu! ❄️"
    
    # Gửi kết quả với emoji animation và nút chơi lại
    markup = InlineKeyboardMarkup()
    btn_play_again = InlineKeyboardButton("🎲 Chơi lại!", callback_data="play")
    markup.add(btn_play_again)
    
    bot.send_message(chat_id, f"🎲 Kết quả: {value1} + {value2} + {value3} = {total} -> {result} 🎲\nHãy thử lại nhé! ✨", reply_markup=markup)
    
    # Xóa nút cũ nếu cần (tùy chọn)
    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Chào! Tôi là bot Tài Xỉu. Nhấn nút bên dưới để bắt đầu chơi! ✨")

@bot.message_handler(commands=['taixiu'])
def taixiu(message):
    # Giữ nguyên command cũ cho tương thích
    handle_play_callback(type('obj', (object,), {'data': 'play', 'message': message})())

# Start the bot
bot.polling()