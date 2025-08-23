# bot_cobac_full.py
import os
import random
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "vnd_wallet.json"

CHOOSING_GAME, CHOOSING_OPTION, BET_CHOICE, INPUT_BET = range(4)

# Load data
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
        users[user_id] = {"vnd": 1000000}
        save_data()
    keyboard = [
        [InlineKeyboardButton("🎲 Tài Xỉu", callback_data="taixiu")],
        [InlineKeyboardButton("🃏 Rút Bài", callback_data="rutbai")],
        [InlineKeyboardButton("🎡 Roulette", callback_data="roulette")],
        [InlineKeyboardButton("🎯 Đua Xúc Xắc", callback_data="dauxucxac")],
        [InlineKeyboardButton("🐟 Bầu Cua", callback_data="baucua")],
        [InlineKeyboardButton("💵 Số dư VND", callback_data="score")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎰 Mini Casino! Chọn trò chơi:", reply_markup=reply_markup)
    return CHOOSING_GAME

# Chọn trò
async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    game = query.data
    context.user_data["game"] = game

    if game == "score":
        await query.edit_message_text(f"💵 Số dư: {users[user_id]['vnd']:,} VND")
        return CHOOSING_GAME

    # Bầu Cua nâng cấp chọn 3 con
    if game == "baucua":
        faces = ["nai","bầu","cá","gà","tôm","cua"]
        context.user_data["baucua_choices"] = []
        keyboard = []
        row=[]
        for face in faces:
            row.append(InlineKeyboardButton(face, callback_data=f"baucua_{face}"))
            if len(row)==3:
                keyboard.append(row)
                row=[]
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("✅ Xong", callback_data="baucua_done")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Chọn 3 con bạn muốn cược:", reply_markup=reply_markup)
        return CHOOSING_OPTION

    keyboard=[]
    if game == "taixiu":
        keyboard=[[InlineKeyboardButton("🎲 Tài", callback_data="taixiu_tai"),
                   InlineKeyboardButton("🎲 Xỉu", callback_data="taixiu_xiu")]]
    elif game == "rutbai":
        keyboard=[[InlineKeyboardButton("🃏 Cao", callback_data="rutbai_cao"),
                   InlineKeyboardButton("🃏 Thấp", callback_data="rutbai_thap")]]
    elif game == "roulette":
        keyboard=[[InlineKeyboardButton("🔴 Red", callback_data="roulette_red"),
                   InlineKeyboardButton("⚫ Black", callback_data="roulette_black")]]
    elif game == "dauxucxac":
        keyboard=[[InlineKeyboardButton(str(i), callback_data=f"dauxucxac_{i}") for i in range(1,7)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Chọn phương án:", reply_markup=reply_markup)
    return CHOOSING_OPTION

# Callback chọn phương án
async def option_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = context.user_data["game"]
    user_id = str(query.from_user.id)
    data = query.data

    # Bầu Cua chọn con
    if game=="baucua":
        if data=="baucua_done":
            if len(context.user_data["baucua_choices"])!=3:
                await query.edit_message_text("❌ Bạn phải chọn đúng 3 con!")
                return CHOOSING_OPTION
            keyboard = [
                [InlineKeyboardButton("💰 50k", callback_data="50000"),
                 InlineKeyboardButton("💰 100k", callback_data="100000"),
                 InlineKeyboardButton("💰 200k", callback_data="200000")],
                [InlineKeyboardButton("Nhập số khác", callback_data="input")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Chọn số VND cược:", reply_markup=reply_markup)
            return BET_CHOICE
        else:
            choices = context.user_data.get("baucua_choices", [])
            face = data.split("_")[1]
            if face in choices:
                choices.remove(face)
            elif len(choices)<3:
                choices.append(face)
            context.user_data["baucua_choices"]=choices
            # hiển thị lại keyboard
            faces = ["nai","bầu","cá","gà","tôm","cua"]
            keyboard=[]
            row=[]
            for f in faces:
                label=f"{f} ✅" if f in choices else f
                row.append(InlineKeyboardButton(label, callback_data=f"baucua_{f}"))
                if len(row)==3:
                    keyboard.append(row)
                    row=[]
            if row: keyboard.append(row)
            keyboard.append([InlineKeyboardButton("✅ Xong", callback_data="baucua_done")])
            reply_markup=InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Chọn 3 con bạn muốn cược:", reply_markup=reply_markup)
            return CHOOSING_OPTION

    # Trò khác
    context.user_data["choice"]=data
    keyboard = [
        [InlineKeyboardButton("💰 50k", callback_data="50000"),
         InlineKeyboardButton("💰 100k", callback_data="100000"),
         InlineKeyboardButton("💰 200k", callback_data="200000")],
        [InlineKeyboardButton("Nhập số khác", callback_data="input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Chọn số VND cược:", reply_markup=reply_markup)
    return BET_CHOICE

# Callback chọn mức cược
async def bet_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data
    if data=="input":
        await query.edit_message_text("Nhập số VND cược:")
        return INPUT_BET
    bet = int(data)
    if bet>users[user_id]["vnd"]:
        await query.edit_message_text("❌ Không đủ VND!")
        return CHOOSING_GAME
    context.user_data["bet"]=bet
    return await play_game(update, context)

# Nhập số khác
async def input_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    try:
        bet=int(update.message.text)
        if bet<=0 or bet>users[user_id]["vnd"]:
            await update.message.reply_text("❌ Số VND không hợp lệ hoặc vượt quá số dư.")
            return INPUT_BET
        context.user_data["bet"]=bet
        return await play_game(update, context)
    except:
        await update.message.reply_text("❌ Nhập số VND hợp lệ.")
        return INPUT_BET

# Chơi game
async def play_game(update, context):
    user_id = str(update.effective_user.id)
    game=context.user_data["game"]
    choice=context.user_data.get("choice","")
    bet=context.user_data["bet"]
    outcome=""

    # Tài Xỉu
    if game=="taixiu":
        dice=[random.randint(1,6) for _ in range(3)]
        result="tai" if 11<=sum(dice)<=18 else "xiu"
        if choice.endswith(result): users[user_id]["vnd"]+=bet; outcome=f"🎉 Thắng! +{bet:,} VND"
        else: users[user_id]["vnd"]-=bet; outcome=f"😢 Thua! -{bet:,} VND"
        save_data()
        text=f"🎲 Tài Xỉu: {dice} → {result}\n{outcome}\n💵 Số dư: {users[user_id]['vnd']:,} VND"

    # Rút Bài
    elif game=="rutbai":
        card=random.randint(1,13)
        result="cao" if card>7 else "thap"
        if choice.endswith(result): users[user_id]["vnd"]+=bet; outcome=f"🎉 Thắng! +{bet:,} VND (Rút {card})"
        else: users[user_id]["vnd"]-=bet; outcome=f"😢 Thua! -{bet:,} VND (Rút {card})"
        save_data()
        text=f"{outcome}\n💵 Số dư: {users[user_id]['vnd']:,} VND"

    # Roulette
    elif game=="roulette":
        spin=random.choice(["red","black"])
        if choice.endswith(spin): users[user_id]["vnd"]+=bet; outcome=f"🎉 Thắng! +{bet:,} VND ({spin})"
        else: users[user_id]["vnd"]-=bet; outcome=f"😢 Thua! -{bet:,} VND ({spin})"
        save_data()
        text=f"{outcome}\n💵 Số dư: {users[user_id]['vnd']:,} VND"

    # Đua Xúc Xắc
    elif game=="dauxucxac":
        dice=random.randint(1,6)
        if int(choice.split("_")[1])==dice: users[user_id]["vnd"]+=bet*5; outcome=f"🎉 Đoán đúng! +{bet*5:,} VND (Xúc xắc: {dice})"
        else: users[user_id]["vnd"]-=bet; outcome=f"😢 Sai! -{bet:,} VND (Xúc xắc: {dice})"
        save_data()
        text=f"{outcome}\n💵 Số dư: {users[user_id]['vnd']:,} VND"

    # Bầu Cua
    elif game=="baucua":
        rolls=[random.choice(["nai","bầu","cá","gà","tôm","cua"]) for _ in range(3)]
        choices=context.user_data.get("baucua_choices", ["nai","bầu","cá"])
        matches=sum([1 for f in rolls if f in choices])
        if matches>0: users[user_id]["vnd"]+=bet*matches; outcome=f"🎉 Thắng! +{bet*matches:,} VND (Xúc xắc: {rolls})"
        else: users[user_id]["vnd"]-=bet; outcome=f"😢 Thua! -{bet:,} VND (Xúc xắc: {rolls})"
        save_data()
        text=f"{outcome}\n💵 Số dư: {users[user_id]['vnd']:,} VND"

    keyboard=[[InlineKeyboardButton("🔄 Chơi tiếp", callback_data="restart"),
              InlineKeyboardButton("🏠 Menu chính", callback_data="cobac")]]
    reply_markup=InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(text, reply_markup=reply_markup)
    return CHOOSING_GAME

# Restart/menu
async def restart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    return await cobac(update, context)

# Main
if __name__=="__main__":
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    conv_handler=ConversationHandler(
        entry_points=[CommandHandler("cobac", cobac)],
        states={
            CHOOSING_GAME:[CallbackQueryHandler(game_callback),
                           CallbackQueryHandler(restart_callback, pattern="restart|cobac")],
            CHOOSING_OPTION:[CallbackQueryHandler(option_callback)],
            BET_CHOICE:[CallbackQueryHandler(bet_choice_callback)],
            INPUT_BET:[MessageHandler(filters.TEXT & ~filters.COMMAND, input_bet)],
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)
    print("Mini Casino VND Bot UI đẹp đang chạy với /cobac...")
    app.run_polling()
