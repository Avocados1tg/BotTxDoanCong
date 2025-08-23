import os, random, json, time, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "vnd_wallet.json"

CHOOSING_GAME, CHOOSING_OPTION, CHOOSING_BET, INPUT_BET = range(4)

# --- Load / Save ---
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        users = json.load(f)
else:
    users = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f)

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

# --- Menu chính callback ---
async def menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    return await cobac(update, context)

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

# --- Chọn phương án trước ---
async def choose_option(update, context):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    game = query.data
    users[user_id]["current_game"]=game
    users[user_id].pop("choice", None)
    bet_values=[10000,50000,100000]
    
    if game=="taixiu":
        buttons=[[InlineKeyboardButton("Tai", callback_data="option_Tai"),
                  InlineKeyboardButton("Xiu", callback_data="option_Xiu")]]
    elif game=="rutbai":
        buttons=[[InlineKeyboardButton("Cao", callback_data="option_Cao"),
                  InlineKeyboardButton("Thap", callback_data="option_Thap")]]
    elif game=="roulette":
        buttons=[[InlineKeyboardButton("Do", callback_data="option_Do"),
                  InlineKeyboardButton("Den", callback_data="option_Den")]]
    elif game=="dauxucxac":
        buttons=[[InlineKeyboardButton("1", callback_data="option_1"),
                  InlineKeyboardButton("2", callback_data="option_2"),
                  InlineKeyboardButton("3", callback_data="option_3")]]
    elif game=="baucua":
        options=["ca","bo","ho","tom","ga","cuu"]
        emoji_map={"ca":"🐟","bo":"🐄","ho":"🐅","tom":"🦑","ga":"🦆","cuu":"🐏"}
        buttons=[]
        for i in range(0,6,3):
            row=[]
            for o in options[i:i+3]:
                row.append(InlineKeyboardButton(emoji_map[o], callback_data=f"option_{o}"))
            buttons.append(row)
    await query.edit_message_text("🎲 Chọn phương án:", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSING_OPTION

# --- Chọn tiền sau khi chọn phương án ---
async def choose_bet(update, context):
    query = update.callback_query
    await query.answer()
    user_id=str(query.from_user.id)
    _, choice = query.data.split("_")
    users[user_id]["choice"]=choice
    bet_values=[10000,50000,100000]
    buttons=[[InlineKeyboardButton(f"{b:,} VND", callback_data=f"bet_{b}") for b in bet_values]]
    buttons.append([InlineKeyboardButton("📝 Nhập số khác", callback_data="bet_custom")])
    await query.edit_message_text(f"Bạn chọn {choice}, bây giờ chọn số VND cược:", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSING_BET

# --- Chọn tiền cược ---
async def option_bet_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id=str(query.from_user.id)
    data=query.data
    if data=="bet_custom":
        await query.edit_message_text("Nhập số VND muốn cược:")
        return INPUT_BET
    _, amount = data.split("_")
    users[user_id]["bet"]=int(amount)
    return await play_game(update, context)

# --- Nhập số VND cược tùy chỉnh ---
async def input_bet(update, context):
    user_id=str(update.message.from_user.id)
    try:
        amount=int(update.message.text)
        if amount<=0 or amount>users[user_id]["vnd"]:
            raise ValueError
        users[user_id]["bet"]=amount
        return await play_game(update, context)
    except:
        await update.message.reply_text("❌ Số VND không hợp lệ.")
        return INPUT_B
