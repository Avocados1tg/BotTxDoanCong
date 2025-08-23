import os, random, json, time, asyncio
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

# --- Menu helper ---
def menu_keyboard(extra_buttons=None):
    keyboard = extra_buttons if extra_buttons else []
    keyboard.append([InlineKeyboardButton("🏠 Menu chính", callback_data="cobac")])
    return InlineKeyboardMarkup(keyboard)

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

# --- History / Top / Daily ---
async def history_callback(update, context):
    query=update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    hist = users[user_id].get("history",[])
    text = "📜 Lịch sử 10 lượt gần nhất:\n" + ("\n".join(hist) if hist else "Chưa có lịch sử chơi nào.")
    await query.edit_message_text(text, reply_markup=menu_keyboard())
    return CHOOSING_GAME

async def top_callback(update, context):
    query=update.callback_query
    await query.answer()
    top = sorted(users.items(), key=lambda x:x[1]["vnd"], reverse=True)[:5]
    text="🏆 Top 5 người chơi VND:\n"
    for i,(uid,data) in enumerate(top,1):
        text+=f"{i}. User {uid}: {data['vnd']:,} VND\n"
    await query.edit_message_text(text, reply_markup=menu_keyboard())
    return CHOOSING_GAME

async def daily_callback(update, context):
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
async def nap_rut(update, context):
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

