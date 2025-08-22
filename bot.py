import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from keep_alive import keep_alive

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Lưu số dư user (tạm thời trong RAM)
so_du = {}

# Hàm tung xúc xắc
def lac_xuc_xac():
    dice = [random.randint(1, 6) for _ in range(3)]
    tong = sum(dice)
    ket_qua = "Tai" if tong >= 11 else "Xiu"
    return dice, tong, ket_qua

# Lấy số dư
def get_balance(user_id):
    return so_du.get(user_id, 0)

# /tx -> bắt đầu chơi
async def tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in so_du:
        so_du[user_id] = 0  # mặc định 0 tiền

    keyboard = [
        [InlineKeyboardButton("Tai 🎲", callback_data="tai"),
         InlineKeyboardButton("Xiu 🎲", callback_data="xiu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🎲 Tai Xiu Game 🎲\nSo du hien tai: {get_balance(user_id)} xu\n\nChon Tai hoac Xiu:",
        reply_markup=reply_markup
    )

# Nút chọn Tai/Xiu
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # Nếu chưa có số dư thì auto tạo
    if user_id not in so_du:
        so_du[user_id] = 0

    # Mặc định đặt 100 xu mỗi ván
    bet = 100
    if so_du[user_id] < bet:
        await query.edit_message_text("❌ Ban khong du tien! Hay /nap <so_tien> truoc.")
        return

    lua_chon = query.data.capitalize()
    dice, tong, ket_qua = lac_xuc_xac()

    msg = f"🎲 Ket qua: {dice[0]} + {dice[1]} + {dice[2]} = {tong} ({ket_qua})\n"

    if lua_chon == ket_qua:
        so_du[user_id] += bet
        msg += f"👉 Ban CHIEN THANG! +{bet} xu\n"
    else:
        so_du[user_id] -= bet
        msg += f"👉 Ban THUA roi! -{bet} xu\n"

    msg += f"💰 So du hien tai: {so_du[user_id]} xu\n\n"

    # Thêm nút chơi tiếp
    keyboard = [
        [InlineKeyboardButton("Choi tiep Tai 🎲", callback_data="tai"),
         InlineKeyboardButton("Choi tiep Xiu 🎲", callback_data="xiu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=msg, reply_markup=reply_markup)

# /nap <so_tien>
async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❌ Dung lenh: /nap <so_tien>")
        return
    tien = int(context.args[0])
    so_du[user_id] = so_du.get(user_id, 0) + tien
    await update.message.reply_text(f"✅ Nap thanh cong {tien} xu. So du: {so_du[user_id]} xu")

# /rut <so_tien>
async def rut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❌ Dung lenh: /rut <so_tien>")
        return
    tien = int(context.args[0])
    if so_du.get(user_id, 0) < tien:
        await update.message.reply_text("❌ Khong du tien de rut!")
        return
    so_du[user_id] -= tien
    await update.message.reply_text(f"✅ Rut thanh cong {tien} xu. So du: {so_du[user_id]} xu")

# /balance
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"💰 So du cua ban: {get_balance(user_id)} xu")

# Chạy bot
def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("tx", tx))
    app.add_handler(CommandHandler("nap", nap))
    app.add_handler(CommandHandler("rut", rut))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == "__main__":
    main()
