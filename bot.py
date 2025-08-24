#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot: "Trùm Cá Cược" (SAFE VERSION)
— Chỉ dùng COIN ẢO để giải trí. KHÔNG TIỀN THẬT, KHÔNG CASH-OUT.
— Bạn tự chịu trách nhiệm tuân thủ pháp luật địa phương và quy định của Telegram.

Yêu cầu:
- Python 3.10+
- Thư viện: python-telegram-bot>=20.0
  cài: pip install python-telegram-bot==21.4

Chạy bot:
1) Đặt token bot vào biến môi trường BOT_TOKEN (hoặc sửa hằng số ở dưới cho nhanh — KHÔNG KHUYẾN NGHỊ commit công khai).
   - Windows (PowerShell):  $env:BOT_TOKEN = "123456:ABC..."
   - Linux/macOS:          export BOT_TOKEN="123456:ABC..."
2) python bot.py

Tính năng chính:
- /start, /help, /rules
- /register: tạo tài khoản coin ảo (nếu /start không auto tạo)
- /balance (hoặc /bal): xem số dư
- /daily: nhận thưởng ngày (cooldown 24h)
- /leaderboard: top giàu nhất
- /bet_taixiu <tiền> <tai|xiu>
- /bet_dice <tiền> <1-6>  (đoán 1 mặt xúc xắc, ăn 5x)
- /bet_roulette <tiền> <red|black|even|odd|0-36>
- Admin (OWNER_ID): /give @user <tiền>, /setbal @user <tiền>, /toggle <game> on|off

Lưu ý công bằng:
- Random chuẩn từ Python's secrets (crypto-secure) khi có thể; fallback random.SystemRandom.
- Lưu lịch sử cược vào SQLite: casino.db

"""

from __future__ import annotations
import asyncio
import os
import re
import sqlite3
from datetime import datetime, timedelta, date
from typing import Optional, Tuple

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
)

# ========================== CẤU HÌNH ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # BẮT BUỘC: đặt biến môi trường
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # id telegram của owner (tùy chọn)
DB_PATH = os.getenv("DB_PATH", "casino.db")

# Game switches (có thể bật/tắt bằng /toggle)
DEFAULT_SWITCHES = {
    "taixiu": True,
    "dice": True,
    "roulette": True,
}

INITIAL_BALANCE = 1_000
DAILY_REWARD = 200
DAILY_COOLDOWN_HOURS = 24
MAX_BET = 100_000
MIN_BET = 10

# ========================== UTILITIES ==========================
try:
    from secrets import randbelow
    _rand = randbelow
except Exception:
    import random
    _sysrand = random.SystemRandom()
    _rand = lambda n: _sysrand.randrange(n)


def now_ts() -> str:
    return datetime.utcnow().isoformat()


def with_db(func):
    """Decorator tiện mở/đóng kết nối SQLite."""
    def wrapper(*args, **kwargs):
        con = sqlite3.connect(DB_PATH)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA foreign_keys=ON;")
        try:
            res = func(con, *args, **kwargs)
            con.commit()
            return res
        finally:
            con.close()
    return wrapper


@with_db
def init_db(con: sqlite3.Connection):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            balance INTEGER NOT NULL DEFAULT 0,
            last_daily TEXT
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game TEXT NOT NULL,
            amount INTEGER NOT NULL,
            choice TEXT NOT NULL,
            result TEXT NOT NULL,
            payout INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS switches (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        );
        """
    )
    # seed switches
    for k, v in DEFAULT_SWITCHES.items():
        con.execute(
            "INSERT OR IGNORE INTO switches(key, value) VALUES (?, ?)", (k, 1 if v else 0)
        )


@with_db
def get_or_create_user(con: sqlite3.Connection, tg_id: int, username: Optional[str]) -> Tuple[int, int]:
    cur = con.execute("SELECT id, balance FROM users WHERE tg_id=?", (tg_id,))
    row = cur.fetchone()
    if row:
        return row[0], row[1]
    con.execute(
        "INSERT INTO users(tg_id, username, balance) VALUES (?, ?, ?)",
        (tg_id, username, INITIAL_BALANCE),
    )
    uid = con.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)).fetchone()[0]
    return uid, INITIAL_BALANCE


@with_db
def get_user(con: sqlite3.Connection, tg_id: int) -> Optional[Tuple[int, str, int, Optional[str]]]:
    cur = con.execute("SELECT id, username, balance, last_daily FROM users WHERE tg_id=?", (tg_id,))
    return cur.fetchone()


