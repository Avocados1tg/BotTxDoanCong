import asyncio, random, json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters

BOT_TOKEN = "8478512062:AAHtkO3agXgg1JPMloOaMLbd0xmSGF-e_o4"
CHOOSING_GAME, ENTER_BET, CHOOSING_OPTION = range(3)

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

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data
    if data=="play_game":
        users[user_id]["current_game"] = None
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

async def game_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    game = query.data
    users[user_id]["current_game"] = game
    await query.edit_message_text(f"Bạn chọn {game}. Chọn số VND muốn cược:", reply_markup=bet_keyboard())
    return ENTER_BET

async def choose_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if query.data=="custom":
        await query.edit_message_text("Nhập số tiền VND muốn cược:")
    else:
        users[user_id]["bet"] = int(query.data)
        await query.edit_message_text("Nhập lựa chọn bạn muốn (ví dụ: Tai/Xiu, Cao/Thấp, tên con Bầu Cua):")
        return CHOOSING_OPTION
    return ENTER_BET

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
    await update.message.reply_text("Nhập lựa chọn bạn muốn (ví dụ: Tai/Xiu, Cao/Thấp, tên con Bầu Cua):")
    return CHOOSING_OPTION

# --- Game play animation ---
async def play_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if hasattr(update, "callback_query") else None
    user_id = str(update.effective_user.id)
    choice = users[user_id].get("choice","Tai")
    bet = users[user_id]["bet"]
    game = users[user_id]["current_game"]
    msg = await (query.edit_message_text(f"🎲 Đang chơi {game}...") if query else update.message.reply_text(f"🎲 Đang chơi {game}..."))

    emoji_map=["","⚀","⚁","⚂","⚃","⚄","⚅"]
    emoji_map_bc={"ca":"🐟","bo":"🐄","ho":"🐅","tom":"🦑","ga":"🦆","cuu":"🐏"}
    emoji_card=["🂡","🂱","🂲","🂳","🂴","🂵","🂶","🂷","🂸","🂹","🂺","🂻","🂽"]

    if game=="dauxucxac":
        rolls = 3
        for _ in range(7):
            dice = [random.randint(1,6) for _ in range(rolls)]
            display=" ".join([emoji_map[d] for d in dice])
            await msg.edit_text(f"🎲 Đua Xúc Xắc...\n{display}")
            await asyncio.sleep(0.25)
        dice=[random.randint(1,6) for _ in range(rolls)]
        dice_display=" ".join([emoji_map[d] for d in dice])
        outcome_text=f"{dice_display} = {sum(dice)}"
        win = int(choice) in dice

    elif game=="baucua":
        dice_keys = list(emoji_map_bc.keys())
        for _ in range(7):
            dice=[random.choice(dice_keys) for _ in range(3)]
            display=" ".join([emoji_map_bc[d] for d in dice])
            await msg.edit_text(f"🐟 Bầu Cua đang lắc...\n{display}")
            await asyncio.sleep(0.25)
        dice=[random.choice(dice_keys) for _ in range(3)]
        display=" ".join([emoji_map_bc[d] for d in dice])
        outcome_text=f"{display}"
        win = choice in dice
        for _ in range(3):
            await msg.edit_text(f"✨ {display} ✨")
            await asyncio.sleep(0.3)
            await msg.edit_text(f"{display}")
            await asyncio.sleep(0.3)

    elif game=="taixiu":
        for _ in range(10):
            dice=[random.randint(1,6) for _ in range(3)]
            display=" ".join([emoji_map[d] for d in dice])
            await msg.edit_text(f"🎲 Tài Xỉu đang lắc...\n{display}")
            await asyncio.sleep(0.2)
        dice=[random.randint(1,6) for _ in range(3)]
        total=sum(dice)
        outcome_text=" ".join([emoji_map[d] for d in dice]) + f" = {total}"
        win=(total>10 and choice=="Tai") or (total<=10 and choice=="Xiu")

    elif game=="rutbai":
        card=random.randint(1,13)
        outcome_text=f"🃏 {emoji_card[card-1]} ({card})"
        win=(card>7 and choice=="Cao") or (card<=7 and choice=="Thap")

    elif game=="roulette":
        num=random.randint(0,36)
        color="Do" if num%2 else "Den"
        outcome_text=f"🎯 Roulette: {num} ({color})"
        win=color==choice

    if win:
        users[user_id]["vnd"] += bet
        users[user_id]["consecutive_loss"]=0
        outcome="Thắng"
    else:
        users[user_id]["vnd"] -= bet
        users[user_id]["consecutive_loss"]+=1
        outcome="Thua"
    users[user_id]["vip_level"]=1 + users[user_id]["vnd"]//1000000
    add_history(user_id,game,choice,bet,outcome)
    save_data()

    await msg.edit_text(f"Kết quả: {outcome_text}\nBạn {outcome}! Số dư: {users[user_id]['vnd']:,} VND", reply_markup=menu_keyboard())
    return CHOOSING_GAME

# --- Main ---
if __name__=="__main__":
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("cobac", start)],
        states={
            CHOOSING_GAME:[CallbackQueryHandler(menu_handler), CallbackQueryHandler(game_selection)],
            ENTER_BET:[CallbackQueryHandler(choose_bet), MessageHandler(filters.TEXT & ~filters.COMMAND, enter_bet)],
            CHOOSING_OPTION:[MessageHandler(filters.TEXT & ~filters.COMMAND, play_game)]
        },
        fallbacks=[CommandHandler("cobac", start)]
    )
    app.add_handler(conv)
    print("Bot đang chạy...")
    app.run_polling()
