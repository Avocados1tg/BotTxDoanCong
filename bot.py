# bot_cobac_full.py
import os
import random
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "vnd_wallet.json"

# Trạng thái Conversation
CHOOSING_GAME, BET_CHOICE, INPUT_BET, CHOOSING_OPTION = range(4)

# Load dữ liệu
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        users = json.load(f)
else:
    users = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f)

# /cobac
async def cobac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in users:
        users[user_id] = {"vnd": 1000000}  # bắt đầu 1 triệu VND
        save_data()

    keyboard = [
        [InlineKeyboardButton("Tài Xỉu", callback_data="taixiu")],
        [InlineKeyboardButton("Rút Bài", callback_data="rutbai")],
        [InlineKeyboardButton("Roulette", callback_data="roulette")],
        [InlineKeyboardButton("Đua Xúc Xắc", callback_data="dauxucxac")],
        [InlineKeyboardButton("Bầu Cua", callback_data="baucua")],
        [InlineKeyboardButton("Số dư VND", callback_data="score")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎰 Chào mừng đến Mini Casino! Chọn trò chơi:", reply_markup=reply_markup)
    return CHOOSING_GAME

# Callback chọn trò
async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    game = query.data
    context.user_data["game"] = game

    if game == "score":
        await query.edit_message_text(f"Số dư hiện tại: {users[user_id]['vnd']:,} VND 💰")
        return CHOOSING_GAME

    # Chọn mức cược
    keyboard = [
        [InlineKeyboardButton("50.000 VND", callback_data="50000"),
         InlineKeyboardButton("100.000 VND", callback_data="100000"),
         InlineKeyboardButton("200.000 VND", callback_data="200000")],
        [InlineKeyboardButton("Nhập số khác", callback_data="input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Chọn số VND cược cho {game}:", reply_markup=reply_markup)
    return BET_CHOICE

# Chọn mức cược sẵn hoặc nhập số
async def bet_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    choice = query.data

    if choice == "input":
        await query.edit_message_text("Nhập số VND cược:")
        return INPUT_BET
    else:
        bet = int(choice)
        if bet > users[user_id]["vnd"]:
            await query.edit_message_text("❌ Không đủ VND để cược!")
            return CHOOSING_GAME
        context.user_data["bet"] = bet
        return await choose_option(update, context)

# Nhập số tiền cược
async def input_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    try:
        bet = int(update.message.text)
        if bet <=0 or bet > users[user_id]["vnd"]:
            await update.message.reply_text("❌ Số VND không hợp lệ hoặc vượt quá số dư.")
            return INPUT_BET
        context.user_data["bet"] = bet
        return await choose_option(update, context)
    except:
        await update.message.reply_text("❌ Vui lòng nhập số VND hợp lệ.")
        return INPUT_BET

# Chọn phương án trong trò chơi
async def choose_option(update, context):
    user_id = str(update.effective_user.id)
    game = context.user_data["game"]

    # Tạo nút cho từng trò
    if game == "taixiu":
        keyboard = [
            [InlineKeyboardButton("Tài", callback_data="taixiu_tai"),
             InlineKeyboardButton("Xỉu", callback_data="taixiu_xiu")]
        ]
    elif game == "rutbai":
        keyboard = [
            [InlineKeyboardButton("Cao", callback_data="rutbai_cao"),
             InlineKeyboardButton("Thấp", callback_data="rutbai_thap")]
        ]
    elif game == "roulette":
        keyboard = [
            [InlineKeyboardButton("Red", callback_data="roulette_red"),
             InlineKeyboardButton("Black", callback_data="roulette_black")]
        ]
    elif game == "dauxucxac":
        keyboard = [
            [InlineKeyboardButton(str(i), callback_data=f"dauxucxac_{i}") for i in range(1,7)]
        ]
    elif game == "baucua":
        faces = ["nai","bầu","cá","gà","tôm","cua"]
        keyboard = [[InlineKeyboardButton(face, callback_data=f"baucua_{face}") for face in faces[:3]],
                    [InlineKeyboardButton(face, callback_data=f"baucua_{face}") for face in faces[3:]]]
        context.user_data["baucua_choices"] = []

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("Chọn phương án:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Chọn phương án:", reply_markup=reply_markup)

    return CHOOSING_OPTION

# Xử lý lựa chọn của người chơi
async def option_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    game = context.user_data["game"]
    bet = context.user_data["bet"]
    data = query.data

    # Tài Xỉu
    if game=="taixiu" and data.startswith("taixiu_"):
        choice = data.split("_")[1]
        dice = [random.randint(1,6) for _ in range(3)]
        total = sum(dice)
        result = "tài" if 11<=total<=18 else "xỉu"
        if choice == result:
            users[user_id]["vnd"] += bet
            outcome = f"🎉 Thắng! +{bet:,} VND"
        else:
            users[user_id]["vnd"] -= bet
            outcome = f"😢 Thua! -{bet:,} VND"
        save_data()
        await query.edit_message_text(f"🎲 Kết quả Tài Xỉu: {dice} → {result}\n{outcome}\nSố dư: {users[user_id]['vnd']:,} VND")
    
    # Rút Bài
    elif game=="rutbai" and data.startswith("rutbai_"):
        choice = data.split("_")[1]
        card = random.randint(1,13)
        result = "cao" if card>7 else "thap"
        if choice == result:
            users[user_id]["vnd"] += bet
            outcome = f"🎉 Thắng! +{bet:,} VND (Rút {card})"
        else:
            users[user_id]["vnd"] -= bet
            outcome = f"😢 Thua! -{bet:,} VND (Rút {card})"
        save_data()
        await query.edit_message_text(f"{outcome}\nSố dư: {users[user_id]['vnd']:,} VND")

    # Roulette
    elif game=="roulette" and data.startswith("roulette_"):
        choice = data.split("_")[1]
        spin = random.choice(["red","black"])
        if choice == spin:
            users[user_id]["vnd"] += bet
            outcome = f"🎉 Thắng! +{bet:,} VND ({spin})"
        else:
            users[user_id]["vnd"] -= bet
            outcome = f"😢 Thua! -{bet:,} VND ({spin})"
        save_data()
        await query.edit_message_text(f"{outcome}\nSố dư: {users[user_id]['vnd']:,} VND")

    # Đua Xúc Xắc
    elif game=="dauxucxac" and data.startswith("dauxucxac_"):
        choice = int(data.split("_")[1])
        dice = random.randint(1,6)
        if choice == dice:
            users[user_id]["vnd"] += bet*5
            outcome = f"🎉 Đoán đúng! +{bet*5:,} VND (Xúc xắc: {dice})"
        else:
            users[user_id]["vnd"] -= bet
            outcome = f"😢 Sai! -{bet:,} VND (Xúc xắc: {dice})"
        save_data()
        await query.edit_message_text(f"{outcome}\nSố dư: {users[user_id]['vnd']:,} VND")

    # Bầu Cua
    elif game=="baucua" and data.startswith("baucua_"):
        rolls = [random.choice(["nai","bầu","cá","gà","tôm","cua"]) for _ in range(3)]
        choices = ["nai","bầu","cá"]  # mặc định 3 con
        matches = sum([1 for f in rolls if f in choices])
        if matches > 0:
            users[user_id]["vnd"] += bet * matches
            outcome = f"🎉 Thắng! +{bet*matches:,} VND (Xúc xắc: {rolls})"
        else:
            users[user_id]["vnd"] -= bet
            outcome = f"😢 Thua! -{bet:,} VND (Xúc xắc: {rolls})"
        save_data()
        await query.edit_message_text(f"{outcome}\nSố dư: {users[user_id]['vnd']:,} VND")

    return CHOOSING_GAME

# Main
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("cobac", cobac)],
        states={
            CHOOSING_GAME: [CallbackQueryHandler(game_callback)],
            BET_CHOICE: [CallbackQueryHandler(bet_choice_callback)],
            INPUT_BET: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_bet)],
            CHOOSING_OPTION: [CallbackQueryHandler(option_callback)],
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    print("Mini Casino VND Bot đang chạy với nút ấn /cobac...")
    app.run_polling()
