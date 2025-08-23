import asyncio, random, json, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # token từ biến môi trường
CHOOSING_GAME, CHOOSING_OPTION, ENTER_BET = range(3)

# --- Data ---
users = {}
data_file = "users.json"

def load_data():
    global users
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        users = {}

def save_data():
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

def add_history(user_id, game, choice, bet, outcome):
    users[user_id].setdefault("history", [])
    users[user_id]["history"].append({"game":game,"choice":choice,"bet":bet,"outcome":outcome})
    if len(users[user_id]["history"])>10:
        users[user_id]["history"].pop(0)

# --- Keyboards ---
def menu_keyboard():
    buttons = [
        [InlineKeyboardButton("🎲 Chơi game", callback_data="play_game")],
        [InlineKeyboardButton("💰 Số dư", callback_data="balance")],
        [InlineKeyboardButton("📜 Lịch sử", callback_data="history")],
        [InlineKeyboardButton("🏆 Top 5", callback_data="top")],
        [InlineKeyboardButton("🎁 Daily", callback_data="daily")]
    ]
    return InlineKeyboardMarkup(buttons)

def game_keyboard():
    buttons = [
        [InlineKeyboardButton("Tài Xỉu", callback_data="taixiu")],
        [InlineKeyboardButton("Đua Xúc Xắc", callback_data="dauxucxac")],
        [InlineKeyboardButton("Bầu Cua", callback_data="baucua")],
        [InlineKeyboardButton("Roulette", callback_data="roulette")],
        [InlineKeyboardButton("Rút Bài", callback_data="rutbai")]
    ]
    return InlineKeyboardMarkup(buttons)

def bet_keyboard():
    buttons = [
        [InlineKeyboardButton("10.000 VND", callback_data="10000"),
         InlineKeyboardButton("50.000 VND", callback_data="50000"),
         InlineKeyboardButton("100.000 VND", callback_data="100000")],
        [InlineKeyboardButton("Nhập khác", callback_data="custom")]
    ]
    return InlineKeyboardMarkup(buttons)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in users:
        users[user_id] = {"vnd":50000,"vip_level":1,"consecutive_loss":0,"history":[]}
        save_data()
    await update.message.reply_text("Chào mừng đến Mini Casino Ultimate!", reply_markup=menu_keyboard())

# Menu chính
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data
    if data=="play_game":
        await query.edit_message_text("Chọn game bạn muốn chơi:", reply_markup=game_keyboard())
        return CHOOSING_GAME
    elif data=="balance":
        await query.edit_message_text(f"Số dư của bạn: {users[user_id]['vnd']:,} VND", reply_markup=menu_keyboard())
    elif data=="history":
        history = users[user_id].get("history", [])
        text = "\n".join([f"{h['game']} - {h['choice']} - {h['bet']:,} VND - {h['outcome']}" for h in history]) or "Chưa có lịch sử nào."
        await query.edit_message_text(f"Lịch sử:\n{text}", reply_markup=menu_keyboard())
    elif data=="top":
        top_users = sorted(users.items(), key=lambda x: x[1]["vnd"], reverse=True)[:5]
        text="\n".join([f"{u[0]}: {u[1]['vnd']:,} VND" for u in top_users])
        await query.edit_message_text(f"Top 5:\n{text}", reply_markup=menu_keyboard())
    elif data=="daily":
        users[user_id]["vnd"] += 10000
        save_data()
        await query.edit_message_text(f"Bạn nhận được 10.000 VND từ Daily!\nSố dư: {users[user_id]['vnd']:,} VND", reply_markup=menu_keyboard())
    return CHOOSING_GAME

# Chọn game
async def game_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    game = query.data
    users[user_id]["current_game"] = game

    if game=="taixiu":
        text="Chọn Tai hoặc Xiu:"
    elif game=="dauxucxac":
        text="Chọn số bạn muốn cược (1-6):"
    elif game=="baucua":
        text="Chọn 3 con bạn muốn cược (ví dụ: ca, bo, ho, tom, ga, cuu) cách nhau bằng dấu phẩy:"
    elif game=="roulette":
        text="Chọn màu: Do hoặc Den:"
    elif game=="rutbai":
        text="Chọn Cao hoặc Thấp:"

    await query.edit_message_text(text)
    return CHOOSING_OPTION

# Nhập lựa chọn
async def option_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    users[user_id]["choice"] = update.message.text
    await update.message.reply_text("Chọn số VND muốn cược:", reply_markup=bet_keyboard())
    return ENTER_BET

# Chọn tiền
async def choose_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if query.data=="custom":
        await query.edit_message_text("Nhập số tiền VND muốn cược:")
        return ENTER_BET
    else:
        users[user_id]["bet"] = int(query.data)
        await play_game(update, context)
        return CHOOSING_GAME

