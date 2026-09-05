#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ربات تلگرام فوتبال - نمایش بازی‌های امروز و نتایج دیروز به وقت ایران
Telegram Football Bot - Daily fixtures & yesterday results in Iran timezone (Asia/Tehran)
Source: ESPN (free, no token) + optional football-data.org
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta, time as dtime, timezone
from pathlib import Path

import pytz
import jdatetime
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# ---------- Config ----------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")  # optional: e.g. @my_channel or chat_id
SUBSCRIBERS_FILE = Path(os.getenv("SUBSCRIBERS_FILE", "subscribers.json"))
TEHRAN_TZ = pytz.timezone("Asia/Tehran")
UTC = pytz.utc

# Optional football-data.org token (if provided, will be used as primary)
FOOTBALL_DATA_TOKEN = os.getenv("FOOTBALL_DATA_TOKEN", "")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Helpers: Persian ----------
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# فقط ۶ لیگ درخواستی - بقیه فیلتر می‌شوند
LEAGUE_FA = {
    "English Premier League": "لیگ برتر انگلیس",
    "Premier League": "لیگ برتر انگلیس",
    "Spanish LaLiga": "لالیگا اسپانیا",
    "LaLiga": "لالیگا اسپانیا",
    "Spanish Laliga": "لالیگا اسپانیا",
    "German Bundesliga": "بوندس‌لیگا آلمان",
    "Bundesliga": "بوندس‌لیگا آلمان",
    "Italian Serie A": "سری آ ایتالیا",
    "Serie A": "سری آ ایتالیا",
    "French Ligue 1": "لیگ ۱ فرانسه",
    "Ligue 1": "لیگ ۱ فرانسه",
    "UEFA Champions League": "لیگ قهرمانان اروپا",
    "Champions League": "لیگ قهرمانان اروپا",
}

# فقط این ۶ لیگ نمایش داده می‌شوند (اگر SHOW_ALL=false)
# Champions League + Premier League + LaLiga + Bundesliga + Serie A + Ligue 1
IMPORTANT_KEYWORDS = [
    "Premier League",
    "Champions League",
    "LaLiga",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
]
SHOW_ALL = os.getenv("SHOW_ALL_LEAGUES", "false").lower() in ("true", "1", "yes")

