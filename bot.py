#!/usr/bin/env python3
import os
import sqlite3
import requests
from datetime import datetime
from dotenv import load_dotenv
import telebot

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN غير موجود في .env")

bot = telebot.TeleBot(TOKEN)
DB_PATH = "watchlist.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            user_id INTEGER,
            symbol TEXT,
            created_at TEXT,
            PRIMARY KEY (user_id, symbol)
        )
    """)
    conn.commit()
    conn.close()


def normalize_symbol(symbol):
    return symbol.strip().upper().replace(" ", "")


def get_quote(symbol):
    symbol = normalize_symbol(symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        name = meta.get("shortName") or symbol
        currency = meta.get("currency") or "USD"
        if price is None:
            return None
        return {
            "symbol": symbol,
            "name": name,
            "price": price,
            "currency": currency,
        }
    except Exception:
        return None


def add_watch(user_id, symbol):
    symbol = normalize_symbol(symbol)
    if not symbol:
        return "❌ الرجاء إدخال رمز صحيح"
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (user_id, symbol, created_at) VALUES (?, ?, ?)",
        (user_id, symbol, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return f"✅ تم إضافة {symbol} إلى قائمة المراقبة"


def remove_watch(user_id, symbol):
    symbol = normalize_symbol(symbol)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("DELETE FROM watchlist WHERE user_id = ? AND symbol = ?", (user_id, symbol))
    conn.commit()
    conn.close()
    if cur.rowcount:
        return f"✅ تم حذف {symbol} من قائمة المراقبة"
    return f"⚠️ الرمز {symbol} غير موجود"


def get_watchlist(user_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT symbol FROM watchlist WHERE user_id = ? ORDER BY created_at ASC", (user_id,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


@bot.message_handler(commands=['start'])
def start(message):
    text = """
مرحباً 👋
أنا بوت أسهم مجاني يعمل على Termux

الأوامر:
/price AAPL
/watch AAPL
/watchlist
/remove AAPL
/help
    """
    bot.reply_to(message, text)


@bot.message_handler(commands=['help'])
def help_cmd(message):
    start(message)


@bot.message_handler(commands=['price'])
def price_cmd(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ استخدم: /price AAPL")
        return
    symbol = normalize_symbol(parts[1])
    quote = get_quote(symbol)
    if not quote:
        bot.reply_to(message, f"⚠️ لا توجد بيانات فعليّة لـ {symbol} الآن")
        return
    text = (
        f"📈 {quote['name']} ({quote['symbol']})\n"
        f"💰 السعر: {quote['price']:.2f} {quote['currency']}"
    )
    bot.reply_to(message, text)


@bot.message_handler(commands=['watch'])
def watch_cmd(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ استخدم: /watch AAPL")
        return
    symbol = normalize_symbol(parts[1])
    bot.reply_to(message, add_watch(message.from_user.id, symbol))


@bot.message_handler(commands=['remove'])
def remove_cmd(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ استخدم: /remove AAPL")
        return
    symbol = normalize_symbol(parts[1])
    bot.reply_to(message, remove_watch(message.from_user.id, symbol))


@bot.message_handler(commands=['watchlist'])
def watchlist_cmd(message):
    items = get_watchlist(message.from_user.id)
    if not items:
        bot.reply_to(message, "📭 قائمة المراقبة فارغة")
        return
    text = "📋 قائمة المراقبة:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(items))
    bot.reply_to(message, text)


@bot.message_handler(func=lambda m: True)
def default_reply(message):
    bot.reply_to(message, "👋 استخدم /help أو /price AAPL")


if __name__ == "__main__":
    init_db()
    print("✅ Bot running...")
    bot.infinity_polling(timeout=30)
