import os, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

users = {}
pending_bet = {}

def get_balance(user_id):
    return users.get(user_id, 1000)

# 🎲 Lệnh bắt đầu tài xỉu
async def tx(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    balance = get_balance(user_id)

    keyboard = [
        [InlineKeyboardButton("🎲 Tài (11-18)", callback_data="Tai"),
         InlineKeyboardButton("🎲 Xỉu (3-10)", callback_data="Xiu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 Xin chào *{user.first_name}*!\n\n"
        f"💰 Số dư hiện tại: *{balance} xu*\n\n"
        f"👉 Hãy chọn Tài hoặc Xỉu để bắt đầu đặt cược:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ⏳ Khi chọn Tài/Xỉu
async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    choice = query.data
    user_id = query.from_user.id
    pending_bet[user_id] = choice

    await query.edit_message_text(
        text=f"✅ Bạn đã chọn *{choice}*.\n"
             f"💸 Nhập số tiền muốn cược:",
        parse_mode="Markdown"
    )

# 🎰 Xử lý đặt cược
async def handle_bet(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    balance = get_balance(user_id)

    if user_id not in pending_bet:
        return

    try:
        bet = int(update.message.text)
    except:
        await update.message.reply_text("⚠️ Vui lòng nhập số tiền hợp lệ.")
        return

    if bet <= 0:
        await update.message.reply_text("⚠️ Số tiền phải lớn hơn 0!")
        return
    if bet > balance:
        await update.message.reply_text(f"❌ Số dư không đủ! Bạn chỉ có {balance} xu.")
        return

    dice = [random.randint(1,6) for _ in range(3)]
    total = sum(dice)
    result = "Tai" if total >= 11 else "Xiu"

    choice = pending_bet[user_id]
    del pending_bet[user_id]

    if choice == result:
        balance += bet
        outcome = f"🎉 Bạn *THẮNG*! +{bet} xu"
    else:
        balance -= bet
        outcome = f"💀 Bạn *THUA*! -{bet} xu"

    users[user_id] = balance

    await update.message.reply_text(
        f"🎲 Kết quả: {dice[0]} + {dice[1]} + {dice[2]} = *{total}*\n"
        f"👉 Kết quả cuối: *{result}*\n\n"
        f"📌 Bạn chọn: *{choice}*\n"
        f"{outcome}\n\n"
        f"💰 Số dư mới: *{balance} xu*",
        parse_mode="Markdown"
    )

# 💵 Nạp tiền
async def nap(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("💳 Dùng: `/nap <sotien>`", parse_mode="Markdown")
        return
    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("⚠️ Số tiền không hợp lệ.")
        return

    if amount <= 0:
        await update.message.reply_text("⚠️ Số tiền phải lớn hơn 0!")
        return

    users[user_id] = get_balance(user_id) + amount
    await update.message.reply_text(f"💳 Bạn đã *NẠP* {amount} xu.\n💰 Số dư mới: {users[user_id]}")

# 💵 Rút tiền
async def rut(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("🏧 Dùng: `/rut <sotien>`", parse_mode="Markdown")
        return
    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("⚠️ Số tiền không hợp lệ.")
        return

    balance = get_balance(user_id)
    if amount <= 0:
        await update.message.reply_text("⚠️ Số tiền phải lớn hơn 0!")
        return
    if amount > balance:
        await update.message.reply_text(f"❌ Không đủ xu để rút. Bạn có {balance}.")
        return

    users[user_id] = balance - amount
    await update.message.reply_text(f"🏧 Bạn đã *RÚT* {amount} xu.\n💰 Số dư còn lại: {users[user_id]}")

# 📊 Xem số dư
async def balance(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    bal = get_balance(user_id)
    await update.message.reply_text(f"👤 Người chơi: *{user.first_name}*\n💰 Số dư: *{bal} xu*", parse_mode="Markdown")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("tx", tx))
    app.add_handler(CommandHandler("nap", nap))
    app.add_handler(CommandHandler("rut", rut))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bet))
    app.run_polling()

if __name__ == "__main__":
    main()