# ---------- Persian Team Names ----------
# ترجمه نام تیم‌ها به فارسی - فقط تیم‌های ۶ لیگ اصلی
TEAM_FA = {
    # --- لیگ برتر انگلیس ---
    "Manchester City": "منچسترسیتی",
    "Man City": "منچسترسیتی",
    "Manchester United": "منچستریونایتد",
    "Man United": "منچستریونایتد",
    "Man Utd": "منچستریونایتد",
    "Liverpool": "لیورپول",
    "Arsenal": "آرسنال",
    "Chelsea": "چلسی",
    "Tottenham Hotspur": "تاتنهام",
    "Tottenham": "تاتنهام",
    "Newcastle United": "نیوکاسل",
    "Newcastle": "نیوکاسل",
    "Aston Villa": "استون ویلا",
    "Brighton & Hove Albion": "برایتون",
    "Brighton": "برایتون",
    "West Ham United": "وستهم",
    "West Ham": "وستهم",
    "Crystal Palace": "کریستال پالاس",
    "Fulham": "فولام",
    "Wolverhampton Wanderers": "ولورهمپتون",
    "Wolves": "ولورهمپتون",
    "Everton": "اورتون",
    "Brentford": "برنتفورد",
    "Bournemouth": "بورنموث",
    "Nottingham Forest": "ناتینگهام فارست",
    "Nottm Forest": "ناتینگهام فارست",
    "Leicester City": "لسترسیتی",
    "Leicester": "لسترسیتی",
    "Ipswich Town": "ایپسویچ",
    "Southampton": "ساوتهمپتون",
    "Leeds United": "لیدز",
    "Leeds": "لیدز",
    "Burnley": "برنلی",
    "Sunderland": "ساندرلند",

    # --- لالیگا اسپانیا ---
    "Real Madrid": "رئال مادرید",
    "Barcelona": "بارسلونا",
    "Atletico Madrid": "اتلتیکو مادرید",
    "Atletico": "اتلتیکو مادرید",
    "Athletic Bilbao": "اتلتیک بیلبائو",
    "Athletic Club": "اتلتیک بیلبائو",
    "Real Sociedad": "رئال سوسیداد",
    "Villarreal": "ویارئال",
    "Real Betis": "رئال بتیس",
    "Betis": "رئال بتیس",
    "Sevilla": "سویا",
    "Valencia": "والنسیا",
    "Girona": "ژیرونا",
    "Getafe": "ختافه",
    "Osasuna": "اوساسونا",
    "Celta Vigo": "سلتاویگو",
    "Celta": "سلتاویگو",
    "Rayo Vallecano": "رایو وایکانو",
    "Mallorca": "مایورکا",
    "Alaves": "آلاوس",
    "Las Palmas": "لاس پالماس",
    "Leganes": "لگانس",
    "Espanyol": "اسپانیول",
    "Valladolid": "وایادولید",

    # --- بوندس‌لیگا آلمان ---
    "Bayern Munich": "بایرن مونیخ",
    "Bayern München": "بایرن مونیخ",
    "Bayer Leverkusen": "بایر لورکوزن",
    "Leverkusen": "بایر لورکوزن",
    "Borussia Dortmund": "دورتموند",
    "Dortmund": "دورتموند",
    "RB Leipzig": "لایپزیش",
    "Leipzig": "لایپزیش",
    "VfB Stuttgart": "اشتوتگارت",
    "Stuttgart": "اشتوتگارت",
    "Eintracht Frankfurt": "اینتراخت فرانکفورت",
    "Frankfurt": "اینتراخت فرانکفورت",
    "Borussia Monchengladbach": "گلادباخ",
    "M'gladbach": "گلادباخ",
    "Werder Bremen": "وردربرمن",
    "Bremen": "وردربرمن",
    "Hoffenheim": "هوفنهایم",
    "Wolfsburg": "وولفسبورگ",
    "Freiburg": "فرایبورگ",
    "Augsburg": "آگزبورگ",
    "Mainz": "ماینتس",
    "Mainz 05": "ماینتس",
    "Union Berlin": "یونیون برلین",
    "Heidenheim": "هایدنهایم",
    "St Pauli": "سن پائولی",
    "Holstein Kiel": "هولشتاین کیل",
    "Bochum": "بوخوم",

    # --- سری آ ایتالیا ---
    "Inter Milan": "اینتر",
    "Inter": "اینتر",
    "Internazionale": "اینتر",
    "AC Milan": "میلان",
    "Milan": "میلان",
    "Juventus": "یوونتوس",
    "Napoli": "ناپولی",
    "Roma": "آ اس رم",
    "AS Roma": "آ اس رم",
    "Lazio": "لاتزیو",
    "Atalanta": "آتالانتا",
    "Fiorentina": "فیورنتینا",
    "Bologna": "بولونیا",
    "Torino": "تورینو",
    "Udinese": "اودینزه",
    "Sassuolo": "ساسولو",
    "Empoli": "امپولی",
    "Monza": "مونزا",
    "Cagliari": "کالیاری",
    "Verona": "ورونا",
    "Hellas Verona": "ورونا",
    "Genoa": "جنوا",
    "Lecce": "لچه",
    "Parma": "پارما",
    "Como": "کومو",
    "Venezia": "ونتزیا",

    # --- لیگ ۱ فرانسه ---
    "Paris Saint-Germain": "پاری سن ژرمن",
    "PSG": "پاری سن ژرمن",
    "Marseille": "مارسی",
    "Olympique Marseille": "مارسی",
    "Lyon": "لیون",
    "Olympique Lyonnais": "لیون",
    "Monaco": "موناکو",
    "AS Monaco": "موناکو",
    "Lille": "لیل",
    "Rennes": "رن",
    "Nice": "نیس",
    "Lens": "لانس",
    "Strasbourg": "استراسبورگ",
    "Nantes": "نانت",
    "Toulouse": "تولوز",
    "Montpellier": "مون‌پلیه",
    "Reims": "رنس",
    "Brest": "برست",
    "Le Havre": "لو آور",
    "Auxerre": "اوسر",
    "Angers": "آنژه",
    "Saint-Etienne": "سن اتین",

    # --- لیگ قهرمانان اروپا - تیم‌های مطرح دیگر ---
    "Benfica": "بنفیکا",
    "Porto": "پورتو",
    "Sporting CP": "اسپورتینگ",
    "Ajax": "آژاکس",
    "PSV": "آیندهوون",
    "Feyenoord": "فاینورد",
    "Celtic": "سلتیک",
    "Rangers": "رنجرز",
    "Galatasaray": "گالاتاسرای",
    "Fenerbahce": "فنرباغچه",
    "Club Brugge": "کلوب بروژ",
    "Shakhtar Donetsk": "شاختار دونتسک",
    "Shakhtar": "شاختار",
    "Red Bull Salzburg": "سالزبورگ",
    "Young Boys": "یانگ بویز",
    "Dinamo Zagreb": "دینامو زاگرب",
}

