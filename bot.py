# ultimate_mini_casino_complete.py
import os, random, json, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "vnd_wallet.json"

CHOOSING_GAME, CHOOSING_OPTION, INPUT_BET = range(3)

# --- Load / Save ---
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        users = json.load(f)
else:
    users = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f)

# --- Menu ---
def menu_keyboard(extra_buttons=None):
    keyboard = extra_buttons if extra_buttons else []
    keyboard.append([InlineKeyboardButton("🏠 Menu chính", callback_data="cobac")])
    return InlineKeyboardMarkup(keyboard)

# --- Add history ---
def add_history(user_id, game, choice, bet, outcome):
    if "history" not in users[user_id]:
        users[user_id]["history"]=[]
    users[user_id]["history"].append(f"{game}: {choice}, {bet:,} VND, {outcome}")
    if len(users[user_id]["history"])>10:
        users[user_id]["history"]=users[user_id]["history"][-10:]
    save_data()

# --- /cobac ---
async def cobac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in users:
        users[user_id] = {"vnd":1000000, "history":[], "vip_level":1, "last_daily":0, "consecutive_loss":0}
        save_data()
    keyboard = [
        [InlineKeyboardButton("🎲 Tài Xỉu", callback_data="taixiu")],
        [InlineKeyboardButton("🃏 Rút Bài", callback_data="rutbai")],
        [InlineKeyboardButton("🎡 Roulette", callback_data="roulette")],
        [InlineKeyboardButton("🎯 Đua Xúc Xắc", callback_data="dauxucxac")],
        [InlineKeyboardButton("🐟 Bầu Cua", callback_data="baucua")],
        [InlineKeyboardButton("💵 Số dư VND", callback_data="score"),
         InlineKeyboardButton("📜 Lịch sử", callback_data="history")],
        [InlineKeyboardButton("🏆 Top 5", callback_data="top"),
         InlineKeyboardButton("🎁 Daily", callback_data="daily")]
    ]
    reply_markup = menu_keyboard(keyboard)
    if update.message:
        await update.message.reply_text("🎰 Mini Casino Ultimate! Chọn trò chơi:", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text("🎰 Mini Casino Ultimate! Chọn trò chơi:", reply_markup=reply_markup)
    return CHOOSING_GAME

# --- History ---
async def history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    hist = users[user_id].get("history",[])
    if not hist:
        text="📜 Chưa có lịch sử chơi nào."
    else:
        text="📜 Lịch sử 10 lượt gần nhất:\n" + "\n".join(hist)
    await query.edit_message_text(text, reply_markup=menu_keyboard())
    return CHOOSING_GAME

# --- Top 5 ---
async def top_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    top = sorted(users.items(), key=lambda x:x[1]["vnd"], reverse=True)[:5]
    text="🏆 Top 5 người chơi VND:\n"
    for i,(uid,data) in enumerate(top,1):
        text+=f"{i}. User {uid}: {data['vnd']:,} VND\n"
    await query.edit_message_text(text, reply_markup=menu_keyboard())
    return CHOOSING_GAME

# --- Daily reward ---
async def daily_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    now=int(time.time())
    last=users[user_id].get("last_daily",0)
    if now-last<86400:
        remaining = 86400-(now-last)
        await query.edit_message_text(f"⏳ Chỉ nhận 1 lần / 24h. Còn {remaining//3600}h {(remaining%3600)//60}m", reply_markup=menu_keyboard())
    else:
        reward = 50000 + users[user_id]["vip_level"]*5000
        users[user_id]["vnd"] += reward
        users[user_id]["last_daily"]=now
        save_data()
        await query.edit_message_text(f"🎁 Nhận thưởng daily: +{reward:,} VND! Số dư: {users[user_id]['vnd']:,} VND", reply_markup=menu_keyboard())
    return CHOOSING_GAME

# --- Nạp / Rút ---
async def nap_rut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    user_id = str(update.message.from_user.id)
    if user_id not in users:
        users[user_id] = {"vnd":1000000, "history":[],"vip_level":1,"last_daily":0,"consecutive_loss":0}
        save_data()
    if msg.startswith("/nap"):
        try:
            amount = int(msg.split()[1])
            if amount<=0: raise ValueError
            users[user_id]["vnd"] += amount
            save_data()
            await update.message.reply_text(f"✅ Nạp thành công +{amount:,} VND. Số dư: {users[user_id]['vnd']:,} VND", reply_markup=menu_keyboard())
        except:
            await update.message.reply_text("❌ Cú pháp: /nap 100000", reply_markup=menu_keyboard())
    elif msg.startswith("/rut"):
        try:
            amount = int(msg.split()[1])
            if amount<=0 or amount>users[user_id]["vnd"]: raise ValueError
            users[user_id]["vnd"] -= amount
            save_data()
            await update.message.reply_text(f"✅ Rút thành công -{amount:,} VND. Số dư: {users[user_id]['vnd']:,} VND", reply_markup=menu_keyboard())
        except:
            await update.message.reply_text("❌ Cú pháp: /rut 100000", reply_markup=menu_keyboard())

# --- Game callback ---
async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    game = query.data
    users[user_id]["current_game"] = game
    # Chọn phương án
    if game == "taixiu":
        keyboard = [
            [InlineKeyboardButton("🎲 Tài", callback_data="Tai")],
            [InlineKeyboardButton("🎲 Xỉu", callback_data="Xiu")]
        ]
    elif game == "rutbai":
        keyboard = [
            [InlineKeyboardButton("🂡 Cao", callback_data="Cao")],
            [InlineKeyboardButton("🂱 Thấp", callback_data="Thap")]
        ]
    elif game == "roulette":
        keyboard = [
            [InlineKeyboardButton("🔴 Đỏ", callback_data="Do")],
            [InlineKeyboardButton("⚫ Đen", callback_data="Den")]
        ]
    elif game == "dauxucxac":
        keyboard = [
            [InlineKeyboardButton("🎯 1", callback_data="1")],
            [InlineKeyboardButton("🎯 2", callback_data="2")],
            [InlineKeyboardButton("🎯 3", callback_data="3")]
        ]
    elif game == "baucua":
        keyboard = [
            [InlineKeyboardButton("🐟", callback_data="ca"), InlineKeyboardButton("🐄", callback_data="bo")],
            [InlineKeyboardButton("🐅", callback_data="ho"), InlineKeyboardButton("🦑", callback_data="tom")],
            [InlineKeyboardButton("🦆", callback_data="ga"), InlineKeyboardButton("🐏", callback_data="cuu")]
        ]
    await query.edit_message_text("Chọn phương án:", reply_markup=menu_keyboard(keyboard))
    return CHOOSING_OPTION

# --- Option callback ---
async def option_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    choice = query.data
    users[user_id]["choice"] = choice
    await query.edit_message_text(f"Bạn chọn: {choice}\nNhập số VND muốn cược:")
    return INPUT_BET

# --- Input bet ---
async def input_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    try:
        bet = int(update.message.text)
        if bet <= 0 or bet > users[user_id]["vnd"]:
            await update.message.reply_text("❌ Số VND không hợp lệ hoặc vượt quá số dư.", reply_markup=menu_keyboard())
            return INPUT_BET
        users[user_id]["bet"] = bet
        await play_game(update, context)
    except:
        await update.message.reply_text("❌ Vui lòng nhập số VND hợp lệ.", reply_markup=menu_keyboard())
        return INPUT_BET

# --- Play game ---
async def play_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    game = users[user_id]["current_game"]
    choice = users[user_id]["choice"]
    bet = users[user_id]["bet"]
    if users[user_id]["consecutive_loss"]>=3:
        bet *=2
        users[user_id]["consecutive_loss"]=0
    win = False
    outcome_text = ""
    
    if game=="taixiu":
        dice=sum(random.randint(1,6) for _ in range(3))
        result="Tai" if dice>10 else "Xiu"
        win = (choice==result)
        outcome_text = f"{result} ({dice})"
    elif game=="rutbai":
        player=random.randint(1,13)
        bot=random.randint(1,13)
        result="Cao" if player>bot else "Thap"
        win = (choice==result)
        outcome_text = f"Bạn {player} - Bot {bot}"
    elif game=="roulette":
        color=random.choice(["Do","Den"])
        win=(choice==color)
        outcome_text=color
    elif game=="dauxucxac":
        dice=[random.randint(1,6) for _ in range(3)]
        win=int(choice) in dice
        outcome_text=",".join(map(str,dice))
    elif game=="baucua":
        dice=[random.choice(["ca","bo","ho","tom","ga","cuu"]) for _ in range(3)]
        win=choice in dice
        outcome_text=",".join(dice)
        
    if win:
        users[user_id]["vnd"] += bet
        users[user_id]["consecutive_loss"]=0
        outcome="Thắng"
    else:
        users[user_id]["vnd"] -= bet
        users[user_id]["consecutive_loss"]+=1
        outcome="Thua"
    users[user_id]["vip_level"]=1 + users[user_id]["vnd"]//1000000
    add_history(user_id, game, choice, bet, outcome)
    save_data()
    await update.message.reply_text(f"Kết quả: {outcome_text}\nBạn {outcome}! Số dư: {users[user_id]['vnd']:,} VND", reply_markup=menu_keyboard())
    return CHOOSING_GAME

# --- Restart ---
async def restart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    return await cobac(update, context)

# --- Main ---
if __name__=="__main__":
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    conv_handler=ConversationHandler(
        entry_points=[CommandHandler("cobac", cobac)],
        states={
            CHOOSING_GAME:[
                CallbackQueryHandler(history_callback, pattern="history"),
                CallbackQueryHandler(top_callback, pattern="top"),
                CallbackQueryHandler(daily_callback, pattern="daily"),
                CallbackQueryHandler(restart_callback, pattern="cobac"),
                CallbackQueryHandler(game_callback)
            ],
            CHOOSING_OPTION:[CallbackQueryHandler(option_callback)],
            INPUT_BET:[MessageHandler(filters.TEXT & ~filters.COMMAND, input_bet)],
        },
        fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, nap_rut)]
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("nap", nap_rut))
    app.add_handler(CommandHandler("rut", nap_rut))
    print("Ultimate Mini Casino Full Bot đang chạy...")
    app.run_polling()
