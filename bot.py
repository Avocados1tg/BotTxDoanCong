import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ========== CONFIG ==========
TOKEN = "8478512062:AAHtkO3agXgg1JPMloOaMLbd0xmSGF-e_o4"
user_balance = {}

# ========== LOG ==========
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== HẰNG SỐ ==========
CHON_CONVAT, DAT_TIEN = range(2)
bau_cua_icons = ["🐟 Cá", "🦀 Cua", "🦌 Nai", "🐓 Gà", "🦁 Hổ", "🥒 Bầu"]

# ========== HÀM TIỆN ÍCH ==========
def get_balance(user_id):
    if user_id not in user_balance:
        user_balance[user_id] = 1000
    return user_balance[user_id]

def update_balance(user_id, amount):
    user_balance[user_id] = get_balance(user_id) + amount

# ========== LỆNH ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bal = get_balance(user_id)
    keyboard = [
        [InlineKeyboardButton("🎲 Tài Xỉu", callback_data="play_tx")],
        [InlineKeyboardButton("🦀 Bầu Cua", callback_data="play_bc")],
        [InlineKeyboardButton("💰 Xem số dư", callback_data="balance")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"👋 Xin chào {update.effective_user.first_name}!\n"
        f"Bạn hiện có {bal}💵.\nChọn trò chơi nhé:",
        reply_markup=reply_markup
    )

# ========== TÀI XỈU ==========
async def play_tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "Tài 🎲" if total >= 11 else "Xỉu 🎲"

    update_balance(user_id, 100)  # mặc định thưởng chơi demo
    bal = get_balance(user_id)

    keyboard = [
        [InlineKeyboardButton("🔄 Chơi lại", callback_data="play_tx")],
        [InlineKeyboardButton("💰 Xem số dư", callback_data="balance")],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
    ]
    await query.edit_message_text(
        f"🎲 Kết quả: {dice} = {total} → {result}\n"
        f"💰 Số dư: {bal}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ========== BẦU CUA ==========
async def play_bc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🐟 Cá", callback_data="bc_0"), InlineKeyboardButton("🦀 Cua", callback_data="bc_1")],
        [InlineKeyboardButton("🦌 Nai", callback_data="bc_2"), InlineKeyboardButton("🐓 Gà", callback_data="bc_3")],
        [InlineKeyboardButton("🦁 Hổ", callback_data="bc_4"), InlineKeyboardButton("🥒 Bầu", callback_data="bc_5")]
    ]
    await query.edit_message_text(
        "🎲 Chọn con vật bạn muốn đặt cược:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHON_CONVAT

async def chon_convat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["convat"] = int(query.data.split("_")[1])
    await query.edit_message_text(
        f"Bạn đã chọn {bau_cua_icons[context.user_data['convat']]}\n💵 Nhập số tiền cược:"
    )
    return DAT_TIEN

async def dat_tien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        bet = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ!")
        return DAT_TIEN

    if bet <= 0 or bet > get_balance(user_id):
        await update.message.reply_text("❌ Tiền cược không hợp lệ!")
        return DAT_TIEN

    roll = [random.randint(0, 5) for _ in range(3)]
    chosen = context.user_data["convat"]

    if chosen in roll:
        win = bet * roll.count(chosen)
        update_balance(user_id, win)
        result_text = f"🎉 Bạn thắng {win}💵!"
    else:
        update_balance(user_id, -bet)
        result_text = f"😢 Bạn thua {bet}💵."

    bal = get_balance(user_id)
    icons = [bau_cua_icons[r] for r in roll]

    keyboard = [
        [InlineKeyboardButton("🔄 Chơi lại", callback_data="play_bc")],
        [InlineKeyboardButton("💰 Xem số dư", callback_data="balance")],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
    ]
    await update.message.reply_text(
        f"🎲 Kết quả xúc xắc: {icons}\n{result_text}\n💰 Số dư: {bal}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# ========== MENU & BAL ==========
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bal = get_balance(query.from_user.id)
    await query.edit_message_text(f"💰 Số dư hiện tại: {bal}💵")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

# ========== MAIN ==========
def main():
    app = Application.builder().token(TOKEN).build()

    conv_bc = ConversationHandler(
        entry_points=[CallbackQueryHandler(play_bc, pattern="^play_bc$")],
        states={
            CHON_CONVAT: [CallbackQueryHandler(chon_convat, pattern="^bc_")],
            DAT_TIEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, dat_tien)]
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_bc)
    app.add_handler(CallbackQueryHandler(play_tx, pattern="^play_tx$"))
    app.add_handler(CallbackQueryHandler(balance, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(menu, pattern="^menu$"))

    app.run_polling()

if __name__ == "__main__":
    main()