WEEKDAYS_FA = {
    "Saturday": "شنبه",
    "Sunday": "یکشنبه",
    "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه",
    "Wednesday": "چهارشنبه",
    "Thursday": "پنجشنبه",
    "Friday": "جمعه",
}

def to_persian_digits(text: str) -> str:
    return str(text).translate(PERSIAN_DIGITS)

def translate_league(name: str) -> str:
    if not name:
        return "سایر رقابت‌ها"
    # Try exact, then contains
    if name in LEAGUE_FA:
        return LEAGUE_FA[name]
    for k, v in LEAGUE_FA.items():
        if k.lower() in name.lower() or name.lower() in k.lower():
            return v
    return name

def translate_team(name: str) -> str:
    if not name:
        return name
    name = name.strip()
    # exact match first
    if name in TEAM_FA:
        return TEAM_FA[name]
    # case-insensitive exact
    lower_map = {k.lower(): v for k, v in TEAM_FA.items()}
    if name.lower() in lower_map:
        return lower_map[name.lower()]
    # partial contains (e.g., "Inter Milan" vs "Inter")
    for k, v in TEAM_FA.items():
        if k.lower() == name.lower():
            return v
    return name  # fallback: keep original if not found - you can add it to TEAM_FA above

def jalali_date_str(greg_date) -> str:
    """greg_date: datetime.date or datetime; returns Persian Jalali string"""
    if isinstance(greg_date, datetime):
        greg_date = greg_date.date()
    jd = jdatetime.date.fromgregorian(date=greg_date)
    # jdatetime strftime gives Persian month names already
    # Format: جمعه ۱۴ شهریور ۱۴۰۴
    weekday_en = greg_date.strftime("%A")
    weekday_fa = WEEKDAYS_FA.get(weekday_en, weekday_en)
    months_fa = ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"]
    month_fa = months_fa[jd.month - 1]
    day_persian = to_persian_digits(str(jd.day))
    year_persian = to_persian_digits(str(jd.year))
    return f"{weekday_fa} {day_persian} {month_fa} {year_persian}"

def gregorian_str(greg_date) -> str:
    return greg_date.strftime("%Y-%m-%d")

# ---------- Data Fetching ----------
def fetch_espn_for_greg_date(greg_date) -> list:
    """Fetch from ESPN all/scoreboard for a given Gregorian date (date object). Returns list of events."""
    yyyymmdd = greg_date.strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates={yyyymmdd}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        events = data.get("events", [])
        logger.info(f"ESPN {yyyymmdd}: {len(events)} events")
        return events
    except Exception as e:
        logger.error(f"ESPN fetch failed for {yyyymmdd}: {e}")
        return []

