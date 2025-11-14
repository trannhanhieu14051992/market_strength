#!/usr/bin/env python3
# bot_server.py  (cloud-ready)
# - Use TELEGRAM_TOKEN env var
# - Read data from ./data_hist (CSV files)
# - Provide /quick command to return score + top5 buy picks
# - Picks filtered: avg previous volume >= 1_000_000 and exclude upcom
# - Target modes: ma / recent / percent

import os
import glob
import math
import io
import json
from datetime import datetime
import logging

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from telegram import BotCommand, __version__ as tg_ver
from telegram import InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------- CONFIG ----------
TELEGRAM_TOKEN = "8246313412:AAHKMq223Ps75C1HhfhEwwHQj5Svl5Tm0Uc"
DATA_DIR = os.getenv("DATA_DIR", "data_hist")
SCORE_FILE = os.getenv("SCORE_FILE", "score.json")
MIN_AVG_VOL = int(os.getenv("MIN_AVG_VOL", "1000000"))  # 1,000,000
VOL_WINDOW = int(os.getenv("VOL_WINDOW", "10"))
MA_SHORT = int(os.getenv("MA_SHORT", "20"))
MA_LONG = int(os.getenv("MA_LONG", "50"))
RECENT_LOW_DAYS = int(os.getenv("RECENT_LOW_DAYS", "5"))
RECENT_HIGH_DAYS = int(os.getenv("RECENT_HIGH_DAYS", "10"))

# ---------- LOGGING ----------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.info("telegram-bot version: %s", tg_ver)

# ---------- UTILITIES ----------