# --- Game UI với theme màu ---
async def game_ui_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    game = query.data
    users[user_id]["current_game"] = game
    bet_values=[10000,50000,100000]
    buttons=[]

    if game=="baucua":
        options=["ca","bo","ho","tom","ga","cuu"]
        emoji_map={"ca":"🐟","bo":"🐄","ho":"🐅","tom":"🦑","ga":"🦆","cuu":"🐏"}
        colors=["🟦","🟩","🟧","🟥","🟪","🟨"]
        for i in range(0,6,3):
            row=[]
            for idx, option in enumerate(options[i:i+3]):
                row.append(InlineKeyboardButton(f"{colors[i+idx]} {emoji_map[option]} + {bet_values[0]:,} VND", 
                                                callback_data=f"{option}_{bet_values[0]}"))
            buttons.append(row)
        buttons.append([InlineKeyboardButton("📝 Nhập số khác", callback_data="bet_custom")])
        await query.edit_message_text("🐟 Bầu Cua 3 con! Chọn con + tiền cược:", reply_markup=InlineKeyboardMarkup(buttons))
        return CHOOSING_OPTION

    game_options={"taixiu":["Tai","Xiu"],"rutbai":["Cao","Thap"],"roulette":["Do","Den"],"dauxucxac":["1","2","3"]}
    game_colors={"Tai":"🟦","Xiu":"🟩","Cao":"🟦","Thap":"🟩","Do":"🟥","Den":"⬛","1":"🟦","2":"🟧","3":"🟩"}
    for option in game_options[game]:
        row=[InlineKeyboardButton(f"{game_colors[option]} {option} + {b:,} VND", callback_data=f"{option}_{b}") for b in bet_values]
        buttons.append(row)
    buttons.append([InlineKeyboardButton("📝 Nhập số khác", callback_data="bet_custom")])
    await query.edit_message_text("Chọn phương án + số VND cược:", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSING_OPTION

# --- Chọn phương án + tiền ---
async def option_bet_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data
    if data=="bet_custom":
        await query.edit_message_text("Nhập số VND muốn cược:")
        return INPUT_BET
    choice, bet = data.split("_")
    users[user_id]["choice"]=choice
    users[user_id]["bet"]=int(bet)
    save_data()
    return await play_game(update, context)

# --- Nhập tiền tùy chỉnh ---
async def input_bet(update, context):
    user_id=str(update.message.from_user.id)
    try:
        amount=int(update.message.text)
        if amount<=0 or amount>users[user_id]["vnd"]:
            raise ValueError
        users[user_id]["bet"]=amount
        save_data()
        await update.message.reply_text(f"✅ Bạn đặt {amount:,} VND. Bấm chọn phương án chơi.")
    except:
        await update.message.reply_text("❌ Số VND không hợp lệ.")
    return CHOOSING_OPTION

# --- Chơi game chung ---
async def play_game(update, context):
    if hasattr(update,"callback_query"):
        query=update.callback_query
        await query.answer()
    user_id=str(update.effective_user.id)
    game=users[user_id]["current_game"]
    choice=users[user_id].get("choice","Tai")
    bet=users[user_id].get("bet",10000)
    
    outcome_text=""
    win=False

    if game=="taixiu":
        dice=[random.randint(1,6) for _ in range(3)]
        total=sum(dice)
        emoji_map=["","⚀","⚁","⚂","⚃","⚄","⚅"]
        dice_display=" ".join([emoji_map[d] for d in dice])
        outcome_text=f"{dice_display} = {total}"
        if (total>10 and choice=="Tai") or (total<=10 and choice=="Xiu"):
            win=True
    elif game=="dauxucxac":
        rolls=int(choice)
        dice=[random.randint(1,6) for _ in range(rolls)]
        await asyncio.sleep(0.8)
        emoji_map=["","⚀","⚁","⚂","⚃","⚄","⚅"]
        dice_display=" ".join([emoji_map[d] for d in dice])
        total=sum(dice)
        outcome_text=f"{dice_display} = {total}"
        win=int(choice) in dice
    elif game=="rutbai":
        card=random.randint(1,13)
        emoji_card=["🂡","🂱","🂲","🂳","🂴","🂵","🂶","🂷","🂸","🂹","🂺","🂻","🂽"]
        outcome_text=f"Quân bài: {emoji_card[(card-1)%13]} ({card})"
        if (card>7 and choice=="Cao") or (card<=7 and choice=="Thap"):
            win=True
    elif game=="roulette":
        num=random.randint(0,36)
        color="Do" if num%2 else "Den"
        outcome_text=f"🎯 Roulette: {num} ({color})"
        if color==choice:
            win=True
    elif game=="baucua":
        dice=[random.choice(["ca","bo","ho","tom","ga","cuu"]) for _ in range(3)]
        emoji_map={"ca":"🐟","bo":"🐄","ho":"🐅","tom":"🦑","ga":"🦆","cuu":"🐏"}
        dice_display=" ".join([emoji_map[d] for d in dice])
        outcome_text=f"{dice_display}"
        if choice in dice:
            win=True

    if hasattr(update,"callback_query"):
        await query.edit_message_text("🎲 Đang chơi game...")
        await asyncio.sleep(0.8)

    if win:
        users[user_id]["vnd"]+=bet
        users[user_id]["consecutive_loss"]=0
        outcome="Thắng"
    else:
        users[user_id]["vnd"]-=bet
        users[user_id]["consecutive_loss"]+=1
        outcome="Thua"

    users[user_id]["vip_level"]=1 + users[user_id]["vnd"]//1000000
    add_history(user_id,game,choice,bet,outcome)
    save_data()
    text=f"Kết quả: {outcome_text}\nBạn {outcome}! Số dư: {users[user_id]['vnd']:,} VND"
    if hasattr(update,"callback_query"):
        await query.edit_message_text(text, reply_markup=menu_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=menu_keyboard())
    return CHOOSING_GAME

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
                CallbackQueryHandler(game_ui_callback, pattern="^(taixiu|rutbai|roulette|dauxucxac|baucua)$")
            ],
            CHOOSING_OPTION:[
                CallbackQueryHandler(option_bet_callback),
            ],
            INPUT_BET:[MessageHandler(filters.TEXT & ~filters.COMMAND, input_bet)]
        },
        fallbacks=[CommandHandler("nap", nap_rut), CommandHandler("rut", nap_rut)]
    )
    app.add_handler(conv_handler)
    print("Bot started")
    app.run_polling()