def parse_espn_events(events: list) -> list:
    """Parse ESPN events into unified format."""
    parsed = []
    for e in events:
        try:
            comp = e.get("competitions", [{}])[0]
            status = comp.get("status", {}).get("type", {})
            state = status.get("state", "pre")  # pre, in, post
            completed = status.get("completed", False)
            detail = status.get("shortDetail") or status.get("description", "")
            league = comp.get("altGameNote") or (comp.get("notes", [{}])[0].get("headline") if comp.get("notes") else None)
            season_slug = e.get("season", {}).get("slug", "")
            # Fallback handling - detect NCAA / college noise
            if not league or league.strip() == "" or league == "سایر":
                if season_slug:
                    # Clean slug: e.g. 2026-27-english-premier-league -> English Premier League
                    # Keep raw for filtering
                    league = season_slug.replace("-", " ").title()
                else:
                    league = "سایر"
            # date UTC
            date_utc_str = e.get("date") or comp.get("date")
            dt_utc = datetime.fromisoformat(date_utc_str.replace("Z", "+00:00"))
            dt_utc = dt_utc.astimezone(UTC)
            dt_tehran = dt_utc.astimezone(TEHRAN_TZ)
            # teams
            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors)>1 else {})
            home_team_raw = home.get("team", {}).get("displayName") or home.get("team", {}).get("name") or "؟"
            away_team_raw = away.get("team", {}).get("displayName") or away.get("team", {}).get("name") or "؟"
            home_team = translate_team(home_team_raw)
            away_team = translate_team(away_team_raw)
            home_score = home.get("score")
            away_score = away.get("score")
            venue = comp.get("venue", {}).get("fullName", "")
            parsed.append({
                "league": league,
                "league_fa": translate_league(league),
                "season_slug": season_slug,
                "date_utc": dt_utc,
                "date_tehran": dt_tehran,
                "home": home_team,
                "away": away_team,
                "home_raw": home_team_raw,
                "away_raw": away_team_raw,
                "home_score": home_score,
                "away_score": away_score,
                "status_state": state,
                "completed": completed,
                "status_detail": detail,
                "venue": venue,
                "raw": e,
            })
        except Exception as ex:
            logger.warning(f"parse error: {ex}")
            continue
    return parsed

def is_important_match(m) -> bool:
    if SHOW_ALL:
        return True
    league = m.get("league", "")
    league_fa = m.get("league_fa", "")
    slug = m.get("season_slug", "")
    combined = f"{league} {slug}".lower()
    # Strict: only allow the 6 leagues - check if translated (means it's one of the 6)
    # Also check keyword whitelist
    if "ncaa" in slug.lower() or "ncaa" in league.lower():
        return False
    if league.strip() in ("سایر", "سایر رقابت‌ها"):
        return False
    # If league_fa is one of our 6 Persian names, it's allowed
    allowed_fa = set(LEAGUE_FA.values())
    if league_fa in allowed_fa:
        return True
    for kw in IMPORTANT_KEYWORDS:
        if kw.lower() in combined:
            return True
    return False

def filter_important(matches: list) -> list:
    filtered = [m for m in matches if is_important_match(m)]
    # Strict mode: do NOT fallback to other leagues. If no match, return empty -> will show "no match" message.
    # Only fallback if SHOW_ALL is somehow expected
    return filtered

def chunk_message(text: str, limit: int = 4000) -> list:
    """Split long message into chunks respecting line boundaries."""
    if len(text) <= limit:
        return [text]
    lines = text.split("\n")
    chunks = []
    cur = ""
    for line in lines:
        if len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = line + "\n"
        else:
            cur += line + "\n"
    if cur:
        chunks.append(cur)
    return chunks

async def send_chunked(bot, chat_id, text: str):
    for chunk in chunk_message(text):
        await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=ParseMode.HTML)

def fetch_matches_for_tehran_date(target_date, filter_important_flag=True) -> list:
    """
    target_date: date object in Tehran timezone (the day we want to display)
    Fetches ESPN for target_date and target_date+1 UTC dates and filters by Tehran date.
    """
    # Fetch for target_date and adjacent days to cover Tehran's UTC overlap (Tehran +3:30)
    candidates = []
    for delta in [-1, 0, 1]:
        d = target_date + timedelta(days=delta)
        events = fetch_espn_for_greg_date(d)
        candidates.extend(parse_espn_events(events))
    
    # Deduplicate by id
    seen = {}
    for m in candidates:
        key = m["raw"].get("id")
        if key not in seen:
            seen[key] = m
    
    # Filter where Tehran date == target_date
    filtered = [m for m in seen.values() if m["date_tehran"].date() == target_date]
    # Sort by time
    filtered.sort(key=lambda x: x["date_tehran"])
    if filter_important_flag:
        filtered = filter_important(filtered)
    return filtered