# Nhập tiền thủ công
async def enter_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    try:
        bet = int(update.message.text)
    except:
        await update.message.reply_text("Vui lòng nhập số VND hợp lệ.")
        return ENTER_BET
    if bet>users[user_id]["vnd"]:
        await update.message.reply_text("Bạn không có đủ VND để cược.")
        return ENTER_BET
    users[user_id]["bet"] = bet
    await play_game(update, context)
    return CHOOSING_GAME

# --- Chơi game + animation ---
async def play_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if hasattr(update, "callback_query"):
        msg_obj = update.callback_query
        await msg_obj.answer()
    else:
        msg_obj = update.message
    user_id = str(update.effective_user.id)
    choice = users[user_id]["choice"]
    bet = users[user_id]["bet"]
    game = users[user_id]["current_game"]

    msg = await msg_obj.edit_message_text(f"🎲 Đang chơi {game}...") if hasattr(msg_obj, "edit_message_text") else await msg_obj.reply_text(f"🎲 Đang chơi {game}...")

    emoji_map=["","⚀","⚁","⚂","⚃","⚄","⚅"]
    baucua_map = {"ca":"🐟","bo":"🐂","ho":"🐅","tom":"🦐","ga":"🐓","cuu":"🐑"}
    roulette_map = ["🟥","🟦"]
    cards = ["🂡","🂢","🂣","🂤","🂥","🂦","🂧","🂨","🂩","🂪","🂫","🂭","🂮"]

    # Xử lý từng game với animation
    if game=="dauxucxac":
        rolls=3
        for _ in range(7):
            display=" ".join([emoji_map[random.randint(1,6)] for _ in range(rolls)])
            await msg.edit_text(f"🎲 Đua Xúc Xắc...\n{display}")
            await asyncio.sleep(0.25)
        dice=[random.randint(1,6) for _ in range(rolls)]
        dice_display=" ".join([emoji_map[d] for d in dice])
        outcome_text=f"{dice_display} = {sum(dice)}"
        win=int(choice) in dice

    elif game=="taixiu":
        rolls=[random.randint(1,6) for _ in range(3)]
        for _ in range(5):
            display=" ".join([emoji_map[random.randint(1,6)] for _ in range(3)])
            await msg.edit_text(f"🎲 Tài Xỉu...\n{display}")
            await asyncio.sleep(0.3)
        display=" ".join([emoji_map[r] for r in rolls])
        total=sum(rolls)
        outcome_text=f"{display} = {total}"
        win=(choice.lower()=="tai" and total>10) or (choice.lower()=="xiu" and total<=10)

    elif game=="baucua":
        rolls=[random.choice(list(baucua_map.keys())) for _ in range(3)]
        for _ in range(5):
            display=" ".join([baucua_map[random.choice(list(baucua_map.keys()))] for _ in range(3)])
            await msg.edit_text(f"🎲 Bầu Cua...\n{display}")
            await asyncio.sleep(0.3)
        display=" ".join([baucua_map[r] for r in rolls])
        outcome_text=f"{display}"
        choices = [c.strip() for c in choice.lower().split(",")]
        win = any(r in choices for r in rolls)

    elif game=="roulette":
        for _ in range(7):
            display=" ".join([random.choice(roulette_map) for _ in range(8)])
            await msg.edit_text(f"🎡 Roulette quay...\n{display}")
            await asyncio.sleep(0.25)
        color=random.choice(["Do","Den"])
        outcome_text=f"Màu dừng: {color}"
        win=(choice.lower()==color.lower())

    elif game=="rutbai":
        card_value=random.randint(1,13)
        for _ in range(5):
            display=random.choice(cards)
            await msg.edit_text(f"🃏 Rút Bài...\n{display}")
            await asyncio.sleep(0.3)
        outcome_text=f"Giá trị bài: {card_value}"
        win=(card_value>=7 and choice.lower()=="cao") or (card_value<7 and choice.lower()=="thap")

    # Cập nhật VND
    if win:
        users[user_id]["vnd"] += bet
        outcome="Thắng"
    else:
        users[user_id]["vnd"] -= bet
        outcome="Thua"

    add_history(user_id, game, choice, bet, outcome)
    save_data()
    await msg.edit_text(f"Kết quả: {outcome_text}\nBạn {outcome}! Số dư: {users[user_id]['vnd']:,} VND", reply_markup=menu_keyboard())

# --- Application ---
if __name__=="__main__":
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler(["start","cobac"], start)],
        states={
            CHOOSING_GAME:[CallbackQueryHandler(game_selection, pattern="^taixiu$|^dauxucxac$|^baucua$|^roulette$|^rutbai$"),
                           CallbackQueryHandler(menu_handler, pattern="^balance$|^history$|^top$|^daily$|^play_game$")],
            CHOOSING_OPTION:[MessageHandler(filters.TEXT & ~filters.COMMAND, option_selected)],
            ENTER_BET:[CallbackQueryHandler(choose_bet, pattern="^\d+$|^custom$"),
                       MessageHandler(filters.TEXT & ~filters.COMMAND, enter_bet)]
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False
    )
    app.add_handler(conv)
    print("Bot đang chạy...")
    app.run_polling()
