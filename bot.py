import os
import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# get token from Railway variables
TOKEN = os.getenv("TOKEN")

# start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎲 Tai", callback_data="tai"),
         InlineKeyboardButton("🎲 Xiu", callback_data="xiu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome to Tai Xiu bot!\nChoose your bet:",
        reply_markup=reply_markup
    )

# handle button press
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data
    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if total >= 11 else "xiu"

    text = f"Dice result: {dice} (Total = {total})\n➡️ {result.upper()}"

    if choice == result:
        text += "\n✅ You win!"
    else:
        text += "\n❌ You lose!"

    await query.edit_message_text(text)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