def fetch_matches_yesterday_tehran() -> list:
    yesterday = (datetime.now(TEHRAN_TZ).date() - timedelta(days=1))
    return fetch_matches_for_tehran_date(yesterday)

def fetch_matches_today_tehran() -> list:
    today = datetime.now(TEHRAN_TZ).date()
    return fetch_matches_for_tehran_date(today)

# Optional: football-data.org fallback
def fetch_football_data(date_from, date_to):
    if not FOOTBALL_DATA_TOKEN:
        return []
    url = f"https://api.football-data.org/v4/matches?dateFrom={date_from}&dateTo={date_to}"
    try:
        r = requests.get(url, headers={"X-Auth-Token": FOOTBALL_DATA_TOKEN}, timeout=15)
        r.raise_for_status()
        data = r.json()
        matches = data.get("matches", [])
        logger.info(f"football-data {date_from} -> {len(matches)}")
        return matches
    except Exception as e:
        logger.error(f"football-data error: {e}")
        return []

# ---------- Message Formatting ----------
def format_today_message(matches: list, target_date) -> str:
    jalali = jalali_date_str(target_date)
    greg = to_persian_digits(gregorian_str(target_date))
    header = f"⚽️ <b>برنامه بازی‌های امروز</b> ⚽️\n"
    header += f"📅 {jalali} | {greg}\n"
    header += f"🕰 به وقت ایران (Asia/Tehran)\n"
    header += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    if not matches:
        header += "😴 امروز بازی مهمی ثبت نشده است.\n"
        header += "فردا دوباره امتحان کنید!\n"
        return header

    # Group by league
    from collections import defaultdict
    grouped = defaultdict(list)
    for m in matches:
        grouped[m["league_fa"]].append(m)

    body = ""
    for league, games in grouped.items():
        body += f"🏆 <b>{league}</b>\n"
        for g in games:
            t = g["date_tehran"].strftime("%H:%M")
            t_fa = to_persian_digits(t)
            # status
            if g["status_state"] == "pre":
                status_emoji = "🕐"
                time_part = f"{status_emoji} ساعت {t_fa}"
                body += f"  {time_part} — {g['home']} 🆚 {g['away']}\n"
            elif g["status_state"] == "in":
                status_emoji = "🔴"
                body += f"  {status_emoji} در حال برگزاری: {g['home']} {to_persian_digits(g['home_score'] or '0')} - {to_persian_digits(g['away_score'] or '0')} {g['away']} ({g['status_detail']})\n"
            else:
                # completed but still today (maybe early finished)
                status_emoji = "✅"
                body += f"  {status_emoji} {g['home']} {to_persian_digits(g['home_score'])} - {to_persian_digits(g['away_score'])} {g['away']} (پایان)\n"
            if g["venue"]:
                body += f"     🏟 {g['venue']}\n"
        body += "\n"

    footer = f"━━━━━━━━━━━━━━━━━━━━\n"
    footer += f"🤖 ربات فوتبال | به‌روزرسانی روزانه ساعت ۹ صبح\n"
    return header + body + footer

def format_yesterday_results(matches: list, target_date) -> str:
    jalali = jalali_date_str(target_date)
    greg = to_persian_digits(gregorian_str(target_date))
    header = f"📊 <b>نتایج بازی‌های دیروز</b> 📊\n"
    header += f"📅 {jalali} | {greg}\n"
    header += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    if not matches:
        header += "😕 نتیجه‌ای برای دیروز ثبت نشد.\n"
        return header

    from collections import defaultdict
    grouped = defaultdict(list)
    for m in matches:
        grouped[m["league_fa"]].append(m)

    body = ""
    # Filter to only completed / post
    for league, games in grouped.items():
        # if all are not completed, skip?
        body += f"🏆 <b>{league}</b>\n"
        for g in games:
            hs = g["home_score"] if g["home_score"] is not None else "-"
            as_ = g["away_score"] if g["away_score"] is not None else "-"
            hs_fa = to_persian_digits(hs)
            as_fa = to_persian_digits(as_)
            t = g["date_tehran"].strftime("%H:%M")
            t_fa = to_persian_digits(t)
            if g["completed"] or g["status_state"] == "post":
                # Determine winner emoji
                try:
                    if int(hs) > int(as_):
                        body += f"  ✅ {g['home']} {hs_fa} - {as_fa} {g['away']}  (⏰ {t_fa})\n"
                    elif int(hs) < int(as_):
                        body += f"  ✅ {g['away']} {as_fa} - {hs_fa} {g['home']}  (⏰ {t_fa})\n"
                    else:
                        body += f"  🤝 {g['home']} {hs_fa} - {as_fa} {g['away']} (مساوی) ⏰ {t_fa}\n"
                except:
                    body += f"  ⚽️ {g['home']} {hs_fa} - {as_fa} {g['away']} ⏰ {t_fa}\n"
            elif g["status_state"] == "in":
                body += f"  🔴 در جریان: {g['home']} {hs_fa} - {as_fa} {g['away']} ({g['status_detail']})\n"
            else:
                body += f"  🕐 لغو/به تعویق: {g['home']} 🆚 {g['away']} ⏰ {t_fa}\n"
        body += "\n"

    footer = f"━━━━━━━━━━━━━━━━━━━━\n"
    footer += f"📈 نتایج به وقت ایران\n"
    return header + body + footer