def load_score():
    if not os.path.exists(SCORE_FILE):
        return None
    try:
        with open(SCORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("load_score failed: %s", e)
        return None

def pretty_score_text(score_obj):
    if not score_obj:
        return "Chưa có dữ liệu score.json"
    s = score_obj.get("score", "N/A")
    b = score_obj.get("breadth_pct", "N/A")
    v = score_obj.get("vol_pct", "N/A")
    m = score_obj.get("mom_pct", "N/A")
    lines = [
        "MARKET STRENGTH",
        f"Score: {s}",
        f"Breadth: {b}% | Volume: {v}% | Momentum: {m}%",
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ]
    return "\n".join(lines)

def detect_close_and_vol_columns(df: pd.DataFrame):
    close_candidates = ["close", "Close", "Close*","Giá đóng cửa", "Gia", "Giá", "close_price", "last", "Last", "ClosePrice"]
    vol_candidates = ["volume", "Volume", "Khối lượng", "Vol", "VOL", "volume_traded", "volume"]
    close_col = None
    vol_col = None
    cols = list(df.columns)
    # Normalize common encodings:
    lowcols = [c.lower() for c in cols]
    for c in close_candidates:
        if c.lower() in lowcols:
            close_col = cols[lowcols.index(c.lower())]
            break
    for c in vol_candidates:
        if c.lower() in lowcols:
            vol_col = cols[lowcols.index(c.lower())]
            break
    # fallback: numeric last column for close, numeric near end for volume
    if close_col is None:
        for c in reversed(cols):
            if pd.api.types.is_numeric_dtype(df[c]):
                close_col = c
                break
    if vol_col is None:
        # try to pick another numeric column that's not close_col
        for c in reversed(cols):
            if c == close_col:
                continue
            if pd.api.types.is_numeric_dtype(df[c]):
                vol_col = c
                break
    return close_col, vol_col

def _price_tick(price: float) -> int:
    """Return typical tick size for rounding buy/sell prices."""
    try:
        p = float(price)
    except Exception:
        return 1
    if p < 100: return 1
    if p < 500: return 2
    if p < 1000: return 5
    if p < 5000: return 10
    if p < 20000: return 50
    return 100

def _round_to_tick(price: float, tick: int, direction="nearest") -> int:
    if tick <= 0:
        return int(round(price))
    if direction == "down":
        return int(math.floor(price / tick) * tick)
    if direction == "up":
        return int(math.ceil(price / tick) * tick)
    return int(round(price / tick) * tick)

# ---------- PICK COMPUTATION ----------

def compute_buy_picks(
    n=5,
    target_mode="ma",  # "ma", "recent", "percent"
    min_avg_vol=MIN_AVG_VOL,
    data_dir=DATA_DIR
):
    """
    Scan CSVs in data_dir and return list of picks:
    each pick: {symbol, last, buy, sell, avg_vol, reason}
    Conditions:
      - exclude symbols with 'upcom' in name or starting with '^'
      - avg previous volume (VOL_WINDOW days before last day) >= min_avg_vol
    """
    files = glob.glob(os.path.join(data_dir, "*.csv"))
    picks = []
    for fp in files:
        try:
            sym = os.path.splitext(os.path.basename(fp))[0]
            usym = sym.upper()
            # exclude indices or upcom
            if usym.startswith("^") or "UPCOM" in usym:
                continue
            df = pd.read_csv(fp)
            if df.empty:
                continue
            # unify date/time column
            if "time" in df.columns and "date" not in df.columns:
                df = df.rename(columns={"time": "date"})
            close_col, vol_col = detect_close_and_vol_columns(df)
            if close_col is None or vol_col is None:
                continue
            # ensure numeric
            df = df.dropna(subset=[close_col])
            closes = pd.to_numeric(df[close_col], errors="coerce").dropna().reset_index(drop=True)
            vols = pd.to_numeric(df[vol_col], errors="coerce").replace(0, np.nan)
            if len(closes) < max(MA_LONG + 2, 10):
                continue
            # avg previous volume excluding last row
            prev_vols = vols[:-1].tail(VOL_WINDOW)
            avg_prev_vol = float(prev_vols.mean()) if not prev_vols.empty else 0.0
            if np.isnan(avg_prev_vol) or avg_prev_vol < min_avg_vol:
                continue
            last = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) >= 2 else last
            pct_change = (last - prev) / prev * 100 if prev != 0 else 0.0
            ma_short = float(closes.rolling(MA_SHORT).mean().iloc[-1]) if len(closes) >= MA_SHORT else float("nan")
            ma_long = float(closes.rolling(MA_LONG).mean().iloc[-1]) if len(closes) >= MA_LONG else float("nan")
            # determine raw buy/sell
            if target_mode == "percent":
                raw_buy = last * 0.98
                raw_sell = last * 1.06
                reason = "percent"
            elif target_mode == "recent":
                raw_buy = float(closes.tail(RECENT_LOW_DAYS).min())
                raw_sell = float(closes.tail(RECENT_HIGH_DAYS).max())
                reason = "recent"
            else:  # ma
                raw_buy = ma_short if not math.isnan(ma_short) else last * 0.98
                raw_sell = ma_long if not math.isnan(ma_long) else last * 1.06
                reason = "ma"
            # adjust to ensure buy < last < sell, and round to tick
            tick = _price_tick(last)
            # if raw targets are not on the right side, move them a bit
            if raw_buy >= last:
                raw_buy = max(1, last - tick)
            if raw_sell <= last:
                raw_sell = last + tick
            buy_price = _round_to_tick(raw_buy, tick, direction="down")
            sell_price = _round_to_tick(raw_sell, tick, direction="up")
            # final sanity
            if buy_price <= 0:
                buy_price = max(1, int(last) - tick)
            if sell_price <= buy_price:
                sell_price = buy_price + tick
            # score heuristic (prefer positive momentum and above MA_long)
            score = pct_change + (5 if last > ma_long and not math.isnan(ma_long) else 0)
            picks.append({
                "symbol": sym,
                "last": last,
                "buy": int(buy_price),
                "sell": int(sell_price),
                "avg_vol": int(avg_prev_vol),
                "score": float(score),
                "reason": reason
            })
        except Exception:
            continue
    # sort by score then avg_vol
    if not picks:
        return []
    dfp = pd.DataFrame(picks)
    dfp = dfp.sort_values(by=["score", "avg_vol"], ascending=[False, False]).head(n)
    return dfp.to_dict(orient="records")

