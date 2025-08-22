import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

BOT_TOKEN = "8478512062:AAHtkO3agXgg1JPMloOaMLbd0xmSGF-e_o4"

# ===== QUẢN LÝ NGƯỜI CHƠI =====
class Player:
    def __init__(self):
        self.balance = 1000
        self.tx_win = 0
        self.tx_lose = 0
        self.bc_win = 0
        self.bc_lose = 0

players = {}
def get_player(user_id):
    if user_id not in players:
        players[user_id] = Player()
    return players[user_id]

# ===== STATES =====
CHON_TX, DAT_TIEN_TX, CHON_CONVAT, DAT_TIEN_BC, FUN_GAME = range(5)

bau_cua_icons = ["🐟 Cá", "🦀 Cua", "🦌 Nai", "🐓 Gà", "🦁 Hổ", "🥒 Bầu"]
quick_bets = [100, 500, 1000]

# ===== MENU CHÍNH LONG LANH =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)

    keyboard = [
        [InlineKeyboardButton("🎲 Tài Xỉu", callback_data="menu_tx"),
         InlineKeyboardButton("🦀 Bầu Cua", callback_data="menu_bc")],
        [InlineKeyboardButton("🎯 Mini Game vui", callback_data="menu_fun")],
        [InlineKeyboardButton("💰 Xem số dư", callback_data="menu_balance")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"👋 Xin chào {user.first_name}!\n💰 Số dư: {player.balance} xu\nChọn trò chơi:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"👋 Xin chào {user.first_name}!\n💰 Số dư: {player.balance} xu\nChọn trò chơi:",
            reply_markup=reply_markup
        )

# ===== TÀI XỈU =====
async def menu_tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🎲 Tài", callback_data="tx_tai"),
         InlineKeyboardButton("🎲 Xỉu", callback_data="tx_xiu")],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
    ]
    await query.edit_message_text("Chọn Tài hay Xỉu:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHON_TX

async def choose_tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["tx_choice"] = query.data.split("_")[1]

    keyboard = [
        [InlineKeyboardButton(f"{b} 💵", callback_data=f"txbet_{b}") for b in quick_bets],
        [InlineKeyboardButton("✏️ Nhập số khác", callback_data="txbet_custom")],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
    ]
    await query.edit_message_text("Chọn số tiền cược:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DAT_TIEN_TX

async def input_tx_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)

    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data.startswith("txbet_") and data != "txbet_custom":
            bet = int(data.split("_")[1])
        else:
            return DAT_TIEN_TX
    else:
        try:
            bet = int(update.message.text)
        except:
            await update.message.reply_text("❌ Nhập số tiền hợp lệ!")
            return DAT_TIEN_TX

    if bet <=0 or bet>player.balance:
        await update.message.reply_text(f"❌ Tiền cược không hợp lệ! Số dư: {player.balance}")
        return DAT_TIEN_TX

    choice = context.user_data.get("tx_choice")
    dice = [random.randint(1,6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if total >= 11 else "xiu"

    if choice == result:
        player.balance += bet
        outcome = f"🎉 Bạn thắng! +{bet} xu"
    else:
        player.balance -= bet
        outcome = f"💀 Bạn thua! -{bet} xu"

    keyboard = [
        [InlineKeyboardButton("🔁 Chơi tiếp", callback_data="menu_tx"),
         InlineKeyboardButton("🏠 Menu", callback_data="menu")]
    ]
    text = f"🎲 Kết quả: {dice} (Tổng: {total} → {'Tài' if result=='tai' else 'Xỉu'})\n{outcome}\n💰 Số dư: {player.balance}"

    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# ===== BẦU CUA =====
async def menu_bc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(bau_cua_icons[0], callback_data="bc_0"),
         InlineKeyboardButton(bau_cua_icons[1], callback_data="bc_1"),
         InlineKeyboardButton(bau_cua_icons[2], callback_data="bc_2")],
        [InlineKeyboardButton(bau_cua_icons[3], callback_data="bc_3"),
         InlineKeyboardButton(bau_cua_icons[4], callback_data="bc_4"),
         InlineKeyboardButton(bau_cua_icons[5], callback_data="bc_5")],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
    ]
    await query.edit_message_text("Chọn 3 con vật (bấm từng con):", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["bc_chosen"] = []
    return CHON_CONVAT

async def choose_bc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[1])
    chosen = context.user_data.get("bc_chosen", [])
    if idx not in chosen:
        chosen.append(idx)
    context.user_data["bc_chosen"] = chosen

    if len(chosen)<3:
        await query.edit_message_text(f"✅ Chọn: {[bau_cua_icons[i] for i in chosen]}\nChọn thêm {3-len(chosen)} con:", reply_markup=query.message.reply_markup)
        return CHON_CONVAT
    else:
        keyboard = [
            [InlineKeyboardButton(f"{b} 💵", callback_data=f"bcbet_{b}") for b in quick_bets],
            [InlineKeyboardButton("✏️ Nhập số khác", callback_data="bcbet_custom")],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
        ]
        await query.edit_message_text(f"✅ Chọn 3 con: {[bau_cua_icons[i] for i in chosen]}\nChọn số tiền cược:", reply_markup=InlineKeyboardMarkup(keyboard))
        return DAT_TIEN_BC

async def input_bc_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data.startswith("bcbet_") and data != "bcbet_custom":
            bet = int(data.split("_")[1])
        else:
            return DAT_TIEN_BC
    else:
        try:
            bet = int(update.message.text)
        except:
            await update.message.reply_text("❌ Nhập số tiền hợp lệ!")
            return DAT_TIEN_BC

    if bet <=0 or bet>player.balance:
        await update.message.reply_text(f"❌ Tiền cược không hợp lệ! Số dư: {player.balance}")
        return DAT_TIEN_BC

    rolls = [random.randint(0,5) for _ in range(3)]
    win_count = sum(1 for r in context.user_data["bc_chosen"] if r in rolls)
    if win_count>0:
        win_amount = bet*win_count
        player.balance += win_amount
        outcome = f"🎉 Thắng! +{win_amount} xu"
    else:
        player.balance -= bet
        outcome = f"💀 Thua! -{bet} xu"

    rolls_icons = [bau_cua_icons[r] for r in rolls]
    keyboard = [
        [InlineKeyboardButton("🔁 Chơi tiếp", callback_data="menu_bc"),
         InlineKeyboardButton("🏠 Menu", callback_data="menu")]
    ]
    text = f"🎲 Kết quả xúc xắc: {rolls_icons}\n{outcome}\n💰 Số dư: {player.balance}"

    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# ===== MINI GAME VUI =====
async def menu_fun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    number = random.randint(1,10)
    context.user_data["fun_number"] = number
    keyboard = [[InlineKeyboardButton(str(i), callback_data=f"fun_{i}") for i in range(1,6)],
                [InlineKeyboardButton(str(i), callback_data=f"fun_{i}") for i in range(6,11)],
                [InlineKeyboardButton("🏠 Menu", callback_data="menu")]]
    await query.edit_message_text("Đoán số may mắn từ 1-10:", reply_markup=InlineKeyboardMarkup(keyboard))
    return FUN_GAME

async def fun_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    guess = int(query.data.split("_")[1])
    number = context.user_data.get("fun_number")
    if guess == number:
        text = f"🎉 Chúc mừng! Bạn đoán đúng: {number}"
    else:
        text = f"❌ Sai rồi! Số may mắn là: {number}"
    keyboard = [[InlineKeyboardButton("🔁 Chơi lại", callback_data="menu_fun"),
                 InlineKeyboardButton("🏠 Menu", callback_data="menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# ===== MENU BALANCE =====
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = get_player(query.from_user.id)
    await query.edit_message_text(f"💰 Số dư hiện tại: {player.balance} xu")

async def callback_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)
    return ConversationHandler.END

# ===== MAIN =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_bc = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_bc, pattern="^menu_bc$")],
        states={
            CHON_CONVAT: [CallbackQueryHandler(choose_bc, pattern="^bc_")],
            DAT_TIEN_BC: [
                CallbackQueryHandler(input_bc_bet, pattern="^bcbet_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_bc_bet)
            ]
        },
        fallbacks=[]
    )

    conv_tx = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_tx, pattern="^menu_tx$")],
        states={
            CHON_TX: [CallbackQueryHandler(choose_tx, pattern="^tx_")],
            DAT_TIEN_TX: [
                CallbackQueryHandler(input_tx_bet, pattern="^txbet_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_tx_bet)
            ]
        },
        fallbacks=[]
    )

    conv_fun = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_fun, pattern="^menu_fun$")],
        states={FUN_GAME: [CallbackQueryHandler(fun_guess, pattern="^fun_")]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("cobac", start))
    app.add_handler(conv_bc)
    app.add_handler(conv_tx)
    app.add_handler(conv_fun)
    app.add_handler(CallbackQueryHandler(show_balance, pattern="^menu_balance$"))
    app.add_handler(CallbackQueryHandler(callback_menu, pattern="^menu$"))

    app.run_polling()

if __name__ == "__main__":
    main()