def build_daily_messages():
    """Build both messages for today and yesterday"""
    today = datetime.now(TEHRAN_TZ).date()
    yesterday = today - timedelta(days=1)
    today_matches = fetch_matches_for_tehran_date(today)
    yesterday_matches = fetch_matches_for_tehran_date(yesterday)
    msg_today = format_today_message(today_matches, today)
    msg_yesterday = format_yesterday_results(yesterday_matches, yesterday)
    return msg_today, msg_yesterday

# ---------- Subscribers Persistence ----------
def load_subscribers():
    if SUBSCRIBERS_FILE.exists():
        try:
            return set(json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8")))
        except:
            return set()
    return set()

def save_subscribers(subs):
    SUBSCRIBERS_FILE.write_text(json.dumps(list(subs), ensure_ascii=False, indent=2), encoding="utf-8")

subscribers = load_subscribers()

# ---------- Telegram Handlers ----------
HELP_TEXT = """
🇮🇷 <b>ربات فوتبال فارسی</b> 🇮🇷

<b>دستورات:</b>
/start - شروع و عضویت در خبرنامه روزانه
/today - نمایش بازی‌های مهم امروز به وقت ایران
/all - نمایش همه بازی‌های امروز (بدون فیلتر)
/yesterday - نمایش نتایج مهم دیروز
/results - همان نتایج دیروز
/daily - ارسال هر دو (امروز + دیروز)
/help - راهنما
/subscribe - عضویت در ارسال خودکار روزانه
/unsubscribe - لغو عضویت

⏰ ربات هر روز ساعت <b>۹ صبح به وقت ایران</b> به صورت خودکار برنامه امروز و نتایج دیروز را ارسال می‌کند.

⚙️ برای کانال: متغیر CHANNEL_ID را در .env تنظیم کنید.
💡 برای نمایش همه لیگ‌ها: <code>SHOW_ALL_LEAGUES=true</code> در .env
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    save_subscribers(subscribers)
    await update.message.reply_text(
        f"سلام {update.effective_user.first_name} عزیز! 👋\n\n"
        "به ربات فوتبال خوش آمدی! ⚽️\n"
        "هر روز ساعت ۹ صبح بازی‌های امروز و نتایج دیروز را به وقت ایران برات می‌فرستم.\n\n"
        "برای دیدن بازی‌های امروز /today را بزن.",
        parse_mode=ParseMode.HTML
    )
    # Also send today immediately
    await send_today(update, context)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)

async def send_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 در حال دریافت بازی‌های امروز...", parse_mode=ParseMode.HTML)
    today = datetime.now(TEHRAN_TZ).date()
    matches = fetch_matches_for_tehran_date(today)
    msg = format_today_message(matches, today)
    for chunk in chunk_message(msg):
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)

async def send_yesterday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 در حال دریافت نتایج دیروز...", parse_mode=ParseMode.HTML)
    yest = datetime.now(TEHRAN_TZ).date() - timedelta(days=1)
    matches = fetch_matches_for_tehran_date(yest)
    msg = format_yesterday_results(matches, yest)
    for chunk in chunk_message(msg):
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)

async def send_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 در حال دریافت برنامه کامل...", parse_mode=ParseMode.HTML)
    msg_today, msg_yest = build_daily_messages()
    for chunk in chunk_message(msg_today):
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
    for chunk in chunk_message(msg_yest):
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    save_subscribers(subscribers)
    await update.message.reply_text("✅ عضو خبرنامه روزانه شدی! هر روز ساعت ۹ صبح پیام دریافت می‌کنی.", parse_mode=ParseMode.HTML)

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.discard(chat_id)
    save_subscribers(subscribers)
    await update.message.reply_text("❌ از خبرنامه روزانه خارج شدی.", parse_mode=ParseMode.HTML)

async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue callback: send to all subscribers and channel"""
    logger.info("Running daily_job")
    try:
        msg_today, msg_yest = build_daily_messages()
        # send to subscribers
        for chat_id in list(subscribers):
            try:
                await send_chunked(context.bot, chat_id, msg_today)
                await send_chunked(context.bot, chat_id, msg_yest)
            except Exception as e:
                logger.warning(f"Failed to send to {chat_id}: {e}")
        # send to channel if configured
        if CHANNEL_ID:
            try:
                await send_chunked(context.bot, CHANNEL_ID, msg_today)
                await send_chunked(context.bot, CHANNEL_ID, msg_yest)
                logger.info(f"Sent to channel {CHANNEL_ID}")
            except Exception as e:
                logger.warning(f"Channel send failed: {e}")
    except Exception as e:
        logger.exception(f"daily_job error: {e}")

def _start_health_server():
    """Optional tiny HTTP server for PaaS like Render/Koyeb that require a port to be bound."""
    port = os.getenv("PORT")
    if not port:
        return
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading
        p = int(port)
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write("Bot is running ✅".encode())
            def log_message(self, *args, **kw):
                pass
        def serve():
            httpd = HTTPServer(("0.0.0.0", p), H)
            logger.info(f"Health server listening on port {p}")
            httpd.serve_forever()
        threading.Thread(target=serve, daemon=True).start()
    except Exception as e:
        logger.warning(f"Health server failed: {e}")

def main():
    _start_health_server()
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set! Create .env from .env.example and fill it.")
        print("  Get token from @BotFather on Telegram")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔍 در حال دریافت همه بازی‌های امروز (بدون فیلتر)...", parse_mode=ParseMode.HTML)
        today = datetime.now(TEHRAN_TZ).date()
        matches = fetch_matches_for_tehran_date(today, filter_important_flag=False)
        msg = format_today_message(matches, today)
        for chunk in chunk_message(msg):
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("today", send_today))
    app.add_handler(CommandHandler("all", send_all))
    app.add_handler(CommandHandler("yesterday", send_yesterday))
    app.add_handler(CommandHandler("results", send_yesterday))
    app.add_handler(CommandHandler("daily", send_daily))
    app.add_handler(CommandHandler("emrooz", send_today))
    app.add_handler(CommandHandler("dirooz", send_yesterday))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # Schedule daily at 09:00 Tehran time
    # JobQueue runs in UTC, so convert 09:00 Tehran -> 05:30 UTC
    tehran_9 = dtime(hour=9, minute=0, tzinfo=TEHRAN_TZ)
    # For python-telegram-bot v20+, we can pass time with timezone
    try:
        app.job_queue.run_daily(daily_job, time=tehran_9, name="daily_9am_tehran")
        logger.info("Scheduled daily job at 09:00 Asia/Tehran")
    except Exception as e:
        logger.warning(f"JobQueue schedule failed: {e}, trying UTC fallback")
        utc_530 = dtime(hour=5, minute=30, tzinfo=timezone.utc)
        app.job_queue.run_daily(daily_job, time=utc_530, name="daily_530utc")

    # Also allow manual trigger via /daily

    print("🤖 ربات فعال شد | Bot is running...")
    print(f"📅 Today Tehran: {datetime.now(TEHRAN_TZ).date()}  | Jalali: {jalali_date_str(datetime.now(TEHRAN_TZ).date())}")
    print("   Commands: /today /yesterday /daily")
    print("   Auto send daily at 09:00 Asia/Tehran")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