# ---------- CHART (optional) ----------

def render_chart_for_symbol(symbol: str, data_dir=DATA_DIR):
    path = os.path.join(data_dir, f"{symbol}.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if "time" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"time": "date"})
    close_col, _ = detect_close_and_vol_columns(df)
    if close_col is None:
        return None
    df["date"] = pd.to_datetime(df.get("date", pd.Series(range(len(df)))), errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date")
    y = pd.to_numeric(df[close_col], errors="coerce").dropna()
    if y.empty:
        return None
    x = df["date"].iloc[-len(y):]
    fig, ax = plt.subplots(figsize=(8,4))
    ax.plot(x, y, linewidth=1.2)
    ax.set_title(symbol)
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf

# ---------- BOT HANDLERS ----------

async def start(update: 'Update', context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "Lệnh sẵn có:\n"
        "/score - Market Strength (từ score.json)\n"
        "/quick [ma|recent|percent] - Score + Top5 gợi ý mua (mặc định ma)\n"
        "/top5 [mode] - Top5 picks alone\n"
        "/chart SYMBOL - gửi chart đơn giản của SYMBOL\n"
    )
    await update.message.reply_text(txt)

async def cmd_score(update: 'Update', context: ContextTypes.DEFAULT_TYPE):
    score = load_score()
    await update.message.reply_text(pretty_score_text(score))

async def cmd_quick(update: 'Update', context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    mode = "ma"
    if len(args) >= 1 and args[0].lower() in ("ma", "recent", "percent"):
        mode = args[0].lower()
    score = load_score()
    header = pretty_score_text(score)
    picks = compute_buy_picks(n=5, target_mode=mode)
    if not picks:
        body = "Không tìm thấy mã phù hợp (đáp ứng điều kiện thanh khoản & dữ liệu)."
    else:
        lines = []
        lines.append(f"TOP {len(picks)} GỢI Ý MUA (mode={mode}):")
        for p in picks:
            lines.append(f"{p['symbol']}: Giá {p['last']:.0f} | Mua {p['buy']} | Bán {p['sell']} | Vol avg {p['avg_vol']}")
        body = "\n".join(lines)
    await update.message.reply_text(header + "\n\n" + body)

async def cmd_top5(update: 'Update', context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    mode = "ma"
    if len(args) >= 1 and args[0].lower() in ("ma", "recent", "percent"):
        mode = args[0].lower()
    picks = compute_buy_picks(n=5, target_mode=mode)
    if not picks:
        await update.message.reply_text("Không tìm thấy mã phù hợp.")
        return
    lines = [f"TOP {len(picks)} PICKS (mode={mode}):"]
    for p in picks:
        lines.append(f"{p['symbol']}: Giá {p['last']:.0f} | Mua {p['buy']} | Bán {p['sell']} | Vol avg {p['avg_vol']}")
    await update.message.reply_text("\n".join(lines))

async def cmd_chart(update: 'Update', context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("Gửi: /chart SYMBOL")
        return
    sym = args[0].upper()
    buf = render_chart_for_symbol(sym)
    if not buf:
        await update.message.reply_text(f"Không tìm thấy dữ liệu cho {sym}")
        return
    await update.message.reply_photo(photo=InputFile(buf, filename=f"{sym}.png"))

# ---------- MAIN ----------

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set. Set environment variable TELEGRAM_TOKEN.")
        return

    # create application
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("quick", cmd_quick))
    app.add_handler(CommandHandler("top5", cmd_top5))
    app.add_handler(CommandHandler("chart", cmd_chart))

    # set commands (async)
    async def _set_cmds():
        try:
            await app.bot.set_my_commands([
                BotCommand("start", "Giới thiệu"),
                BotCommand("score", "Market Strength"),
                BotCommand("quick", "Score + Top5"),
                BotCommand("top5", "Top 5 picks"),
                BotCommand("chart", "Chart SYMBOL"),
            ])
        except Exception:
            logger.exception("set_my_commands failed")

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(_set_cmds())
    except Exception:
        pass

    logger.info("Bot starting (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