@with_db
def update_balance(con: sqlite3.Connection, user_id: int, new_balance: int):
    con.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, user_id))


@with_db
def record_bet(con: sqlite3.Connection, user_id: int, game: str, amount: int, choice: str, result: str, payout: int):
    con.execute(
        "INSERT INTO bets(user_id, game, amount, choice, result, payout, created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, game, amount, choice, result, payout, now_ts()),
    )


@with_db
def set_last_daily(con: sqlite3.Connection, user_id: int, ts: str):
    con.execute("UPDATE users SET last_daily=? WHERE id=?", (ts, user_id))


@with_db
def leaderboard(con: sqlite3.Connection, limit: int = 10):
    cur = con.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
    return cur.fetchall()


@with_db
def set_switch(con: sqlite3.Connection, key: str, value: bool):
    con.execute("INSERT INTO switches(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, 1 if value else 0))


@with_db
def get_switch(con: sqlite3.Connection, key: str) -> bool:
    cur = con.execute("SELECT value FROM switches WHERE key=?", (key,))
    row = cur.fetchone()
    if not row:
        return DEFAULT_SWITCHES.get(key, True)
    return bool(row[0])


# ========================== HELPERS ==========================

def parse_bet(args: list[str]) -> Tuple[Optional[int], Optional[str]]:
    if len(args) < 2:
        return None, None
    try:
        amt = int(args[0])
    except ValueError:
        return None, None
    return amt, args[1].lower()


def ensure_registered(user: Optional[Tuple[int, str, int, Optional[str]]]) -> bool:
    return user is not None


def clamp_bet(amount: int) -> Optional[str]:
    if amount < MIN_BET:
        return f"Mức cược tối thiểu là {MIN_BET}."
    if amount > MAX_BET:
        return f"Mức cược tối đa là {MAX_BET}."
    return None


# ========================== COMMANDS ==========================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()  # đảm bảo DB sẵn sàng
    uid, bal = get_or_create_user(user.id, user.username or user.full_name)
    await update.message.reply_text(
        f"Chào {user.first_name}! Bạn đã có ví coin ảo với số dư: {bal}💰\n"
        f"/help để xem lệnh. Chơi vui, KHÔNG tiền thật."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📜 Lệnh cơ bản:\n"
        "/start – khởi động & tạo ví\n"
        "/balance hoặc /bal – xem số dư\n"
        f"/daily – nhận {DAILY_REWARD} coin mỗi {DAILY_COOLDOWN_HOURS}h\n"
        "/leaderboard – top coin\n\n"
        "🎲 Cược game:\n"
        "/bet_taixiu <tiền> <tai|xiu>\n"
        "/bet_dice <tiền> <1-6>  (đúng ăn x5)\n"
        "/bet_roulette <tiền> <red|black|even|odd|0-36>\n\n"
        "⚙️ Admin: /give @user <tiền>, /setbal @user <tiền>, /toggle <game> on|off\n"
        "🔒 Lưu ý: coin ảo, không đổi ra tiền thật."
    )
    await update.message.reply_text(msg)


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Luật chơi công bằng, random minh bạch.\n"
        "❌ Không dùng tiền thật, không khuyến khích đánh bạc.\n"
        "🧠 Vui là chính — nhớ kiểm soát thời gian!"
    )


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not ensure_registered(user):
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    _, username, balance, _ = user
    await update.message.reply_text(f"{username}: {balance} coin 💰")


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not ensure_registered(u):
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    uid, _, balance, last_daily = u
    now = datetime.utcnow()
    if last_daily:
        last = datetime.fromisoformat(last_daily)
        if now - last < timedelta(hours=DAILY_COOLDOWN_HOURS):
            remain = timedelta(hours=DAILY_COOLDOWN_HOURS) - (now - last)
            hrs = int(remain.total_seconds() // 3600)
            mins = int((remain.total_seconds() % 3600) // 60)
            await update.message.reply_text(f"Chưa đủ cooldown. Thử lại sau {hrs}h{mins:02d}.")
            return
    # reward
    new_bal = balance + DAILY_REWARD
    update_balance(uid, new_bal)
    set_last_daily(uid, now.isoformat())
    await update.message.reply_text(f"Nhận +{DAILY_REWARD} coin! Số dư: {new_bal} 💰")


# -------------- GAME: TÀI XỈU --------------

def roll_3dice() -> Tuple[int, Tuple[int, int, int]]:
    d1 = _rand(6) + 1
    d2 = _rand(6) + 1
    d3 = _rand(6) + 1
    s = d1 + d2 + d3
    return s, (d1, d2, d3)


async def cmd_bet_taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_switch("taixiu"):
        await update.message.reply_text("Game Tài Xỉu đang tắt.")
        return
    u = get_user(update.effective_user.id)
    if not ensure_registered(u):
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    uid, _, balance, _ = u

    amt, choice = parse_bet(context.args)
    if amt is None:
        await update.message.reply_text("Cú pháp: /bet_taixiu <tiền> <tai|xiu>")
        return
    msg = clamp_bet(amt)
    if msg:
        await update.message.reply_text(msg)
        return
    if amt > balance:
        await update.message.reply_text("Không đủ coin.")
        return
    if choice not in {"tai", "xiu"}:
        await update.message.reply_text("Chọn 'tai' hoặc 'xiu'.")
        return

    total, dice = roll_3dice()
    outcome = "tai" if total >= 11 else "xiu"
    win = (choice == outcome)
    payout = amt if win else -amt
    new_bal = balance + payout
    update_balance(uid, new_bal)
    record_bet(uid, "taixiu", amt, choice, f"{dice}={total}", payout)

    text = (
        f"🎲 Kết quả: {dice} = {total} → {outcome.upper()}\n"
        f"Bạn {'THẮNG' if win else 'THUA'} {'+' if win else ''}{payout} coin.\n"
        f"Số dư mới: {new_bal} 💰"
    )
    await update.message.reply_text(text)


# -------------- GAME: ĐOÁN XÚC XẮC (1-6) --------------
async def cmd_bet_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_switch("dice"):
        await update.message.reply_text("Game Dice đang tắt.")
        return
    u = get_user(update.effective_user.id)
    if not ensure_registered(u):
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    uid, _, balance, _ = u

    amt, face = parse_bet(context.args)
    if amt is None:
        await update.message.reply_text("Cú pháp: /bet_dice <tiền> <1-6>")
        return
    msg = clamp_bet(amt)
    if msg:
        await update.message.reply_text(msg)
        return
    if amt > balance:
        await update.message.reply_text("Không đủ coin.")
        return
    if face not in {"1","2","3","4","5","6"}:
        await update.message.reply_text("Bạn phải chọn số từ 1 đến 6.")
        return

    roll = _rand(6) + 1
    win = (int(face) == roll)
    payout = amt * 5 if win else -amt  # fair-ish (house edge ~16.67% w/ single die paying 5x)
    new_bal = balance + payout
    update_balance(uid, new_bal)
    record_bet(uid, "dice", amt, face, str(roll), payout)

    await update.message.reply_text(
        f"🎯 Xúc xắc ra: {roll}\nBạn {'THẮNG' if win else 'THUA'} {'+' if win else ''}{payout} coin.\nSố dư mới: {new_bal} 💰"
    )


# -------------- GAME: ROULETTE ĐƠN GIẢN --------------
_ROULETTE_REDS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
_ROULETTE_BLACKS = set(range(1,37)) - _ROULETTE_REDS


def spin_roulette() -> int:
    # Single-zero roulette: 0..36
    return _rand(37)


async def cmd_bet_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_switch("roulette"):
        await update.message.reply_text("Roulette đang tắt.")
        return
    u = get_user(update.effective_user.id)
    if not ensure_registered(u):
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    uid, _, balance, _ = u

    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /bet_roulette <tiền> <red|black|even|odd|0-36>")
        return
    try:
        amt = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Tiền cược phải là số nguyên.")
        return
    choice = context.args[1].lower()

    msg = clamp_bet(amt)
    if msg:
        await update.message.reply_text(msg)
        return
    if amt > balance:
        await update.message.reply_text("Không đủ coin.")
        return

    result = spin_roulette()
    win = False
    multiplier = 0

    if choice in {"red", "đen", "black"}:  # hỗ trợ en/vi
        is_red = result in _ROULETTE_REDS
        is_black = result in _ROULETTE_BLACKS
        if result == 0:
            win = False
        elif choice in {"red"} and is_red:
            win = True
        elif choice in {"black", "đen"} and is_black:
            win = True
        multiplier = 1  # 1:1
    elif choice in {"even", "chẵn"}:
        win = (result != 0 and result % 2 == 0)
        multiplier = 1
    elif choice in {"odd", "lẻ"}:
        win = (result % 2 == 1)
        multiplier = 1
    else:
        # chọn số cụ thể
        if re.fullmatch(r"\d{1,2}", choice):
            num = int(choice)
            if 0 <= num <= 36:
                win = (result == num)
                multiplier = 35  # 35:1
            else:
                await update.message.reply_text("Số phải từ 0 đến 36.")
                return
        else:
            await update.message.reply_text("Lựa chọn không hợp lệ.")
            return

    payout = (amt * multiplier) if win else -amt
    new_bal = balance + payout
    update_balance(uid, new_bal)
    record_bet(uid, "roulette", amt, choice, str(result), payout)

    await update.message.reply_text(
        f"🎡 Roulette ra: {result}\nBạn {'THẮNG' if win else 'THUA'} {'+' if win else ''}{payout} coin.\nSố dư mới: {new_bal} 💰"
    )


# -------------- LEADERBOARD --------------
async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = leaderboard(10)
    if not top:
        await update.message.reply_text("Chưa có ai trong bảng xếp hạng.")
        return
    text = ["🏆 TOP 10 GIÀU NHẤT:"]
    for i, (username, bal) in enumerate(top, start=1):
        text.append(f"{i}. {username or 'Người chơi'} – {bal}💰")
    await update.message.reply_text("\n".join(text))


# -------------- ADMIN --------------
async def _require_owner(update: Update) -> bool:
    if OWNER_ID and update.effective_user and update.effective_user.id == OWNER_ID:
        return True
    await update.effective_message.reply_text("Bạn không có quyền.")
    return False


@with_db
def find_user_by_mention(con: sqlite3.Connection, mention: str) -> Optional[Tuple[int, int, str]]:
    # Chấp nhận @username hoặc ID
    if mention.startswith("@"):  # by username
        cur = con.execute("SELECT id, tg_id, username FROM users WHERE lower(username)=lower(?)", (mention[1:],))
        return cur.fetchone()
    else:
        try:
            tid = int(mention)
        except ValueError:
            return None
        cur = con.execute("SELECT id, tg_id, username FROM users WHERE tg_id=?", (tid,))
        return cur.fetchone()


async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_owner(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /give @user <tiền>")
        return
    target = find_user_by_mention(context.args[0])
    if not target:
        await update.message.reply_text("Không tìm thấy user.")
        return
    try:
        amt = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Tiền phải là số.")
        return
    # get current bal
    u = get_user(target[1])
    new_bal = u[2] + amt
    update_balance(u[0], new_bal)
    await update.message.reply_text(f"Đã cộng {amt} coin cho {u[1]}. Số dư: {new_bal}")


async def cmd_setbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_owner(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /setbal @user <tiền>")
        return
    target = find_user_by_mention(context.args[0])
    if not target:
        await update.message.reply_text("Không tìm thấy user.")
        return
    try:
        amt = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Tiền phải là số.")
        return
    update_balance(target[0], amt)
    await update.message.reply_text(f"Đã set số dư {amt} cho {target[2]}.")


async def cmd_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_owner(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /toggle <taixiu|dice|roulette> <on|off>")
        return
    game, state = context.args[0].lower(), context.args[1].lower()
    if game not in DEFAULT_SWITCHES:
        await update.message.reply_text("Game không hợp lệ.")
        return
    val = True if state in {"on", "1", "true"} else False
    set_switch(game, val)
    await update.message.reply_text(f"Đã {'bật' if val else 'tắt'} {game}.")


# -------------- MISC --------------
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Không hiểu lệnh. Gõ /help nhé.")


# ========================== MAIN ==========================
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Thiếu BOT_TOKEN. Đặt biến môi trường BOT_TOKEN rồi chạy lại.")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["help", "menu"], cmd_help))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler(["balance", "bal"], cmd_balance))
    app.add_handler(CommandHandler("daily", cmd_daily))

    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))

    app.add_handler(CommandHandler("bet_taixiu", cmd_bet_taixiu))
    app.add_handler(CommandHandler("bet_dice", cmd_bet_dice))
    app.add_handler(CommandHandler("bet_roulette", cmd_bet_roulette))

    app.add_handler(CommandHandler("give", cmd_give))
    app.add_handler(CommandHandler("setbal", cmd_setbal))
    app.add_handler(CommandHandler("toggle", cmd_toggle))

    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("Bot đang chạy… nhấn Ctrl+C để dừng.")
    await app.run_polling(close_loop=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Tạm biệt!")
