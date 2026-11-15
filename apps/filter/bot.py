# -*- coding: utf-8 -*-

import psycopg2
from psycopg2.extras import RealDictCursor
import threading
import copy
import secrets
import hashlib
import time
import os
import html
import traceback
from datetime import datetime, timedelta

import telebot
from telebot import types
from flask import Flask, request

# =========================
# Flask Keep-Alive / Health Server
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!", 200

@app.route("/health")
def health():
    return "OK", 200


# =========================
# Telegram Webhook
# =========================
# Render Free services sleep after inactivity. Telegram polling cannot wake
# a sleeping Render service because polling requires the Python process to
# already be running. Webhook mode fixes this: Telegram sends the user's
# update as an HTTP request, which wakes the Render Web Service.
WEBHOOK_PATH = "/telegram-webhook"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") or os.environ.get("RENDER_EXTERNAL_URL")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")


@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    if WEBHOOK_SECRET:
        incoming_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if incoming_secret != WEBHOOK_SECRET:
            return "Forbidden", 403

    try:
        if not request.is_json:
            return "Bad Request", 400

        raw_update = request.get_json(silent=True)
        print("WEBHOOK UPDATE RECEIVED | keys=", list(raw_update.keys()) if isinstance(raw_update, dict) else type(raw_update).__name__)
        update = telebot.types.Update.de_json(raw_update)
        if update is None:
            print("WEBHOOK ERROR | Update.de_json returned None")
            return "Bad Request", 400

        # Log the exact Telegram message/callback route without exposing bot token.
        try:
            if getattr(update, "message", None):
                print("WEBHOOK MESSAGE | text=", repr(getattr(update.message, "text", None)),
                      "| user=", getattr(update.message.from_user, "id", None))
            if getattr(update, "callback_query", None):
                print("WEBHOOK CALLBACK | data=", repr(update.callback_query.data),
                      "| user=", getattr(update.callback_query.from_user, "id", None))
        except Exception:
            pass

        bot.process_new_updates([update])
        return "OK", 200
    except Exception as error:
        print("WEBHOOK PROCESSING ERROR |", repr(error))
        traceback.print_exc()
        # Telegram already delivered the update. Return 200 so it is not retried forever.
        return "OK", 200


def setup_telegram_webhook():
    """
    Configure Telegram to deliver updates to this Render Web Service.
    On Render, RENDER_EXTERNAL_URL is provided automatically.
    WEBHOOK_URL can be set manually when running somewhere else.
    """
    if not WEBHOOK_URL:
        print("WEBHOOK_URL/RENDER_EXTERNAL_URL پیدا نشد؛ webhook فعال نشد.")
        return False

    try:
        bot.remove_webhook()
        time.sleep(0.2)

        kwargs = {}
        if WEBHOOK_SECRET:
            kwargs["secret_token"] = WEBHOOK_SECRET

        full_url = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH
        if not full_url.lower().startswith("https://"):
            print("WEBHOOK ERROR | URL must start with https:// |", full_url)
            return False
        bot.set_webhook(url=full_url, **kwargs)

        print("Telegram webhook فعال شد:", full_url)
        try:
            info = bot.get_webhook_info()
            print(
                "WEBHOOK INFO | url=", getattr(info, "url", None),
                "| pending=", getattr(info, "pending_update_count", None),
                "| last_error=", getattr(info, "last_error_message", None)
            )
        except Exception as info_error:
            print("WEBHOOK INFO ERROR |", repr(info_error))
        return True
    except Exception as error:
        print("خطا در فعال‌سازی Telegram webhook:", error)
        return False


def run_flask():
    # Hosting services such as Render/Railway normally provide PORT.
    # 8000 is used locally if PORT is not defined.
    try:
        port = int(os.environ.get("PORT", "8000"))
    except (TypeError, ValueError):
        port = 8000

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True
    )




# =========================
# تنظیمات اصلی
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required.")

OWNER_ID = int(os.environ.get("OWNER_ID", "6914909647"))

DEFAULT_DELETE_AFTER = 17

DEFAULT_SUB_DAYS = 30


# =========================
# راه‌اندازی ربات و دیتابیس
# =========================


bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# =========================
# سیستم زبان سراسری ربات
# =========================
# تمام پیام‌های خروجی و متن دکمه‌ها هنگام انتخاب English به انگلیسی
# تبدیل می‌شوند. زبان در user_preferences ذخیره می‌شود.
EN_TEXT_MAP = {'📢 کانال\u200cهای اجباری:\n\n': '📢 Mandatory channels:\n\n', '👥 لیست ادمین\u200cها:\n\n': '👥 Admin list:\n\n', '📂 فایل\u200cهای ثبت\u200cشده:\n\n': '📂 Registered files:\n\n', '📤 آپلود فایل': '📤 Upload file', '📂 فایل\u200cهای من': '📂 My files', '📊 آمار من': '📊 My stats', '📢 مدیریت کانال\u200cها': '📢 Manage channels', '💳 وضعیت اشتراک': '💳 Subscription status', '💎 تمدید / خرید اشتراک': '💎 Buy / Renew subscription', '🎁 اشتراک رایگان ۳ روزه': '🎁 3-Day Free Trial', '🌐 زبان / Language': '🌐 Language', '❌ بستن پنل': '❌ Close panel', '👥 مدیریت ادمین\u200cها': '👥 Manage admins', '➕ افزودن ادمین': '➕ Add admin', '➖ حذف ادمین': '➖ Remove admin', '💰 درآمد': '💰 Revenue', '📊 آمار کل': '📊 Global stats', '📂 همه فایل\u200cها': '📂 All files', '💎 مدیریت اشتراک\u200cها': '💎 Subscription plans', '📢 همه کانال\u200cها': '📢 All channels', '⏱ تنظیم حذف خودکار': '⏱ Auto-delete settings', '🌐 زبان انتخاب شد: فارسی': '🌐 Language selected: Persian', '🌐 زبان را انتخاب کنید / Choose your language:': '🌐 Please choose your language:', '🌐 زبان را انتخاب کنید / Please choose your language:': '🌐 Please choose your language:', 'سلام! 👋\nاین ربات برای دریافت فایل استفاده می\u200cشود.': 'Hello! 👋\nThis bot is used to receive files.', '💎 خرید / تمدید اشتراک': '💎 Buy / Renew subscription', '🎁 دوره آزمایشی رایگان ۳ روزه': '🎁 3-Day Free Trial', '🎁 شما می\u200cتوانید ۳ روز اشتراک رایگان دریافت کنید.': '🎁 You are eligible for a 3-day free trial.', '✅ دوره آزمایشی رایگان شما فعال شد.\n⏳ مدت: ۳ روز\n📅 پایان: {expire}': '✅ Your free trial is now active.\n⏳ Duration: 3 days\n📅 Expires: {expire}', '❌ شما قبلاً از دوره آزمایشی رایگان استفاده کرده\u200cاید.': '❌ You have already used your free trial.', 'ℹ️ شما در حال حاضر یک اشتراک فعال دارید. دوره آزمایشی رایگان برای شما فعال نشد.': 'ℹ️ You already have an active subscription. The free trial was not activated.', '❌ فعال\u200cسازی دوره آزمایشی انجام نشد. لطفاً دوباره تلاش کنید.': '❌ The free trial could not be activated. Please try again.', 'فعلاً هیچ پلن فعالی وجود ندارد.': 'There are no active plans at the moment.', '💎 پلن\u200cهای اشتراک:': '💎 Subscription plans:', '🧾 فاکتور پرداخت در تلگرام برای شما ارسال شد.': '🧾 The payment invoice was sent inside Telegram.', '✅ پرداخت با موفقیت انجام شد و اشتراک شما فعال/تمدید شد.': '✅ Payment completed and your subscription was activated/extended.', '❌ پرداخت ثبت نشد یا اطلاعات پرداخت نامعتبر است.': '❌ Payment could not be registered or the payment information is invalid.', '⛔ فقط مالک به این بخش دسترسی دارد.': '⛔ Owner access only.', '⛔ شما دسترسی ادمین ندارید.': '⛔ You do not have admin access.', '💎 مدیریت پلن\u200cهای اشتراک': '💎 Subscription plan management', '➕ افزودن پلن': '➕ Add plan', '🗑 حذف پلن': '🗑 Delete plan', '📢 همه کانال\u200cهای اجباری': '📢 All mandatory channels', '⏱ تنظیم حذف خودکار برای ادمین': '⏱ Set auto-delete for an admin', '🆔 آیدی عددی ادمین را ارسال کنید.': "🆔 Send the admin's numeric ID.", 'آیدی عددی کاربر را ارسال کنید.': "Send the user's numeric ID.", '⏱ زمان حذف خودکار را به ثانیه ارسال کنید.': '⏱ Send the auto-delete time in seconds.', 'فرمت: نام فارسی | نام انگلیسی | تعداد روز | تعداد ستاره | recurring\nمثال: 30 روزه | 30 Days | 30 | 250 | yes': 'Format: Persian name | English name | days | stars | recurring\nExample: 30 Days | 30 Days | 30 | 250 | yes', '✅ پلن با موفقیت اضافه شد.': '✅ Plan added successfully.', '✅ پلن حذف شد.': '✅ Plan deleted.', '❌ اطلاعات پلن نامعتبر است.': '❌ Invalid plan information.', '❌ فقط عدد مثبت ارسال کنید.': '❌ Send a positive number only.', '❌ فقط یک عدد مثبت ارسال کنید.': '❌ Send a positive number only.', '✅ زمان حذف خودکار ادمین تنظیم شد.': '✅ Admin auto-delete time updated.', 'هیچ کانال اجباری ثبت نشده است.': 'No mandatory channels are registered.', 'هیچ کانالی ثبت نشده است.': 'No channels are registered.', '✅ کانال حذف شد.': '✅ Channel removed.', 'کانال\u200cها حذف شدند.': 'Channels deleted.', '✅ همه کانال\u200cهای اجباری حذف شدند.': '✅ All mandatory channels have been deleted.', '🇮🇷 فارسی': '🇮🇷 Persian', '👑 به پنل مالک خوش آمدید.\nبرای ورود به پنل از /owner استفاده کنید.': '👑 Welcome to the owner panel.\nUse /owner to open the panel.', '🛠 شما ادمین هستید.\nبرای ورود به پنل از /panel استفاده کنید.': '🛠 You are an admin.\nUse /panel to open the admin panel.', '❌ لینک فایل نامعتبر یا منقضی شده است.': '❌ The file link is invalid or expired.', '❌ اشتراک صاحب این فایل منقضی شده یا فایل غیرفعال است.': "❌ The file owner's subscription has expired or the file is inactive.", '⚠️ برای دریافت فایل ابتدا عضو کانال شوید.': '⚠️ Please join the required channel(s) before receiving the file.', '🗑 فایل حذف شد': '🗑 File deleted', '🗑 فایل حذف شد و لینک آن غیرفعال گردید.': '🗑 File deleted and its link has been disabled.', 'لینک دریافت پیدا نشد.': 'Download link not found.', 'فایل دیگر موجود نیست.': 'The file is no longer available.', '⛔ اشتراک شما فعال نیست.': '⛔ Your subscription is not active.', '❌ نوع فایل پشتیبانی نمی\u200cشود.': '❌ This file type is not supported.', 'پنل بسته شد.': 'Panel closed.', '📤 فایل را ارسال کنید.\nفرمت\u200cهای PDF، ZIP، MP4، MP3، عکس، وویس و سایر فایل\u200cها پشتیبانی می\u200cشوند.': '📤 Send the file.\nPDF, ZIP, MP4, MP3, images, voice messages, and other file types are supported.', '⛔ دسترسی ندارید.': '⛔ Access denied.', '📂 هنوز فایلی آپلود نکرده\u200cاید.': '📂 You have not uploaded any files yet.', '📊 آمار شما:\n\n📂 تعداد فایل\u200cها: ': '📊 Your statistics:\n\n📂 Files: ', '\n⬇️ تعداد دانلودها: ': '\n⬇️ Downloads: ', '⛔ ادمین نیستید.': '⛔ You are not an admin.', '💳 وضعیت اشتراک: ': '💳 Subscription status: ', '\n📅 تاریخ پایان: ': '\n📅 Expiration date: ', '🗑 حذف همه کانال\u200cها': '🗑 Delete all channels', 'هیچ ادمینی ثبت نشده است.': 'No admins are registered.', '\n📅 پایان: ': '\n📅 Expires: ', '\n📂 فایل\u200cها: ': '\n📂 Files: ', '\n⬇️ دانلودها: ': '\n⬇️ Downloads: ', '\n📌 وضعیت: ': '\n📌 Status: ', '📊 آمار کلی ربات:\n\n👥 کاربران دریافت\u200cکننده: ': '📊 Global bot statistics:\n\n👥 Users who received files: ', '\n⬇️ کل دانلودها: ': '\n⬇️ Total downloads: ', '\n📂 فایل\u200cهای فعال: ': '\n📂 Active files: ', '\n🛡 تعداد ادمین\u200cها: ': '\n🛡 Admins: ', 'هیچ فایلی وجود ندارد.': 'No files exist.', '\n👤 ادمین: ': '\n👤 Admin: ', '\n⬇️ دانلود: ': '\n⬇️ Downloads: ', '\n📅 تاریخ: ': '\n📅 Date: ', 'دسترسی ندارید.': 'Access denied.', '✅ کپشن فایل ویرایش شد.': '✅ File caption updated.', '✏️ کپشن جدید را ارسال کنید.\nبرای حذف کپشن، عبارت «بدون کپشن» را ارسال کنید.': '✏️ Send the new caption.\nTo remove the caption, send “No caption”.', 'موردی ثبت نشده است.': 'No records found.', '📢 اطلاعات کانال را در یک خط ارسال کنید:\n\nفرمت پیشنهادی:\n@channel_username | https://t.me/channel_username\n\nربات باید در کانال ادمین باشد.': '📢 Send the channel information in one line:\n\nSuggested format:\n@channel_username | https://t.me/channel_username\n\nThe bot must be an admin in the channel.', '📢 افزودن کانال اجباری برای همه فایل\u200cها:\n\n': '📢 Add a mandatory channel for all files:\n\n', 'یا اگر می\u200cخواهید فقط برای یک ادمین باشد:\n': 'Or if you want it only for one admin:\n', '❌ ارسال فایل با خطا مواجه شد.': '❌ Failed to send the file.', '❌ هنوز عضو کانال\u200cهای اجباری نشده\u200cاید.\nابتدا عضو شوید و دوباره «عضو شدم» را بزنید.': '❌ You have not joined all required channels yet.\nJoin them and press “I joined” again.', '❌ عضویت شما قابل بررسی نیست. لطفاً چند لحظه بعد دوباره تلاش کنید.': '❌ Your membership could not be verified. Please try again in a moment.', '✅ عضویت تأیید شد.': '✅ Membership verified.', '🔒 عضویت اجباری\n\nبرای دریافت فایل ابتدا باید در کانال\u200cهای زیر عضو شوید.\nروی دکمه\u200cهای عضویت بزنید، سپس «✅ عضو شدم» را انتخاب کنید تا عضویت شما بررسی شود.': '🔒 Mandatory membership\n\nYou must join the channels below before receiving the file.\nJoin the channels, then select “✅ I joined” so your membership can be verified.', '📢 عضویت در ': '📢 Join ', '📢 عضویت در کانال': '📢 Join channel', '✅ عضو شدم': '✅ I joined', '📄 نام: ': '📄 Name: ', '📅 تاریخ آپلود: ': '📅 Upload date: ', '\n\n👥 آخرین دریافت\u200cکنندگان:\n': '\n\n👥 Recent recipients:\n', '30 روزه': '30 Days', 'بدون نام': 'Unnamed', 'بدون کپشن': 'No caption', '🔐 این فایل رمز دارد': '🔐 This file is password protected', '🔓 بدون رمز': '🔓 No password', '🔓 بدون رمز / تعیین رمز': '🔓 No password / Set password', '🗑 حذف': '🗑 Delete', '✏️ ویرایش کپشن': '✏️ Edit caption', '📊 آمار دانلود': '📊 Download statistics', '📊 آمار': '📊 Statistics', '🔐 رمز فایل': '🔐 File password', '🔐 دارای رمز': '🔐 Password protected', '➕ افزودن کانال': '➕ Add channel', '💰 درآمد کل:\nبرای ثبت درآمد واقعی، درگاه پرداخت باید به ربات متصل شود.\nدر حال حاضر درآمد ثبت\u200cشده: 0': '💰 Total revenue:\nA payment gateway must be connected to record real revenue.\nCurrently recorded revenue: 0', '❌ ادمین پیدا نشد.': '❌ Admin not found.', '❌ آیدی باید عددی باشد.': '❌ The ID must be numeric.', '❌ admin_id باید عددی باشد.': '❌ admin_id must be numeric.', '❌ فرمت ناقص است.': '❌ Incomplete format.', '❌ این ادمین در ربات ثبت نشده است.': '❌ This admin is not registered in the bot.', '❌ نام/آیدی کانال خالی است.': '❌ Channel name/ID cannot be empty.', '❌ کانال پیدا نشد یا ربات دسترسی لازم ندارد.': '❌ Channel not found or the bot lacks the required access.', '❌ کانال پیدا نشد یا ربات دسترسی لازم ندارد.\nربات را داخل کانال ادمین کنید و دوباره تلاش کنید.': '❌ Channel not found or the bot lacks the required access.\nMake the bot an admin in the channel and try again.', '❌ کانال پیدا نشد یا ربات در کانال دسترسی لازم ندارد.\nربات را داخل کانال ادمین کنید و دوباره تلاش کنید.': '❌ Channel not found or the bot does not have the required access in the channel.\nMake the bot an admin in the channel and try again.', '❌ لینک کانال را وارد کنید.': '❌ Please enter the channel link.', '🔒 عضویت اجباری': '🔒 Mandatory membership', '📢 ورود به کانال': '📢 Join channel', '⚠️ اشتراک شما منقضی شده است.\nآپلود فایل و لینک\u200cهای قبلی غیرفعال شدند.': '⚠️ Your subscription has expired.\nFile uploads and previous links have been disabled.', 'پرداخت دوره\u200cای Telegram Stars باید ۳۰ روزه باشد.': 'Telegram Stars recurring subscriptions must be 30 days.', 'پرداخت اشتراک نامعتبر است.': 'Invalid subscription payment.', 'این اشتراک دیگر در دسترس نیست.': 'This subscription is no longer available.', 'این فاکتور متعلق به کاربر دیگری است.': 'This invoice belongs to another user.', 'واحد پرداخت Telegram Stars نامعتبر است.': 'Invalid Telegram Stars currency.', 'مبلغ پرداخت با قیمت پلن مطابقت ندارد.': 'The payment amount does not match the plan price.', 'اعتبارسنجی پرداخت ناموفق بود.': 'Payment validation failed.', '💳 پشتیبانی پرداخت\n\nاگر از حساب شما Stars کسر شده ولی اشتراک فعال نشده است، رسید پرداخت یا شناسه پرداخت Telegram را برای مالک ربات ارسال کنید.\n\nپرداخت\u200cهای Stars مستقیماً داخل تلگرام انجام می\u200cشوند.': '💳 Payment Support\n\nIf you were charged Stars but your subscription was not activated, please send the payment receipt or Telegram payment charge ID to the bot owner.\n\nTelegram Stars payments are processed inside Telegram.', 'ربات با موفقیت اجرا شد.': 'Bot started successfully.', 'Flask health server نیز در پس\u200cزمینه اجرا شد.': 'Flask health server is also running in the background.', 'همه فایل\u200cها': 'All files', 'ادمین ': 'Admin ', ' ثبت شد.': ' registered.', ' افزوده یا تمدید شد.': ' added or renewed.', ' مسدود شد.': ' blocked.', '✅ ادمین ': '✅ Admin ', '⛔ دسترسی ادمینی شما مسدود شد.': '⛔ Your admin access has been blocked.', 'فایل حذف شد.': 'File deleted.', '❌ این درخواست منقضی شده است.': '❌ This request has expired.', '❌ اطلاعات کانال ناقص است.': '❌ Incomplete channel information.', '📤 فایل را ارسال کنید.': '📤 Send the file.', '✅ فایل ارسال شد\n⏱ این فایل تا ': '✅ File sent\n⏱ This file will be deleted in ', ' ثانیه دیگر حذف خواهد شد': ' seconds.', ' ثانیه تنظیم شد.': ' seconds.', '✅ مدت حذف خودکار روی ': '✅ Auto-delete time set to ', '👤 ادمین: ': '👤 Admin: ', '📌 وضعیت: ': '📌 Status: ', '📅 آپلود: ': '📅 Upload: ', 'بله': 'Yes', 'برای دریافت فایل ابتدا عضو کانال شوید.': 'Please join the required channel(s) before receiving the file.', 'کانال اجباری': 'Mandatory channel', '🔐 تعیین رمز': '🔐 Set password', '➡️ بدون رمز': '➡️ No password', '🔑 تغییر رمز': '🔑 Change password', '🔓 حذف رمز': '🔓 Remove password', '🔒 این فایل دارای رمز عبور است.': '🔒 This file is password protected.', '🔑 رمز عبور را ارسال کنید:': '🔑 Send the file password:', '❌ رمز عبور اشتباه است. دوباره تلاش کنید.': '❌ Incorrect password. Please try again.', '✅ رمز فایل با موفقیت تنظیم شد.': '✅ File password set successfully.', '✅ رمز فایل تغییر کرد.': '✅ File password changed.', '✅ رمز فایل حذف شد.': '✅ File password removed.', '❌ رمز عبور نمی\u200cتواند خالی باشد.': '❌ Password cannot be empty.', '❌ رمز عبور خیلی کوتاه است. حداقل ۴ کاراکتر وارد کنید.': '❌ Password is too short. Use at least 4 characters.', '📄 <b>': '📄 <b>', '🔗 توکن: ': '🔗 Token: ', '🔗 لینک اختصاصی:': '🔗 Private link:', '🆔 شناسه فایل: ': '🆔 File ID: ', '⏱ این فایل تا ': '⏱ This file will be deleted in ', 'فایل ذخیره شد.': 'File saved.', 'ادمین': 'Admin', 'ثبت شد.': 'registered.', 'مسدود شد.': 'blocked.', 'افزوده یا تمدید شد.': 'added or renewed.', 'نام/آیدی': 'name/ID', 'فعال': 'active', 'غیرفعال': 'inactive', '🛠 پنل مدیریت ادمین:': '🛠 Admin management panel:', '👑 پنل مالک:': '👑 Owner panel:', '📊 آمار فایل:': '📊 File statistics:', '\n⬇️ تعداد دانلود: ': '\n⬇️ Downloads: ', '✅ کانال اجباری با موفقیت ثبت شد.': '✅ Mandatory channel added successfully.', 'آیدی عددی ادمین را ارسال کنید.': "Send the admin's numeric ID.", 'لطفاً لینک فایل را از فرستنده دریافت کنید.': 'Please obtain the file link from the sender.', 'اشتراک - ': 'Subscription - ', ' روز / ': ' days / ', '✅ شما به عنوان ادمین ربات فعال شدید.\nبرای ورود از /panel استفاده کنید.': '✅ You have been activated as a bot admin.\nUse /panel to open the admin panel.', '✅ کانال اجباری برای ': '✅ Mandatory channel for '}

def localize_text(user_id, text):
    """Translate bot-generated Persian UI text for an English-speaking user."""
    if not text or get_language(user_id) != "en":
        return text
    result = str(text)
    # Replace longer phrases first so fragments do not break full messages.
    for fa, en in sorted(EN_TEXT_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if fa in result:
            result = result.replace(fa, en)
    return result

def localize_markup(user_id, markup):
    """Translate visible keyboard labels without changing callback data."""
    if not markup or get_language(user_id) != "en":
        return markup
    try:
        cloned = copy.deepcopy(markup)
        keyboard = getattr(cloned, "keyboard", None)
        if keyboard is None:
            keyboard = getattr(cloned, "inline_keyboard", None)
        if keyboard:
            for row in keyboard:
                for button in row:
                    if hasattr(button, "text") and button.text:
                        button.text = localize_text(user_id, button.text)
        return cloned
    except Exception:
        return markup

# Keep references to the original TeleBot methods and transparently localize
# every outgoing private-chat message/callback according to the user's choice.
_original_send_message = bot.send_message
_original_edit_message_text = bot.edit_message_text
_original_answer_callback_query = bot.answer_callback_query
_original_process_new_updates = bot.process_new_updates
_callback_users = {}

def _localized_send_message(chat_id, text, *args, **kwargs):
    try:
        user_id = int(chat_id)
    except Exception:
        user_id = None
    if user_id is not None:
        text = localize_text(user_id, text)
        if "reply_markup" in kwargs:
            kwargs["reply_markup"] = localize_markup(user_id, kwargs["reply_markup"])
    return _original_send_message(chat_id, text, *args, **kwargs)

def _localized_edit_message_text(text, chat_id, message_id, *args, **kwargs):
    try:
        user_id = int(chat_id)
    except Exception:
        user_id = None
    if user_id is not None:
        text = localize_text(user_id, text)
        if "reply_markup" in kwargs:
            kwargs["reply_markup"] = localize_markup(user_id, kwargs["reply_markup"])
    return _original_edit_message_text(text, chat_id, message_id, *args, **kwargs)

def _localized_answer_callback_query(callback_query_id, text=None, *args, **kwargs):
    user_id = _callback_users.pop(callback_query_id, None)
    if user_id is not None and text:
        text = localize_text(user_id, text)
    return _original_answer_callback_query(callback_query_id, text, *args, **kwargs)

def _localized_process_new_updates(updates):
    # Save callback -> user mapping before TeleBot dispatches handlers.
    for update in updates or []:
        try:
            callback = getattr(update, "callback_query", None)
            if callback:
                _callback_users[callback.id] = callback.from_user.id
        except Exception:
            pass
    return _original_process_new_updates(updates)

bot.send_message = _localized_send_message
bot.edit_message_text = _localized_edit_message_text
bot.answer_callback_query = _localized_answer_callback_query
bot.process_new_updates = _localized_process_new_updates

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required.")

db_lock = threading.RLock()

user_states = {}
pending_downloads = {}
# First-time /start flow: language must be selected before continuing.
pending_start_tokens = {}
# Used only for compatibility with the post-file language flow.
pending_post_file_language = set()

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def date_text(date_obj):
    return date_obj.strftime("%Y-%m-%d %H:%M:%S")

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def execute(query, params=(), fetchone=False, fetchall=False, commit=False):
    # SQLite '?' placeholders are converted to PostgreSQL '%s'.
    query = query.replace("?", "%s")
    with db_lock:
        connection = get_db()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(query, params)
            if fetchone:
                result = cursor.fetchone()
            elif fetchall:
                result = cursor.fetchall()
            else:
                result = None
                if cursor.description:
                    row = cursor.fetchone()
                    result = row["id"] if row and "id" in row else None
            if commit:
                connection.commit()
            else:
                connection.rollback()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

def init_database():
    with db_lock:
        connection = get_db()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE NOT NULL,
                    name TEXT,
                    created_at TEXT NOT NULL,
                    expire_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id BIGSERIAL PRIMARY KEY,
                    admin_id BIGINT NOT NULL,
                    file_id TEXT NOT NULL,
                    file_name TEXT,
                    file_type TEXT NOT NULL,
                    caption TEXT,
                    token TEXT UNIQUE NOT NULL,
                    password_hash TEXT,
                    downloads INTEGER NOT NULL DEFAULT 0,
                    upload_date TEXT NOT NULL,
                    deleted INTEGER NOT NULL DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id BIGSERIAL PRIMARY KEY,
                    admin_id BIGINT NOT NULL,
                    channel_id TEXT NOT NULL,
                    channel_username TEXT,
                    channel_link TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id BIGSERIAL PRIMARY KEY,
                    file_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    admin_id BIGINT PRIMARY KEY,
                    delete_after INTEGER NOT NULL DEFAULT 60
                )
            """)

            # Added features: bilingual UI, owner-managed subscription plans,
            # Telegram Stars payments, and payment history.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id BIGINT PRIMARY KEY,
                    language TEXT NOT NULL DEFAULT 'fa'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscription_plans (
                    id BIGSERIAL PRIMARY KEY,
                    name_fa TEXT NOT NULL,
                    name_en TEXT NOT NULL,
                    days INTEGER NOT NULL,
                    stars INTEGER NOT NULL,
                    recurring BOOLEAN NOT NULL DEFAULT FALSE,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    plan_id BIGINT,
                    payload TEXT UNIQUE NOT NULL,
                    stars INTEGER NOT NULL,
                    charge_id TEXT,
                    paid_at TEXT NOT NULL,
                    expire_at TEXT,
                    status TEXT NOT NULL DEFAULT 'paid'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS free_trials (
                    user_id BIGINT PRIMARY KEY,
                    claimed_at TEXT NOT NULL,
                    expire_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_channels (
                    file_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    PRIMARY KEY (file_id, channel_id)
                )
            """)

            # Password support migration for existing installations.
            cursor.execute("ALTER TABLE files ADD COLUMN IF NOT EXISTS password_hash TEXT")

            # Performance indexes for the most frequent bot queries.
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_token_active ON files(token, deleted)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_admin_active ON files(admin_id, deleted)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_admin ON channels(admin_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_downloads_file ON downloads(file_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_downloads_user ON downloads(user_id)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_charge_id ON payments(charge_id) WHERE charge_id IS NOT NULL")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()


# =========================
# توابع دسترسی و منوها
# =========================

def is_owner(user_id):
    return user_id == OWNER_ID


def get_admin(user_id):
    return execute(
        "SELECT * FROM admins WHERE user_id = ?",
        (user_id,),
        fetchone=True
    )


def is_admin(user_id):
    admin = get_admin(user_id)

    if not admin:
        return False

    if admin["status"] != "active":
        return False

    try:
        expire_at = datetime.strptime(admin["expire_at"], "%Y-%m-%d %H:%M:%S")
        return expire_at > datetime.now()
    except Exception:
        return False


def get_active_admin(user_id):
    if not is_admin(user_id):
        return None
    return get_admin(user_id)


def admin_keyboard(user_id=None):
    user_id = user_id if user_id is not None else OWNER_ID
    if get_language(user_id) == "en":
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row("📤 Upload file", "📂 My files")
        keyboard.row("📊 My stats", "📢 Manage channels")
        keyboard.row("💳 Subscription status", "💎 Buy / Renew subscription")
        keyboard.row("🎁 3-Day Free Trial")
        keyboard.row("🌐 Language")
        keyboard.row("❌ Close panel")
        return keyboard
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("📤 آپلود فایل", "📂 فایل‌های من")
    keyboard.row("📊 آمار من", "📢 مدیریت کانال‌ها")
    keyboard.row("💳 وضعیت اشتراک", "💎 تمدید / خرید اشتراک")
    keyboard.row("🎁 اشتراک رایگان ۳ روزه")
    keyboard.row("🌐 زبان / Language")
    keyboard.row("❌ بستن پنل")
    return keyboard
def owner_keyboard(user_id=None):
    user_id = user_id if user_id is not None else OWNER_ID
    if get_language(user_id) == "en":
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row("👥 Manage admins", "➕ Add admin")
        keyboard.row("➖ Remove admin", "💰 Revenue")
        keyboard.row("📊 Global stats", "📂 All files")
        keyboard.row("💎 Subscription plans", "📢 All channels")
        keyboard.row("⏱ Auto-delete settings")
        keyboard.row("🌐 Language")
        keyboard.row("❌ Close panel")
        return keyboard
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("👥 مدیریت ادمین‌ها", "➕ افزودن ادمین")
    keyboard.row("➖ حذف ادمین", "💰 درآمد")
    keyboard.row("📊 آمار کل", "📂 همه فایل‌ها")
    keyboard.row("💎 مدیریت اشتراک‌ها", "📢 همه کانال‌ها")
    keyboard.row("⏱ تنظیم حذف خودکار")
    keyboard.row("🌐 زبان / Language")
    keyboard.row("❌ بستن پنل")
    return keyboard
def inline_button(text, callback_data):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text, callback_data=callback_data))
    return keyboard


def clear_state(user_id):
    user_states.pop(user_id, None)


def hash_file_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_file_password(password, password_hash):
    if not password_hash:
        return True
    return secrets.compare_digest(hash_file_password(password), password_hash)


def password_text(user_id, key):
    """Return password-related text in the user's selected language."""
    texts = {
        "set_password": ("🔐 Set password", "🔐 تعیین رمز"),
        "no_password": ("➡️ No password", "➡️ بدون رمز"),
        "change_password": ("🔑 Change password", "🔑 تغییر رمز"),
        "remove_password": ("🔓 Remove password", "🔓 حذف رمز"),
        "ask_password": (
            "🔐 Do you want to set a password for this file?",
            "🔐 آیا می‌خواهید برای این فایل رمز عبور تعیین کنید؟"
        ),
        "send_password": (
            "🔑 Send the file password:\n\nMinimum 4 characters.",
            "🔑 رمز عبور فایل را ارسال کنید:\n\nحداقل ۴ کاراکتر."
        ),
        "send_new_password": (
            "🔑 Send the new file password:\n\nMinimum 4 characters.",
            "🔑 رمز عبور جدید فایل را ارسال کنید:\n\nحداقل ۴ کاراکتر."
        ),
        "password_required": (
            "🔒 This file is password protected.\n\n🔑 Send the password:",
            "🔒 این فایل دارای رمز عبور است.\n\n🔑 رمز عبور را ارسال کنید:"
        ),
        "wrong_password": (
            "❌ Incorrect password. Please try again.",
            "❌ رمز عبور اشتباه است. دوباره تلاش کنید."
        ),
        "password_too_short": (
            "❌ Password is too short. Use at least 4 characters.",
            "❌ رمز عبور خیلی کوتاه است. حداقل ۴ کاراکتر وارد کنید."
        ),
        "password_set": (
            "✅ File password set successfully.",
            "✅ رمز فایل با موفقیت تنظیم شد."
        ),
        "password_changed": (
            "✅ File password changed.",
            "✅ رمز فایل تغییر کرد."
        ),
        "password_removed": (
            "✅ File password removed.",
            "✅ رمز فایل حذف شد."
        ),
        "has_password_status": (
            "🔐 This file currently has a password.",
            "🔐 این فایل در حال حاضر رمز دارد."
        ),
        "no_password_status": (
            "🔓 This file currently has no password.",
            "🔓 این فایل در حال حاضر رمز ندارد."
        ),
        "file_not_found": (
            "❌ File is no longer available.",
            "❌ فایل دیگر موجود نیست."
        ),
        "no_access": (
            "⛔ You do not have access.",
            "⛔ دسترسی ندارید."
        ),
        "password_saved_no_password": (
            "🔓 File saved without a password.",
            "🔓 فایل بدون رمز ذخیره شد."
        ),
    }
    pair = texts.get(key, ("", ""))
    return pair[0] if get_language(user_id) == "en" else pair[1]

def password_keyboard(user_id):
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(password_text(user_id, "set_password"), callback_data="set_password_yes"),
        types.InlineKeyboardButton(password_text(user_id, "no_password"), callback_data="set_password_no")
    )
    return kb


def file_password_management_keyboard(user_id, has_password):
    kb = types.InlineKeyboardMarkup()
    if get_language(user_id) == "en":
        if has_password:
            kb.row(
                types.InlineKeyboardButton(password_text(user_id, "change_password"), callback_data="change_password:"),
                types.InlineKeyboardButton(password_text(user_id, "remove_password"), callback_data="remove_password:")
            )
        else:
            kb.add(types.InlineKeyboardButton(password_text(user_id, "set_password"), callback_data="set_file_password:"))
    else:
        if has_password:
            kb.row(
                types.InlineKeyboardButton(password_text(user_id, "change_password"), callback_data="change_password:"),
                types.InlineKeyboardButton(password_text(user_id, "remove_password"), callback_data="remove_password:")
            )
        else:
            kb.add(types.InlineKeyboardButton(password_text(user_id, "set_password"), callback_data="set_file_password:"))
    return kb


def safe_send(chat_id, text, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception:
        return None



# =========================
# قابلیت‌های افزوده: زبان، اشتراک، پرداخت Telegram Stars
# =========================

LANG = {
    "fa": {
        "language": "🌐 زبان انتخاب شد: فارسی",
        "choose_language": "🌐 زبان را انتخاب کنید / Choose your language:",
        "welcome": "سلام! 👋\nاین ربات برای دریافت فایل استفاده می‌شود.",
        "buy": "💎 خرید / تمدید اشتراک",
        "free_trial": "🎁 اشتراک رایگان ۳ روزه",
        "trial_title": "🎁 دوره آزمایشی رایگان ۳ روزه",
        "trial_available": "🎁 شما می‌توانید ۳ روز اشتراک رایگان دریافت کنید.",
        "trial_activated": "✅ دوره آزمایشی رایگان شما فعال شد.\n⏳ مدت: ۳ روز\n📅 پایان: {expire}",
        "trial_already_used": "❌ شما قبلاً از دوره آزمایشی رایگان استفاده کرده‌اید.",
        "trial_active": "ℹ️ شما در حال حاضر یک اشتراک فعال دارید. دوره آزمایشی رایگان برای شما فعال نشد.",
        "trial_error": "❌ فعال‌سازی دوره آزمایشی انجام نشد. لطفاً دوباره تلاش کنید.",
        "no_plans": "فعلاً هیچ پلن فعالی وجود ندارد.",
        "plans": "💎 پلن‌های اشتراک:",
        "payment_sent": "🧾 فاکتور پرداخت در تلگرام برای شما ارسال شد.",
        "payment_ok": "✅ پرداخت با موفقیت انجام شد و اشتراک شما فعال/تمدید شد.",
        "payment_error": "❌ پرداخت ثبت نشد یا اطلاعات پرداخت نامعتبر است.",
        "owner_only": "⛔ فقط مالک به این بخش دسترسی دارد.",
        "admin_only": "⛔ شما دسترسی ادمین ندارید.",
        "owner_plans": "💎 مدیریت پلن‌های اشتراک",
        "add_plan": "➕ افزودن پلن",
        "remove_plan": "🗑 حذف پلن",
        "owner_channels": "📢 همه کانال‌های اجباری",
        "owner_delete": "⏱ تنظیم حذف خودکار برای ادمین",
        "send_admin_id": "🆔 آیدی عددی ادمین را ارسال کنید.",
        "send_seconds": "⏱ زمان حذف خودکار را به ثانیه ارسال کنید.",
        "plan_format": "فرمت: نام فارسی | نام انگلیسی | تعداد روز | تعداد ستاره | recurring\nمثال: 30 روزه | 30 Days | 30 | 250 | yes",
        "plan_added": "✅ پلن با موفقیت اضافه شد.",
        "plan_deleted": "✅ پلن حذف شد.",
        "invalid_plan": "❌ اطلاعات پلن نامعتبر است.",
        "invalid_seconds": "❌ فقط عدد مثبت ارسال کنید.",
        "delete_set": "✅ زمان حذف خودکار ادمین تنظیم شد.",
        "no_channels": "هیچ کانال اجباری ثبت نشده است.",
        "channel_removed": "✅ کانال حذف شد.",
    },
    "en": {
        "language": "🌐 Language selected: English",
        "choose_language": "🌐 زبان را انتخاب کنید / Choose your language:",
        "welcome": "Hello! 👋\nThis bot is used to receive files.",
        "buy": "💎 Buy / Renew subscription",
        "free_trial": "🎁 3-Day Free Trial",
        "trial_title": "🎁 3-Day Free Trial",
        "trial_available": "🎁 You are eligible for a 3-day free trial.",
        "trial_activated": "✅ Your free trial is now active.\n⏳ Duration: 3 days\n📅 Expires: {expire}",
        "trial_already_used": "❌ You have already used your free trial.",
        "trial_active": "ℹ️ You already have an active subscription. The free trial was not activated.",
        "trial_error": "❌ The free trial could not be activated. Please try again.",
        "no_plans": "There are no active plans at the moment.",
        "plans": "💎 Subscription plans:",
        "payment_sent": "🧾 The payment invoice was sent inside Telegram.",
        "payment_ok": "✅ Payment completed and your subscription was activated/extended.",
        "payment_error": "❌ Payment could not be registered or the payment information is invalid.",
        "owner_only": "⛔ Owner access only.",
        "admin_only": "⛔ You do not have admin access.",
        "owner_plans": "💎 Subscription plan management",
        "add_plan": "➕ Add plan",
        "remove_plan": "🗑 Delete plan",
        "owner_channels": "📢 All mandatory channels",
        "owner_delete": "⏱ Set auto-delete for an admin",
        "send_admin_id": "🆔 Send the admin's numeric ID.",
        "send_seconds": "⏱ Send auto-delete time in seconds.",
        "plan_format": "Format: Persian name | English name | days | stars | recurring\nExample: 30 Days | 30 Days | 30 | 250 | yes",
        "plan_added": "✅ Plan added successfully.",
        "plan_deleted": "✅ Plan deleted.",
        "invalid_plan": "❌ Invalid plan information.",
        "invalid_seconds": "❌ Send a positive number only.",
        "delete_set": "✅ Admin auto-delete time updated.",
        "no_channels": "No mandatory channels are registered.",
        "channel_removed": "✅ Channel removed.",
    }
}

def has_language(user_id):
    row = execute("SELECT language FROM user_preferences WHERE user_id = ?", (user_id,), fetchone=True)
    return bool(row and row["language"] in LANG)

def get_language(user_id):
    row = execute("SELECT language FROM user_preferences WHERE user_id = ?", (user_id,), fetchone=True)
    return row["language"] if row and row["language"] in LANG else "fa"

def set_language(user_id, language):
    if language not in LANG:
        return
    execute("""
        INSERT INTO user_preferences(user_id, language) VALUES(?, ?)
        ON CONFLICT(user_id) DO UPDATE SET language=EXCLUDED.language
    """, (user_id, language), commit=True)

def tr(user_id, key, **kwargs):
    return LANG[get_language(user_id)].get(key, key).format(**kwargs)

def localized_status(user_id, status):
    """Translate database status labels for the selected language."""
    status = str(status or "")
    if get_language(user_id) == "en":
        return {"active": "Active", "blocked": "Blocked", "inactive": "Inactive"}.get(status.lower(), status)
    return {"active": "فعال", "blocked": "مسدود", "inactive": "غیرفعال"}.get(status.lower(), status)

def language_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang:fa"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")
    )
    return kb

def plans_keyboard(user_id, owner=False):
    plans = execute(
        "SELECT * FROM subscription_plans WHERE active = TRUE ORDER BY days, stars",
        fetchall=True
    )
    kb = types.InlineKeyboardMarkup()

    # Free trial is a separate flow; it never creates a 0-Star invoice.
    if not owner and not has_used_free_trial(user_id) and not is_admin(user_id):
        kb.add(types.InlineKeyboardButton(
            tr(user_id, "free_trial"),
            callback_data="free_trial"
        ))

    for plan in plans:
        name = plan["name_fa"] if get_language(user_id) == "fa" else plan["name_en"]
        recurring = " 🔄" if plan["recurring"] else ""
        kb.add(types.InlineKeyboardButton(
            f"{name} — {plan['days']}d / ⭐{plan['stars']}{recurring}",
            callback_data=f"buy_plan:{plan['id']}"
        ))
    if owner:
        kb.row(
            types.InlineKeyboardButton("➕ افزودن پلن", callback_data="owner_add_plan"),
            types.InlineKeyboardButton("🗑 حذف پلن", callback_data="owner_delete_plan")
        )
    return kb


def has_used_free_trial(user_id):
    row = execute(
        "SELECT user_id FROM free_trials WHERE user_id=?",
        (user_id,), fetchone=True
    )
    return bool(row)


def activate_free_trial(user_id):
    """Activate a one-time 3-day trial without going through Telegram Payments."""
    if has_used_free_trial(user_id):
        return False, "already_used", None

    # Do not let an already-active paid/admin subscription be converted into
    # an additional free period. The trial is intended for first-time users.
    current = get_admin(user_id)
    if current and is_admin(user_id):
        return False, "active", None

    now = datetime.now()
    expire = now + timedelta(days=3)

    try:
        # The PRIMARY KEY on user_id makes the one-time claim atomic at the
        # database level even if the user taps the button more than once.
        execute(
            "INSERT INTO free_trials(user_id, claimed_at, expire_at) VALUES(?,?,?)",
            (user_id, now_text(), date_text(expire)), commit=True
        )
    except Exception as error:
        # A duplicate-key race means another request already claimed it.
        print("Free trial claim error:", error)
        if has_used_free_trial(user_id):
            return False, "already_used", None
        return False, "error", None

    if current:
        execute(
            "UPDATE admins SET status='active', expire_at=? WHERE user_id=?",
            (date_text(expire), user_id), commit=True
        )
    else:
        execute(
            "INSERT INTO admins(user_id,name,created_at,expire_at,status) VALUES(?,?,?,?, 'active')",
            (user_id, str(user_id), now_text(), date_text(expire)), commit=True
        )
        execute(
            "INSERT INTO settings(admin_id, delete_after) VALUES(?,?) ON CONFLICT(admin_id) DO NOTHING",
            (user_id, DEFAULT_DELETE_AFTER), commit=True
        )

    return True, "activated", expire

def ensure_default_plan():
    count = execute("SELECT COUNT(*) AS total FROM subscription_plans", fetchone=True)
    if not count or count["total"] == 0:
        execute("""
            INSERT INTO subscription_plans
            (name_fa, name_en, days, stars, recurring, active, created_at)
            VALUES (?, ?, ?, ?, ?, TRUE, ?)
        """, ("اشتراک ماهیانه", "Monthly Subscription", 30, 250, True, now_text()), commit=True)

def send_subscription_plans(chat_id, user_id):
    ensure_default_plan()
    plans = execute("SELECT * FROM subscription_plans WHERE active=TRUE ORDER BY days, stars", fetchall=True)

    # The normal user subscription screen contains:
    # - the monthly paid plan (30 days by default)
    # - the one-time 3-day free trial, while the user is eligible.
    if not plans and has_used_free_trial(user_id):
        bot.send_message(chat_id, tr(user_id, "no_plans"))
        return

    text = tr(user_id, "plans")
    if not has_used_free_trial(user_id) and not is_admin(user_id) and not is_owner(user_id):
        text += "\n\n" + tr(user_id, "trial_available")

    bot.send_message(chat_id, text, reply_markup=plans_keyboard(user_id))

def activate_paid_subscription(user_id, plan, payment):
    current = get_admin(user_id)
    now = datetime.now()
    try:
        current_expire = datetime.strptime(current["expire_at"], "%Y-%m-%d %H:%M:%S") if current else now
    except Exception:
        current_expire = now
    base = current_expire if current and current_expire > now else now
    # Telegram recurring invoices are always 30 days. One-time plans can use any
    # positive day count.
    expire = base + timedelta(days=int(plan["days"]))
    if current:
        execute("""
            UPDATE admins SET status='active', expire_at=? WHERE user_id=?
        """, (date_text(expire), user_id), commit=True)
    else:
        execute("""
            INSERT INTO admins(user_id,name,created_at,expire_at,status)
            VALUES(?,?,?,?, 'active')
        """, (user_id, str(user_id), now_text(), date_text(expire)), commit=True)
        execute("""
            INSERT INTO settings(admin_id, delete_after)
            VALUES(?, ?) ON CONFLICT(admin_id) DO NOTHING
        """, (user_id, DEFAULT_DELETE_AFTER), commit=True)
    execute("""
        INSERT INTO payments(user_id, plan_id, payload, stars, charge_id, paid_at, expire_at)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(payload) DO NOTHING
    """, (
        user_id, plan["id"], payment.invoice_payload, payment.total_amount,
        payment.telegram_payment_charge_id, now_text(), date_text(expire)
    ), commit=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang:"))
def language_callback(call):
    user_id = call.from_user.id
    lang = call.data.split(":", 1)[1]
    if lang not in LANG:
        return

    set_language(user_id, lang)
    bot.answer_callback_query(call.id, LANG[lang]["language"])

    try:
        bot.edit_message_text(
            LANG[lang]["language"],
            call.message.chat.id,
            call.message.message_id
        )
    except Exception:
        pass

    # If the user arrived through a file link, language selection is step 1.
    # Continue with step 2 only after the language has been selected.
    pending_token = pending_start_tokens.pop(user_id, None)
    if pending_token:
        request_file(call.message, pending_token)
        return

    # If a previous flow was waiting for language after file delivery,
    # continue with the subscription screen as the next step.
    if user_id in pending_post_file_language:
        pending_post_file_language.discard(user_id)
        send_subscription_plans(call.message.chat.id, user_id)
        return

    # Language is now selected; show the normal home flow in that language.
    if is_owner(user_id):
        bot.send_message(
            call.message.chat.id,
            "👑 به پنل مالک خوش آمدید.\nبرای ورود به پنل از /owner استفاده کنید.",
            reply_markup=owner_keyboard(user_id)
        )
    elif is_admin(user_id):
        bot.send_message(
            call.message.chat.id,
            "🛠 شما ادمین هستید.\nبرای ورود به پنل از /panel استفاده کنید.",
            reply_markup=admin_keyboard(user_id)
        )
    else:
        bot.send_message(
            call.message.chat.id,
            tr(user_id, "welcome") + "\n\n" +
            ("لطفاً لینک فایل را از فرستنده دریافت کنید." if lang == "fa"
             else "Please obtain the file link from the sender.")
        )
        send_subscription_plans(call.message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "free_trial")
def free_trial_callback(call):
    user_id = call.from_user.id
    success, status, expire = activate_free_trial(user_id)

    if status == "already_used":
        bot.answer_callback_query(call.id, tr(user_id, "trial_already_used"), show_alert=True)
        return
    if status == "active":
        bot.answer_callback_query(call.id, tr(user_id, "trial_active"), show_alert=True)
        return
    if not success:
        bot.answer_callback_query(call.id, tr(user_id, "trial_error"), show_alert=True)
        return

    bot.answer_callback_query(call.id)
    expire_text = expire.strftime("%Y-%m-%d %H:%M:%S")
    bot.send_message(
        call.message.chat.id,
        tr(user_id, "trial_activated", expire=expire_text),
        reply_markup=admin_keyboard(user_id)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_plan:"))
def buy_plan_callback(call):
    user_id = call.from_user.id
    try:
        plan_id = int(call.data.split(":", 1)[1])
    except ValueError:
        bot.answer_callback_query(call.id, tr(user_id, "invalid_plan"), show_alert=True)
        return
    plan = execute(
        "SELECT * FROM subscription_plans WHERE id=? AND active=TRUE",
        (plan_id,), fetchone=True
    )
    if not plan:
        bot.answer_callback_query(call.id, tr(user_id, "no_plans"), show_alert=True)
        return
    if int(plan["stars"]) < 1 or int(plan["stars"]) > 10000:
        bot.answer_callback_query(call.id, tr(user_id, "payment_error"), show_alert=True)
        print(f"Invalid Stars price for plan {plan_id}: {plan['stars']}")
        return
    if plan["recurring"] and plan["days"] != 30:
        bot.answer_callback_query(call.id, ("پرداخت دوره‌ای Telegram Stars باید ۳۰ روزه باشد." if get_language(user_id) == "fa" else "Telegram Stars recurring subscriptions must be 30 days."), show_alert=True)
        return
    payload = f"sub:{plan['id']}:{user_id}:{secrets.token_urlsafe(8)}"
    try:
        # IMPORTANT: Start with a simple one-time Telegram Stars invoice.
        # This avoids recurring-subscription parameters while we verify the
        # basic Stars payment flow. The plan still grants its configured days.
        # Telegram requires XTR for digital goods/services.
        # provider_token is intentionally omitted for XTR invoices.
        bot.send_invoice(
            user_id,
            title=(plan["name_fa"] if get_language(user_id) == "fa" else plan["name_en"])[:32],
            description=(f"اشتراک - {plan['days']} روز / {plan['stars']} Telegram Stars" if get_language(user_id) == "fa" else f"Subscription - {plan['days']} days / {plan['stars']} Telegram Stars")[:255],
            invoice_payload=payload,
            provider_token="",
            currency="XTR",
            prices=[types.LabeledPrice(
                label="Telegram Stars",
                amount=int(plan["stars"])
            )]
        )
        bot.answer_callback_query(call.id)
        print(
            f"Stars invoice sent successfully: user={user_id}, plan={plan['id']}, "
            f"stars={int(plan['stars'])}, days={int(plan['days'])}"
        )
    except Exception as error:
        # Render must show the actual Telegram/API/library error instead of
        # only the generic popup shown to the user.
        print(
            "TELEGRAM STARS INVOICE ERROR | "
            f"type={type(error).__name__} | "
            f"error_code={getattr(error, 'error_code', None)} | "
            f"description={getattr(error, 'description', None)} | "
            f"message={error!r}"
        )
        traceback.print_exc()
        bot.answer_callback_query(call.id, tr(user_id, "payment_error"), show_alert=True)

@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_handler(pre_checkout_query):
    try:
        payload = pre_checkout_query.invoice_payload or ""
        parts = payload.split(":")
        if len(parts) < 3 or parts[0] != "sub":
            bot.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message=("پرداخت اشتراک نامعتبر است." if get_language(pre_checkout_query.from_user.id) == "fa" else "Invalid subscription payment.")
            )
            return

        plan_id = int(parts[1])
        user_id = int(parts[2])
        plan = execute(
            "SELECT * FROM subscription_plans WHERE id=? AND active=TRUE",
            (plan_id,), fetchone=True
        )

        if not plan:
            bot.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message=("این اشتراک دیگر در دسترس نیست." if get_language(pre_checkout_query.from_user.id) == "fa" else "Subscription is no longer available.")
            )
            return

        if user_id != pre_checkout_query.from_user.id:
            bot.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message=("این فاکتور متعلق به کاربر دیگری است." if get_language(pre_checkout_query.from_user.id) == "fa" else "This invoice belongs to another user.")
            )
            return

        if pre_checkout_query.currency != "XTR":
            bot.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message=("واحد پرداخت Telegram Stars نامعتبر است." if get_language(pre_checkout_query.from_user.id) == "fa" else "Invalid Telegram Stars currency.")
            )
            return

        expected_stars = int(plan["stars"])
        actual_stars = int(pre_checkout_query.total_amount)
        if expected_stars < 1 or expected_stars != actual_stars:
            print(
                f"Stars price mismatch: plan={plan_id}, expected={expected_stars}, actual={actual_stars}, "
                f"user={user_id}"
            )
            bot.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message=("مبلغ پرداخت با قیمت پلن مطابقت ندارد." if get_language(pre_checkout_query.from_user.id) == "fa" else "Price mismatch.")
            )
            return

        # This must be answered quickly; no slow work is done after validation.
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as error:
        print("خطای pre_checkout:", error)
        try:
            bot.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message=("اعتبارسنجی پرداخت ناموفق بود." if get_language(pre_checkout_query.from_user.id) == "fa" else "Payment validation failed.")
            )
        except Exception:
            pass

@bot.message_handler(content_types=["successful_payment"])
def successful_payment_handler(message):
    payment = message.successful_payment
    user_id = message.from_user.id
    try:
        payload = payment.invoice_payload or ""
        parts = payload.split(":")
        if len(parts) < 3 or parts[0] != "sub":
            bot.send_message(user_id, tr(user_id, "payment_error"))
            return

        if payment.currency != "XTR":
            print(f"Unexpected payment currency: {payment.currency}")
            bot.send_message(user_id, tr(user_id, "payment_error"))
            return

        # Verify that the invoice belongs to the same Telegram user who paid.
        # The payload format is: sub:<plan_id>:<user_id>:<random_token>
        try:
            payload_user_id = int(parts[2])
        except (TypeError, ValueError):
            bot.send_message(user_id, tr(user_id, "payment_error"))
            return

        if payload_user_id != user_id:
            print(
                f"Payment user mismatch: payload_user={payload_user_id}, "
                f"payer={user_id}"
            )
            bot.send_message(user_id, tr(user_id, "payment_error"))
            return

        # Telegram can retry delivery of an update. Never grant the same
        # successful charge twice.
        existing = execute(
            "SELECT id FROM payments WHERE charge_id=?",
            (payment.telegram_payment_charge_id,), fetchone=True
        )
        if existing:
            bot.send_message(user_id, tr(user_id, "payment_ok"), reply_markup=admin_keyboard(user_id))
            return

        plan = execute(
            "SELECT * FROM subscription_plans WHERE id=? AND active=TRUE",
            (int(parts[1]),), fetchone=True
        )
        if not plan or int(plan["stars"]) != int(payment.total_amount):
            print(
                f"Successful payment validation failed: plan={parts[1]}, "
                f"amount={payment.total_amount}, user={user_id}"
            )
            bot.send_message(user_id, tr(user_id, "payment_error"))
            return

        activate_paid_subscription(user_id, plan, payment)
        bot.send_message(
            user_id, tr(user_id, "payment_ok"), reply_markup=admin_keyboard(user_id)
        )
    except Exception as error:
        print("خطای ثبت پرداخت:", error)
        bot.send_message(user_id, tr(user_id, "payment_error"))

@bot.callback_query_handler(func=lambda call: call.data == "owner_add_plan")
def owner_add_plan_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, tr(call.from_user.id, "owner_only"), show_alert=True)
        return
    user_states[call.from_user.id] = {"action": "owner_add_plan"}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, tr(call.from_user.id, "plan_format"))

@bot.callback_query_handler(func=lambda call: call.data == "owner_delete_plan")
def owner_delete_plan_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, tr(call.from_user.id, "owner_only"), show_alert=True)
        return
    plans = execute("SELECT * FROM subscription_plans WHERE active=TRUE ORDER BY id", fetchall=True)
    kb = types.InlineKeyboardMarkup()
    for plan in plans:
        kb.add(types.InlineKeyboardButton(
            f"{plan['name_fa']} / {plan['name_en']} — ⭐{plan['stars']}",
            callback_data=f"del_plan:{plan['id']}"
        ))
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, tr(call.from_user.id, "owner_plans"), reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_plan:"))
def delete_plan_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, tr(call.from_user.id, "owner_only"), show_alert=True)
        return
    plan_id = int(call.data.split(":")[1])
    execute("UPDATE subscription_plans SET active=FALSE WHERE id=?", (plan_id,), commit=True)
    bot.answer_callback_query(call.id, tr(call.from_user.id, "plan_deleted"))

@bot.callback_query_handler(func=lambda call: call.data == "owner_channels")
def owner_channels_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, tr(call.from_user.id, "owner_only"), show_alert=True)
        return
    channels = execute("""
        SELECT c.*, a.name AS admin_name
        FROM channels c LEFT JOIN admins a ON a.user_id=c.admin_id
        ORDER BY c.id DESC
    """, fetchall=True)
    kb = types.InlineKeyboardMarkup()
    text = tr(call.from_user.id, "owner_channels") + "\n\n"
    if not channels:
        text += tr(call.from_user.id, "no_channels")
    else:
        for c in channels:
            text += f"👤 {c['admin_name'] or c['admin_id']} | {c['channel_username'] or c['channel_id']}\n"
            kb.add(types.InlineKeyboardButton(
                f"🗑 {c['channel_username'] or c['channel_id']}",
                callback_data=f"owner_del_channel:{c['id']}"
            ))
    kb.add(types.InlineKeyboardButton("➕ افزودن کانال", callback_data="owner_add_channel"))
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("owner_del_channel:"))
def owner_del_channel_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, tr(call.from_user.id, "owner_only"), show_alert=True)
        return
    channel_id = int(call.data.split(":")[1])
    execute("DELETE FROM channels WHERE id=?", (channel_id,), commit=True)
    bot.answer_callback_query(call.id, tr(call.from_user.id, "channel_removed"))
    owner_channels_callback(call)

@bot.callback_query_handler(func=lambda call: call.data == "owner_add_channel")
def owner_add_channel_callback(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, tr(call.from_user.id, "owner_only"), show_alert=True)
        return
    user_states[call.from_user.id] = {"action": "owner_add_channel"}
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "📢 افزودن کانال اجباری برای همه فایل‌ها:\n\n"
        "@channel_username | https://t.me/channel_username\n\n"
        "یا اگر می‌خواهید فقط برای یک ادمین باشد:\n"
        "admin_id | @channel_username | https://t.me/channel_username"
    )

# =========================
# دستورهای عمومی
# =========================

@bot.message_handler(commands=["paysupport"])
def paysupport_handler(message):
    user_id = message.from_user.id
    if get_language(user_id) == "en":
        text = (
            "💳 Payment Support\n\n"
            "If you were charged but your subscription was not activated, "
            "please send the payment receipt or Telegram payment charge ID to the bot owner.\n\n"
            "Telegram Stars payments are processed inside Telegram."
        )
    else:
        text = (
            "💳 پشتیبانی پرداخت\n\n"
            "اگر از حساب شما Stars کسر شده ولی اشتراک فعال نشده است، "
            "رسید پرداخت یا شناسه پرداخت Telegram را برای مالک ربات ارسال کنید.\n\n"
            "پرداخت‌های Stars مستقیماً داخل تلگرام انجام می‌شوند."
        )
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["start"])
def start_handler(message):
    """Main entry point with the required priority:

    1) Language selection
    2) If this is a file deep-link: mandatory channels -> file delivery
    3) Subscription plans (monthly + 3-day free trial)

    For a normal /start without a file link, regular users go from language
    directly to the subscription screen.
    """
    user_id = message.from_user.id
    raw_text = (message.text or "").strip()

    # Telegram normally sends: /start file_TOKEN.
    # Also tolerate /start@BotName file_TOKEN and an accidentally pasted deep URL.
    token = None
    parts = raw_text.split(maxsplit=1)
    if len(parts) > 1:
        candidate = parts[1].strip()
        if candidate.startswith("file_"):
            token = candidate[5:].strip()
        elif "start=file_" in candidate:
            token = candidate.split("start=file_", 1)[1].split("&", 1)[0].strip()

    print(f"START ROUTE | user_id={user_id} | raw={raw_text!r} | token={token!r}")

    # LANGUAGE ALWAYS COMES BEFORE THE FILE FLOW.
    # If a file deep-link was used before the user selected a language,
    # remember the token and continue with the exact same file after selection.
    if not has_language(user_id):
        if token:
            pending_start_tokens[user_id] = token
        else:
            pending_start_tokens.pop(user_id, None)

        bot.send_message(
            message.chat.id,
            "🌐 زبان را انتخاب کنید / Please choose your language:",
            reply_markup=language_keyboard()
        )
        return

    # Language is already known. A file deep-link now starts:
    # mandatory channels -> membership check -> file -> subscription.
    if token:
        request_file(message, token)
        return

    # Normal /start without a file link.
    if is_owner(user_id):
        bot.send_message(
            message.chat.id,
            "👑 به پنل مالک خوش آمدید.\nبرای ورود به پنل از /owner استفاده کنید.",
            reply_markup=owner_keyboard(user_id)
        )
    elif is_admin(user_id):
        bot.send_message(
            message.chat.id,
            "🛠 شما ادمین هستید.\nبرای ورود به پنل از /panel استفاده کنید.",
            reply_markup=admin_keyboard(user_id)
        )
    else:
        # No file requested -> go directly to subscription.
        # send_subscription_plans shows both the monthly paid plan and,
        # when eligible, the one-time 3-day free trial.
        send_subscription_plans(message.chat.id, user_id)

@bot.message_handler(commands=["panel"])
def panel_handler(message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        bot.send_message(
            message.chat.id,
            "⛔ شما دسترسی ادمین ندارید."
        )
        return

    clear_state(user_id)
    bot.send_message(
        message.chat.id,
        "🛠 پنل مدیریت ادمین:",
        reply_markup=admin_keyboard(user_id)
    )


@bot.message_handler(commands=["owner"])
def owner_handler(message):
    user_id = message.from_user.id

    if not is_owner(user_id):
        bot.send_message(message.chat.id, "⛔ فقط مالک به این بخش دسترسی دارد.")
        return

    clear_state(user_id)
    bot.send_message(
        message.chat.id,
        "👑 پنل مالک:",
        reply_markup=owner_keyboard(user_id)
    )


# =========================
# دریافت فایل از لینک
# =========================

def get_required_channels_for_file(file_row):
    """Return admin-specific + owner-global mandatory channels, without duplicates."""
    admin_id = int(file_row["admin_id"])
    rows = execute(
        "SELECT * FROM channels WHERE admin_id IN (?, ?) ORDER BY id",
        (admin_id, OWNER_ID),
        fetchall=True
    ) or []

    result = []
    seen = set()
    for row in rows:
        key = str(row.get("channel_id"))
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def user_is_member_of_channel(user_id, channel_id):
    """Check whether the user is currently a member of the required channel."""
    member = bot.get_chat_member(channel_id, user_id)
    status = getattr(member, "status", None)

    # Normal members, admins and the creator are members.
    if status in ("member", "administrator", "creator"):
        return True

    # Telegram may return a restricted member. If Telegram explicitly says
    # is_member=True, the user is still a member and must be allowed to get
    # the file.
    if status == "restricted":
        return bool(getattr(member, "is_member", False))

    # left / kicked / unknown statuses are not members.
    return False


def build_required_channel_keyboard(channels, token):
    kb = types.InlineKeyboardMarkup()
    for channel in channels:
        link = channel.get("channel_link")
        username = channel.get("channel_username")
        if not link and username:
            link = "https://t.me/" + str(username).lstrip("@")

        label = str(username) if username else "کانال اجباری"
        if not label.startswith("@") and username:
            label = "@" + label
        button_text = f"📢 عضویت در {label}" if username else "📢 عضویت در کانال"

        if link:
            kb.add(types.InlineKeyboardButton(button_text, url=link))

    # Put the token in callback_data so concurrent file requests cannot collide.
    kb.add(types.InlineKeyboardButton("✅ عضو شدم", callback_data=f"check_join:{token}"))
    return kb


def request_file(message, token):
    """Absolute-priority file delivery flow."""
    user_id = message.from_user.id
    token = (token or "").strip()
    print(f"FILE FLOW START | user_id={user_id} | token={token!r}")

    file_row = execute(
        "SELECT * FROM files WHERE token = ? AND deleted = 0",
        (token,),
        fetchone=True
    )
    if not file_row:
        print(f"FILE FLOW INVALID TOKEN | user_id={user_id} | token={token!r}")
        bot.send_message(message.chat.id, "❌ لینک فایل نامعتبر یا منقضی شده است.")
        return

    # Validate only the FILE OWNER's permission. Never inspect recipient subscription.
    owner_id = int(file_row["admin_id"])
    if owner_id != OWNER_ID and not is_admin(owner_id):
        bot.send_message(message.chat.id, "❌ اشتراک صاحب این فایل منقضی شده یا فایل غیرفعال است.")
        return

    channels = get_required_channels_for_file(file_row)
    not_joined = []
    for channel in channels:
        try:
            if not user_is_member_of_channel(user_id, channel["channel_id"]):
                not_joined.append(channel)
        except Exception as error:
            print(
                "MANDATORY CHANNEL CHECK ERROR | "
                f"user_id={user_id} | channel_id={channel['channel_id']} | error={error!r}"
            )
            # Verification failure is fail-closed: do not leak the file.
            not_joined.append(channel)

    print(
        f"FILE FLOW CHECK | user_id={user_id} | token={token!r} | "
        f"file_id={file_row['id']} | channels={len(channels)} | not_joined={len(not_joined)}"
    )

    if not_joined:
        keyboard = build_required_channel_keyboard(not_joined, token)
        bot.send_message(
            message.chat.id,
            "🔒 عضویت اجباری\n\n"
            "برای دریافت فایل ابتدا باید در کانال‌های زیر عضو شوید.\n"
            "روی دکمه‌های عضویت بزنید، سپس «✅ عضو شدم» را انتخاب کنید تا عضویت شما بررسی شود.",
            reply_markup=keyboard
        )
        return

    # Already a member: password-protected files require the password first.
    if file_row.get("password_hash"):
        user_states[user_id] = {
            "action": "verify_file_password",
            "file_token": token
        }
        bot.send_message(
            message.chat.id,
            password_text(user_id, "password_required")
        )
        return

    send_file_to_user(message.chat.id, message.from_user, file_row)


def after_file_delivery(chat_id, user_id):
    """Continue existing language/subscription features only AFTER file delivery."""
    try:
        if not has_language(user_id):
            pending_post_file_language.add(user_id)
            bot.send_message(
                chat_id,
                "🌐 زبان را انتخاب کنید / Please choose your language:",
                reply_markup=language_keyboard()
            )
            return
        send_subscription_plans(chat_id, user_id)
    except Exception as error:
        print("POST FILE FLOW ERROR |", repr(error))


def send_file_to_user(chat_id, user, file_row):
    """Send the Telegram file FIRST; analytics/auto-delete cannot block delivery."""
    sent_message = None
    try:
        caption = file_row["caption"] or ""
        file_type = file_row["file_type"]
        file_id = file_row["file_id"]
        print(f"FILE SEND START | chat_id={chat_id} | db_file_id={file_row['id']} | type={file_type}")

        if file_type == "document":
            sent_message = bot.send_document(chat_id, file_id, caption=caption)
        elif file_type == "photo":
            sent_message = bot.send_photo(chat_id, file_id, caption=caption)
        elif file_type == "video":
            sent_message = bot.send_video(chat_id, file_id, caption=caption)
        elif file_type == "audio":
            sent_message = bot.send_audio(chat_id, file_id, caption=caption)
        elif file_type == "voice":
            sent_message = bot.send_voice(chat_id, file_id, caption=caption)
        else:
            sent_message = bot.send_document(chat_id, file_id, caption=caption)

        print(f"FILE SEND SUCCESS | chat_id={chat_id} | message_id={getattr(sent_message, 'message_id', None)}")

    except Exception as error:
        print(
            "FILE SEND ERROR | "
            f"chat_id={chat_id} | db_file_id={file_row.get('id')} | "
            f"type={file_row.get('file_type')} | telegram_file_id={file_row.get('file_id')!r} | "
            f"error={error!r}"
        )
        traceback.print_exc()
        bot.send_message(chat_id, "❌ ارسال فایل با خطا مواجه شد.")
        return False

    # Everything below is deliberately isolated from the actual file send.
    try:
        execute("UPDATE files SET downloads = downloads + 1 WHERE id = ?", (file_row["id"],), commit=True)
    except Exception as error:
        print("DOWNLOAD COUNTER ERROR |", repr(error))

    try:
        execute(
            "INSERT INTO downloads (file_id, user_id, username, timestamp) VALUES (?, ?, ?, ?)",
            (file_row["id"], user.id, user.username or "", now_text()),
            commit=True
        )
    except Exception as error:
        print("DOWNLOAD LOG ERROR |", repr(error))

    delete_after = DEFAULT_DELETE_AFTER
    try:
        settings = execute(
            "SELECT delete_after FROM settings WHERE admin_id = ?",
            (file_row["admin_id"],),
            fetchone=True
        )
        if settings and settings.get("delete_after") is not None:
            delete_after = int(settings["delete_after"])
    except Exception as error:
        print("AUTO DELETE SETTING ERROR |", repr(error))

    notice = None
    try:
        notice = bot.send_message(
            chat_id,
            f"✅ فایل ارسال شد\n⏱ این فایل تا {delete_after} ثانیه دیگر حذف خواهد شد"
        )
    except Exception as error:
        print("DELIVERY NOTICE ERROR |", repr(error))

    if sent_message:
        try:
            notice_id = notice.message_id if notice else 0
            threading.Thread(
                target=delete_messages_later,
                args=(chat_id, sent_message.message_id, notice_id, delete_after),
                daemon=True
            ).start()
        except Exception as error:
            print("AUTO DELETE THREAD ERROR |", repr(error))

    after_file_delivery(chat_id, user.id)
    return True


def delete_messages_later(chat_id, file_message_id, notice_message_id, seconds):
    try:
        time.sleep(seconds)

        try:
            bot.delete_message(chat_id, file_message_id)
        except Exception:
            pass

        try:
            bot.delete_message(chat_id, notice_message_id)
        except Exception:
            pass

        bot.send_message(chat_id, "🗑 فایل حذف شد")

    except Exception:
        pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("check_join:"))
def check_join_callback(call):
    user_id = call.from_user.id
    token = call.data.split(":", 1)[1].strip()
    print(f"CHECK JOIN | user_id={user_id} | token={token!r}")

    file_row = execute(
        "SELECT * FROM files WHERE token = ? AND deleted = 0",
        (token,),
        fetchone=True
    )
    if not file_row:
        bot.answer_callback_query(call.id, "فایل دیگر موجود نیست.", show_alert=True)
        return

    channels = get_required_channels_for_file(file_row)
    for channel in channels:
        try:
            if not user_is_member_of_channel(user_id, channel["channel_id"]):
                bot.answer_callback_query(
                    call.id,
                    "❌ هنوز عضو کانال‌های اجباری نشده‌اید.\nابتدا عضو شوید و دوباره «عضو شدم» را بزنید.",
                    show_alert=True
                )
                return
        except Exception as error:
            print(
                "CHECK JOIN ERROR | "
                f"user_id={user_id} | channel_id={channel['channel_id']} | error={error!r}"
            )
            bot.answer_callback_query(
                call.id,
                "❌ عضویت شما قابل بررسی نیست. لطفاً چند لحظه بعد دوباره تلاش کنید.",
                show_alert=True
            )
            return

    bot.answer_callback_query(call.id, "✅ عضویت تأیید شد.")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    # Re-check owner validity only; recipient subscription is never checked.
    owner_id = int(file_row["admin_id"])
    if owner_id != OWNER_ID and not is_admin(owner_id):
        bot.send_message(call.message.chat.id, "❌ اشتراک صاحب این فایل منقضی شده یا فایل غیرفعال است.")
        return

    if file_row.get("password_hash"):
        user_states[user_id] = {
            "action": "verify_file_password",
            "file_token": token
        }
        bot.send_message(
            call.message.chat.id,
            password_text(user_id, "password_required")
        )
        return

    send_file_to_user(call.message.chat.id, call.from_user, file_row)


# =========================
# دریافت فایل توسط ادمین
# =========================

@bot.message_handler(content_types=[
    "document",
    "photo",
    "video",
    "audio",
    "voice"
])
def upload_handler(message):
    user_id = message.from_user.id

    if user_states.get(user_id, {}).get("action") != "upload":
        return

    if not is_admin(user_id):
        clear_state(user_id)
        bot.send_message(message.chat.id, "⛔ اشتراک شما فعال نیست.")
        return

    file_id = None
    file_name = ""
    file_type = "document"

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "document"
        file_type = "document"

    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = "photo.jpg"
        file_type = "photo"

    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video.mp4"
        file_type = "video"

    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "audio.mp3"
        file_type = "audio"

    elif message.voice:
        file_id = message.voice.file_id
        file_name = "voice.ogg"
        file_type = "voice"

    if not file_id:
        bot.send_message(message.chat.id, "❌ نوع فایل پشتیبانی نمی‌شود.")
        return

    caption = message.caption or ""

    token = secrets.token_urlsafe(8)

    while execute(
        "SELECT id FROM files WHERE token = ?",
        (token,),
        fetchone=True
    ):
        token = secrets.token_urlsafe(8)

    file_db_id = execute(
        """
        INSERT INTO files
        (admin_id, file_id, file_name, file_type, caption, token, password_hash, upload_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (
            user_id,
            file_id,
            file_name,
            file_type,
            caption,
            token,
            None,
            now_text()
        ),
        commit=True
    )

    username = bot.get_me().username
    link = f"https://t.me/{username}?start=file_{token}"

    user_states[user_id] = {
        "action": "choose_file_password",
        "file_id": file_db_id,
        "file_name": file_name,
        "link": link
    }

    bot.send_message(
        message.chat.id,
        f"✅ فایل ذخیره شد.\n\n"
        f"📄 نام: <code>{html.escape(file_name)}</code>\n"
        f"🔗 لینک اختصاصی:\n{link}\n\n"
        f"🆔 شناسه فایل: {file_db_id}\n\n" +
        password_text(user_id, "ask_password"),
        reply_markup=password_keyboard(user_id)
    )


# =========================
# پنل ادمین
# =========================

@bot.message_handler(func=lambda message: True)
def text_handler(message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text in ("❌ بستن پنل", "❌ Close panel"):
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "پنل بسته شد.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    if text in ("📤 آپلود فایل", "📤 Upload file"):
        if not is_admin(user_id):
            bot.send_message(message.chat.id, "⛔ اشتراک شما فعال نیست.")
            return

        user_states[user_id] = {"action": "upload"}
        bot.send_message(
            message.chat.id,
            "📤 فایل را ارسال کنید.\n"
            "فرمت‌های PDF، ZIP، MP4، MP3، عکس، وویس و سایر فایل‌ها پشتیبانی می‌شوند."
        )
        return

    if text in ("📂 فایل‌های من", "📂 My files"):
        show_admin_files(message)
        return

    if text in ("📊 آمار من", "📊 My stats"):
        show_admin_stats(message)
        return

    if text in ("📢 مدیریت کانال‌ها", "📢 Manage channels"):
        channel_management(message)
        return

    if text in ("⏱ تنظیم حذف خودکار", "⏱ Auto-delete settings"):
        if not is_owner(user_id):
            bot.send_message(message.chat.id, tr(user_id, "owner_only"))
            return

        user_states[user_id] = {"action": "owner_delete_after_admin"}
        bot.send_message(message.chat.id, tr(user_id, "send_admin_id"))
        return

    if text in ("💳 وضعیت اشتراک", "💳 Subscription status"):
        show_subscription(message)
        return

    if text in ("👥 مدیریت ادمین‌ها", "👥 Manage admins"):
        show_admins(message)
        return

    if text in ("➕ افزودن ادمین", "➕ Add admin"):
        if is_owner(user_id):
            user_states[user_id] = {"action": "add_admin"}
            bot.send_message(message.chat.id, "آیدی عددی کاربر را ارسال کنید.")
        return

    if text in ("➖ حذف ادمین", "➖ Remove admin"):
        if is_owner(user_id):
            user_states[user_id] = {"action": "remove_admin"}
            bot.send_message(message.chat.id, "آیدی عددی ادمین را ارسال کنید.")
        return

    if text in ("💰 درآمد", "💰 Revenue"):
        if is_owner(user_id):
            bot.send_message(
                message.chat.id,
                "💰 درآمد کل:\n"
                "برای ثبت درآمد واقعی، درگاه پرداخت باید به ربات متصل شود.\n"
                "در حال حاضر درآمد ثبت‌شده: 0"
            )
        return

    if text in ("📊 آمار کل", "📊 Global stats"):
        if is_owner(user_id):
            show_global_stats(message)
        return

    if text in ("📂 همه فایل‌ها", "📂 All files"):
        if is_owner(user_id):
            show_all_files(message)
        return

    if text in ("💎 تمدید / خرید اشتراک", "💎 Buy / Renew subscription"):
        send_subscription_plans(message.chat.id, user_id)
        return

    if text in ("🎁 اشتراک رایگان ۳ روزه", "🎁 3-Day Free Trial"):
        success, status, expire = activate_free_trial(user_id)
        if status == "already_used":
            bot.send_message(message.chat.id, tr(user_id, "trial_already_used"))
        elif status == "active":
            bot.send_message(message.chat.id, tr(user_id, "trial_active"))
        elif not success:
            bot.send_message(message.chat.id, tr(user_id, "trial_error"))
        else:
            bot.send_message(
                message.chat.id,
                tr(user_id, "trial_activated", expire=expire.strftime("%Y-%m-%d %H:%M:%S")),
                reply_markup=admin_keyboard(user_id)
            )
        return

    if text in ("🌐 زبان / Language", "🌐 Language"):
        bot.send_message(message.chat.id, tr(user_id, "choose_language"), reply_markup=language_keyboard())
        return

    if text in ("💎 مدیریت اشتراک‌ها", "💎 Subscription plans"):
        if is_owner(user_id):
            ensure_default_plan()
            bot.send_message(message.chat.id, tr(user_id, "owner_plans"), reply_markup=plans_keyboard(user_id, owner=True))
        return

    if text in ("📢 همه کانال‌ها", "📢 All channels"):
        if is_owner(user_id):
            # Reuse owner callback logic through a small direct rendering.
            channels = execute("""
                SELECT c.*, a.name AS admin_name FROM channels c
                LEFT JOIN admins a ON a.user_id=c.admin_id ORDER BY c.id DESC
            """, fetchall=True)
            kb = types.InlineKeyboardMarkup()
            out = tr(user_id, "owner_channels") + "\n\n"
            if not channels:
                out += tr(user_id, "no_channels")
            else:
                for c in channels:
                    out += f"👤 {c['admin_name'] or c['admin_id']} | {c['channel_username'] or c['channel_id']}\n"
                    kb.add(types.InlineKeyboardButton(
                        f"🗑 {c['channel_username'] or c['channel_id']}",
                        callback_data=f"owner_del_channel:{c['id']}"
                    ))
            kb.add(types.InlineKeyboardButton("➕ افزودن کانال", callback_data="owner_add_channel"))
            bot.send_message(message.chat.id, out, reply_markup=kb)
        return

    state = user_states.get(user_id)

    if state:
        process_state(message, state)
        return


# =========================
# عملیات ادمین
# =========================

def show_admin_files(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, password_text(user_id, "no_access"))
        return

    files = execute(
        """
        SELECT * FROM files
        WHERE admin_id = ? AND deleted = 0
        ORDER BY id DESC
        """,
        (message.from_user.id,),
        fetchall=True
    )

    if not files:
        bot.send_message(message.chat.id, "📂 هنوز فایلی آپلود نکرده‌اید.")
        return

    for item in files:
        bot.send_message(
            message.chat.id,
            f"📄 <b>{html.escape(item['file_name'] or 'بدون نام')}</b>\n"
            f"⬇️ دانلود: {item['downloads']}\n"
            f"📅 آپلود: {item['upload_date']}\n"
            f"🔗 توکن: <code>{item['token']}</code>\n"
            f"{'🔐 این فایل رمز دارد' if item.get('password_hash') else '🔓 بدون رمز'}",
            reply_markup=types.InlineKeyboardMarkup(
                keyboard=[
                    [
                        types.InlineKeyboardButton(
                            "🗑 حذف",
                            callback_data=f"delete_file:{item['id']}"
                        ),
                        types.InlineKeyboardButton(
                            "✏️ ویرایش کپشن",
                            callback_data=f"edit_caption:{item['id']}"
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            "🔐 رمز فایل" if item.get("password_hash") else "🔓 بدون رمز / تعیین رمز",
                            callback_data=f"file_password_menu:{item['id']}"
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            "📊 آمار دانلود",
                            callback_data=f"file_stats:{item['id']}"
                        )
                    ]
                ]
            )
        )


def show_admin_stats(message):
    admin_id = message.from_user.id

    if not is_admin(admin_id):
        bot.send_message(message.chat.id, password_text(user_id, "no_access"))
        return

    files = execute(
        "SELECT COUNT(*) AS total FROM files WHERE admin_id = ? AND deleted = 0",
        (admin_id,),
        fetchone=True
    )

    downloads = execute(
        """
        SELECT COUNT(*) AS total
        FROM downloads d
        JOIN files f ON f.id = d.file_id
        WHERE f.admin_id = ?
        """,
        (admin_id,),
        fetchone=True
    )

    bot.send_message(
        message.chat.id,
        f"📊 آمار شما:\n\n"
        f"📂 تعداد فایل‌ها: {files['total']}\n"
        f"⬇️ تعداد دانلودها: {downloads['total']}"
    )


def show_subscription(message):
    admin = get_admin(message.from_user.id)

    if not admin:
        bot.send_message(message.chat.id, "⛔ ادمین نیستید.")
        return

    bot.send_message(
        message.chat.id,
        f"💳 وضعیت اشتراک: {localized_status(message.from_user.id, admin['status'])}\n"
        f"📅 تاریخ پایان: {admin['expire_at']}"
    )


def channel_management(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, password_text(user_id, "no_access"))
        return

    channels = execute(
        "SELECT * FROM channels WHERE admin_id = ?",
        (message.from_user.id,),
        fetchall=True
    )

    text = "📢 کانال‌های اجباری:\n\n"

    if not channels:
        text += "هیچ کانالی ثبت نشده است."
    else:
        for channel in channels:
            text += (
                f"🆔 {channel['channel_id']}\n"
                f"🔗 {channel['channel_link'] or '-'}\n\n"
            )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            "➕ افزودن کانال",
            callback_data="add_channel"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(
            "🗑 حذف همه کانال‌ها",
            callback_data="clear_channels"
        )
    )

    bot.send_message(message.chat.id, text, reply_markup=keyboard)


# =========================
# عملیات مالک
# =========================

def show_admins(message):
    admins = execute(
        "SELECT * FROM admins ORDER BY id DESC",
        fetchall=True
    )

    if not admins:
        bot.send_message(message.chat.id, "هیچ ادمینی ثبت نشده است.")
        return

    text = "👥 لیست ادمین‌ها:\n\n"

    for admin in admins:
        file_count = execute(
            """
            SELECT COUNT(*) AS total
            FROM files
            WHERE admin_id = ? AND deleted = 0
            """,
            (admin["user_id"],),
            fetchone=True
        )

        download_count = execute(
            """
            SELECT COUNT(*) AS total
            FROM downloads d
            JOIN files f ON f.id = d.file_id
            WHERE f.admin_id = ?
            """,
            (admin["user_id"],),
            fetchone=True
        )

        text += (
            f"👤 {admin['name'] or '-'}\n"
            f"🆔 {admin['user_id']}\n"
            f"📅 پایان: {admin['expire_at']}\n"
            f"📂 فایل‌ها: {file_count['total']}\n"
            f"⬇️ دانلودها: {download_count['total']}\n"
            f"📌 وضعیت: {localized_status(message.from_user.id, admin['status'])}\n\n"
        )

    bot.send_message(message.chat.id, text)


def show_global_stats(message):
    users = execute(
        "SELECT COUNT(DISTINCT user_id) AS total FROM downloads",
        fetchone=True
    )

    downloads = execute(
        "SELECT COUNT(*) AS total FROM downloads",
        fetchone=True
    )

    files = execute(
        "SELECT COUNT(*) AS total FROM files WHERE deleted = 0",
        fetchone=True
    )

    admins = execute(
        "SELECT COUNT(*) AS total FROM admins",
        fetchone=True
    )

    bot.send_message(
        message.chat.id,
        f"📊 آمار کلی ربات:\n\n"
        f"👥 کاربران دریافت‌کننده: {users['total']}\n"
        f"⬇️ کل دانلودها: {downloads['total']}\n"
        f"📂 فایل‌های فعال: {files['total']}\n"
        f"🛡 تعداد ادمین‌ها: {admins['total']}"
    )


def show_all_files(message):
    files = execute(
        """
        SELECT f.*, a.name
        FROM files f
        LEFT JOIN admins a ON a.user_id = f.admin_id
        WHERE f.deleted = 0
        ORDER BY f.id DESC
        """,
        fetchall=True
    )

    if not files:
        bot.send_message(message.chat.id, "هیچ فایلی وجود ندارد.")
        return

    text = "📂 فایل‌های ثبت‌شده:\n\n"

    for item in files:
        text += (
            f"📄 {item['file_name']}\n"
            f"👤 ادمین: {item['name'] or item['admin_id']}\n"
            f"⬇️ دانلود: {item['downloads']}\n"
            f"📅 تاریخ: {item['upload_date']}\n"
            f"{'🔐 دارای رمز' if item.get('password_hash') else '🔓 بدون رمز'}\n\n"
        )
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton("🗑 حذف", callback_data=f"delete_file:{item['id']}"),
            types.InlineKeyboardButton("✏️ ویرایش کپشن", callback_data=f"edit_caption:{item['id']}"),
            types.InlineKeyboardButton("📊 آمار", callback_data=f"file_stats:{item['id']}")
        )
        bot.send_message(message.chat.id, text, reply_markup=kb)
        text = ""

    if text:
        bot.send_message(message.chat.id, text)


# =========================
# پردازش حالت‌های مرحله‌ای
# =========================

def process_state(message, state):
    user_id = message.from_user.id
    action = state.get("action")
    text = message.text.strip()

    if action == "delete_after":
        try:
            seconds = int(text)

            if seconds < 1:
                raise ValueError

            execute(
                """
                INSERT INTO settings (admin_id, delete_after)
                VALUES (?, ?)
                ON CONFLICT(admin_id)
                DO UPDATE SET delete_after = EXCLUDED.delete_after
                """,
                (user_id, seconds),
                commit=True
            )

            clear_state(user_id)
            bot.send_message(
                message.chat.id,
                f"✅ مدت حذف خودکار روی {seconds} ثانیه تنظیم شد.",
                reply_markup=admin_keyboard(user_id)
            )

        except ValueError:
            bot.send_message(message.chat.id, "❌ فقط یک عدد مثبت ارسال کنید.")

    elif action == "add_admin":
        if not is_owner(user_id):
            clear_state(user_id)
            return

        try:
            target_id = int(text)
        except ValueError:
            bot.send_message(message.chat.id, "❌ آیدی باید عددی باشد.")
            return

        existing = get_admin(target_id)
        expire = datetime.now() + timedelta(days=DEFAULT_SUB_DAYS)

        if existing:
            execute(
                """
                UPDATE admins
                SET status = 'active', expire_at = ?
                WHERE user_id = ?
                """,
                (date_text(expire), target_id),
                commit=True
            )
        else:
            execute(
                """
                INSERT INTO admins
                (user_id, name, created_at, expire_at, status)
                VALUES (?, ?, ?, ?, 'active')
                """,
                (
                    target_id,
                    str(target_id),
                    now_text(),
                    date_text(expire)
                ),
                commit=True
            )

        execute(
            """
            INSERT INTO settings (admin_id, delete_after)
            VALUES (?, ?)
            ON CONFLICT(admin_id) DO NOTHING
            """,
            (target_id, DEFAULT_DELETE_AFTER),
            commit=True
        )

        clear_state(user_id)

        bot.send_message(
            message.chat.id,
            f"✅ ادمین {target_id} افزوده یا تمدید شد.",
            reply_markup=owner_keyboard(user_id)
        )

        safe_send(
            target_id,
            "✅ شما به عنوان ادمین ربات فعال شدید.\nبرای ورود از /panel استفاده کنید."
        )

    elif action == "remove_admin":
        if not is_owner(user_id):
            clear_state(user_id)
            return

        try:
            target_id = int(text)
        except ValueError:
            bot.send_message(message.chat.id, "❌ آیدی باید عددی باشد.")
            return

        execute(
            "UPDATE admins SET status = 'blocked' WHERE user_id = ?",
            (target_id,),
            commit=True
        )

        clear_state(user_id)

        bot.send_message(
            message.chat.id,
            f"✅ ادمین {target_id} مسدود شد.",
            reply_markup=owner_keyboard(user_id)
        )

        safe_send(target_id, "⛔ دسترسی ادمینی شما مسدود شد.")


# =========================
# Callbackهای فایل و کانال
# =========================

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_file:"))
def delete_file_callback(call):
    admin_id = call.from_user.id
    file_id = int(call.data.split(":")[1])

    file_row = execute(
        "SELECT * FROM files WHERE id = ?",
        (file_id,),
        fetchone=True
    )

    if not file_row or (file_row["admin_id"] != admin_id and not is_owner(admin_id)):
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return

    execute(
        "UPDATE files SET deleted = 1 WHERE id = ?",
        (file_id,),
        commit=True
    )

    bot.answer_callback_query(call.id, "فایل حذف شد.")
    bot.edit_message_text(
        "🗑 فایل حذف شد و لینک آن غیرفعال گردید.",
        call.message.chat.id,
        call.message.message_id
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_caption:"))
def edit_caption_callback(call):
    admin_id = call.from_user.id
    file_id = int(call.data.split(":")[1])

    file_row = execute(
        "SELECT * FROM files WHERE id = ?",
        (file_id,),
        fetchone=True
    )

    if not file_row or (file_row["admin_id"] != admin_id and not is_owner(admin_id)):
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return

    user_states[admin_id] = {
        "action": "edit_caption",
        "file_id": file_id
    }

    bot.answer_callback_query(call.id)
    bot.send_message(
        admin_id,
        "✏️ کپشن جدید را ارسال کنید.\n"
        "برای حذف کپشن، عبارت «بدون کپشن» را ارسال کنید."
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("set_password_"))
def set_password_choice_callback(call):
    user_id = call.from_user.id
    state = user_states.get(user_id, {})
    if state.get("action") != "choose_file_password":
        bot.answer_callback_query(call.id, "❌ این درخواست منقضی شده است.", show_alert=True)
        return

    file_id = int(state["file_id"])
    file_row = execute("SELECT * FROM files WHERE id = ?", (file_id,), fetchone=True)
    if not file_row or (file_row["admin_id"] != user_id and not is_owner(user_id)):
        clear_state(user_id)
        bot.answer_callback_query(call.id, password_text(user_id, "no_access"), show_alert=True)
        return

    choice = call.data.rsplit("_", 1)[1]
    if choice == "no":
        execute("UPDATE files SET password_hash = NULL WHERE id = ?", (file_id,), commit=True)
        clear_state(user_id)
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            password_text(user_id, "password_saved_no_password"),
            reply_markup=owner_keyboard(user_id) if is_owner(user_id) else admin_keyboard(user_id)
        )
        return

    user_states[user_id] = {
        "action": "set_file_password",
        "file_id": file_id
    }
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        password_text(user_id, "send_password")
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("file_password_menu:"))
def file_password_menu_callback(call):
    user_id = call.from_user.id
    file_id = int(call.data.split(":")[1])
    file_row = execute("SELECT * FROM files WHERE id = ?", (file_id,), fetchone=True)

    if not file_row or (file_row["admin_id"] != user_id and not is_owner(user_id)):
        bot.answer_callback_query(call.id, password_text(user_id, "no_access"), show_alert=True)
        return

    kb = types.InlineKeyboardMarkup()
    if file_row.get("password_hash"):
        if get_language(user_id) == "en":
            kb.row(
                types.InlineKeyboardButton(password_text(user_id, "change_password"), callback_data=f"change_password:{file_id}"),
                types.InlineKeyboardButton(password_text(user_id, "remove_password"), callback_data=f"remove_password:{file_id}")
            )
        else:
            kb.row(
                types.InlineKeyboardButton(password_text(user_id, "change_password"), callback_data=f"change_password:{file_id}"),
                types.InlineKeyboardButton(password_text(user_id, "remove_password"), callback_data=f"remove_password:{file_id}")
            )
        status = password_text(user_id, "has_password_status")
    else:
        if get_language(user_id) == "en":
            kb.add(types.InlineKeyboardButton(password_text(user_id, "set_password"), callback_data=f"change_password:{file_id}"))
            status = password_text(user_id, "no_password_status")
        else:
            kb.add(types.InlineKeyboardButton(password_text(user_id, "set_password"), callback_data=f"change_password:{file_id}"))
            status = password_text(user_id, "no_password_status")

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, status, reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data.startswith("change_password:"))
def change_password_callback(call):
    user_id = call.from_user.id
    file_id = int(call.data.split(":")[1])
    file_row = execute("SELECT * FROM files WHERE id = ?", (file_id,), fetchone=True)

    if not file_row or (file_row["admin_id"] != user_id and not is_owner(user_id)):
        bot.answer_callback_query(call.id, password_text(user_id, "no_access"), show_alert=True)
        return

    user_states[user_id] = {"action": "set_file_password", "file_id": file_id}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, password_text(user_id, "send_new_password"))


@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_password:"))
def remove_password_callback(call):
    user_id = call.from_user.id
    file_id = int(call.data.split(":")[1])
    file_row = execute("SELECT * FROM files WHERE id = ?", (file_id,), fetchone=True)

    if not file_row or (file_row["admin_id"] != user_id and not is_owner(user_id)):
        bot.answer_callback_query(call.id, password_text(user_id, "no_access"), show_alert=True)
        return

    execute("UPDATE files SET password_hash = NULL WHERE id = ?", (file_id,), commit=True)
    bot.answer_callback_query(call.id, password_text(user_id, "password_removed"))
    bot.send_message(
        call.message.chat.id,
        password_text(user_id, "password_removed"),
        reply_markup=owner_keyboard(user_id) if is_owner(user_id) else admin_keyboard(user_id)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("file_stats:"))
def file_stats_callback(call):
    admin_id = call.from_user.id
    file_id = int(call.data.split(":")[1])

    file_row = execute(
        "SELECT * FROM files WHERE id = ?",
        (file_id,),
        fetchone=True
    )

    if not file_row or (file_row["admin_id"] != admin_id and not is_owner(admin_id)):
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return

    users = execute(
        """
        SELECT username, user_id, timestamp
        FROM downloads
        WHERE file_id = ?
        ORDER BY id DESC
        LIMIT 10
        """,
        (file_id,),
        fetchall=True
    )

    text = (
        f"📊 آمار فایل:\n\n"
        f"📄 نام: {file_row['file_name']}\n"
        f"⬇️ تعداد دانلود: {file_row['downloads']}\n"
        f"📅 تاریخ آپلود: {file_row['upload_date']}\n\n"
        f"👥 آخرین دریافت‌کنندگان:\n"
    )

    if not users:
        text += "موردی ثبت نشده است."
    else:
        for user in users:
            text += (
                f"• {user['username'] or user['user_id']} - "
                f"{user['timestamp']}\n"
            )

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "add_channel")
def add_channel_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return

    user_states[call.from_user.id] = {
        "action": "add_channel"
    }

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "📢 اطلاعات کانال را در یک خط ارسال کنید:\n\n"
        "فرمت پیشنهادی:\n"
        "@channel_username | https://t.me/channel_username\n\n"
        "ربات باید در کانال ادمین باشد."
    )


@bot.callback_query_handler(func=lambda call: call.data == "clear_channels")
def clear_channels_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
        return

    execute(
        "DELETE FROM channels WHERE admin_id = ?",
        (call.from_user.id,),
        commit=True
    )

    bot.answer_callback_query(call.id, "کانال‌ها حذف شدند.")
    bot.send_message(call.message.chat.id, "✅ همه کانال‌های اجباری حذف شدند.")


# =========================
# تکمیل حالت‌های متنی
# =========================

_old_process_state = process_state


def process_state(message, state):
    user_id = message.from_user.id
    action = state.get("action")
    text = message.text.strip()

    if action == "verify_file_password":
        token = state.get("file_token")
        file_row = execute(
            "SELECT * FROM files WHERE token = ? AND deleted = 0",
            (token,),
            fetchone=True
        )

        if not file_row:
            clear_state(user_id)
            bot.send_message(message.chat.id, password_text(user_id, "file_not_found"))
            return

        owner_id = int(file_row["admin_id"])
        if owner_id != OWNER_ID and not is_admin(owner_id):
            clear_state(user_id)
            bot.send_message(message.chat.id, "❌ اشتراک صاحب این فایل منقضی شده یا فایل غیرفعال است.")
            return

        if verify_file_password(text, file_row.get("password_hash")):
            clear_state(user_id)
            send_file_to_user(message.chat.id, message.from_user, file_row)
        else:
            bot.send_message(
                message.chat.id,
                password_text(user_id, "wrong_password")
            )
        return

    if action == "set_file_password":
        if len(text) < 4:
            bot.send_message(message.chat.id, password_text(user_id, "password_too_short"))
            return

        file_id = state.get("file_id")
        file_row = execute("SELECT * FROM files WHERE id = ?", (file_id,), fetchone=True)
        if not file_row or (file_row["admin_id"] != user_id and not is_owner(user_id)):
            clear_state(user_id)
            bot.send_message(message.chat.id, password_text(user_id, "no_access"))
            return

        execute(
            "UPDATE files SET password_hash = ? WHERE id = ?",
            (hash_file_password(text), file_id),
            commit=True
        )
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            password_text(user_id, "password_set"),
            reply_markup=owner_keyboard(user_id) if is_owner(user_id) else admin_keyboard(user_id)
        )
        return

    if action == "edit_caption":
        caption = "" if text == "بدون کپشن" else text

        if is_owner(user_id):
            execute(
                "UPDATE files SET caption = ? WHERE id = ?",
                (caption, state["file_id"]),
                commit=True
            )
        else:
            execute(
                "UPDATE files SET caption = ? WHERE id = ? AND admin_id = ?",
                (caption, state["file_id"], user_id),
                commit=True
            )

        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "✅ کپشن فایل ویرایش شد.",
            reply_markup=owner_keyboard(user_id) if is_owner(user_id) else admin_keyboard(user_id)
        )
        return

    if action == "owner_add_plan":
        if not is_owner(user_id):
            clear_state(user_id)
            return
        parts = [part.strip() for part in text.split("|")]
        if len(parts) < 5:
            bot.send_message(message.chat.id, tr(user_id, "invalid_plan"))
            return
        try:
            name_fa, name_en = parts[0], parts[1]
            days, stars = int(parts[2]), int(parts[3])
            recurring = parts[4].lower() in ("yes", "true", "1", "بله")
            if days < 1 or stars < 1 or stars > 10000 or (recurring and days != 30):
                raise ValueError
            execute("""
                INSERT INTO subscription_plans
                (name_fa,name_en,days,stars,recurring,active,created_at)
                VALUES(?,?,?,?,?,TRUE,?)
            """, (name_fa[:64], name_en[:64], days, stars, recurring, now_text()), commit=True)
            clear_state(user_id)
            bot.send_message(message.chat.id, tr(user_id, "plan_added"), reply_markup=owner_keyboard(user_id))
        except Exception:
            bot.send_message(message.chat.id, tr(user_id, "invalid_plan"))
        return

    if action == "owner_delete_after_admin":
        if not is_owner(user_id):
            clear_state(user_id)
            return
        try:
            target_id = int(text)
            if not get_admin(target_id):
                bot.send_message(message.chat.id, "❌ ادمین پیدا نشد.")
                return
            user_states[user_id] = {"action": "owner_delete_after_seconds", "admin_id": target_id}
            bot.send_message(message.chat.id, tr(user_id, "send_seconds"))
        except ValueError:
            bot.send_message(message.chat.id, tr(user_id, "send_admin_id"))
        return

    if action == "owner_delete_after_seconds":
        if not is_owner(user_id):
            clear_state(user_id)
            return
        try:
            seconds = int(text)
            if seconds < 1:
                raise ValueError
            target_id = state["admin_id"]
            execute("""
                INSERT INTO settings(admin_id,delete_after) VALUES(?,?)
                ON CONFLICT(admin_id) DO UPDATE SET delete_after=EXCLUDED.delete_after
            """, (target_id, seconds), commit=True)
            clear_state(user_id)
            bot.send_message(message.chat.id, tr(user_id, "delete_set"), reply_markup=owner_keyboard(user_id))
        except ValueError:
            bot.send_message(message.chat.id, tr(user_id, "invalid_seconds"))
        return

    if action == "owner_add_channel":
        if not is_owner(user_id):
            clear_state(user_id)
            return

        parts = [part.strip() for part in text.split("|")]
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ فرمت ناقص است.")
            return

        # Two supported formats:
        # 1) @channel | https://t.me/channel  -> global for all files
        # 2) admin_id | @channel | https://t.me/channel -> only that admin
        if parts[0].lstrip("-").isdigit():
            target_admin = int(parts[0])
            channel_username = parts[1]
            channel_link = parts[2] if len(parts) > 2 else ""
            if not get_admin(target_admin):
                bot.send_message(message.chat.id, "❌ این ادمین در ربات ثبت نشده است.")
                return
        else:
            target_admin = OWNER_ID
            channel_username = parts[0]
            channel_link = parts[1]

        if not channel_username:
            bot.send_message(message.chat.id, "❌ نام/آیدی کانال خالی است.")
            return

        # Store the actual Telegram chat identifier in channel_id.
        # For public channels @username works directly with get_chat/get_chat_member.
        channel_id = channel_username
        try:
            chat = bot.get_chat(channel_id)
            resolved_id = str(chat.id)
            resolved_username = getattr(chat, "username", None) or channel_username
        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ کانال پیدا نشد یا ربات دسترسی لازم ندارد.\n"
                "ربات را داخل کانال ادمین کنید و دوباره تلاش کنید."
            )
            return

        if not channel_link:
            if resolved_username:
                channel_link = "https://t.me/" + str(resolved_username).lstrip("@")
            else:
                bot.send_message(message.chat.id, "❌ لینک کانال را وارد کنید.")
                return

        execute("""
            INSERT INTO channels(admin_id,channel_id,channel_username,channel_link)
            VALUES(?,?,?,?)
            ON CONFLICT DO NOTHING
        """, (target_admin, resolved_id, resolved_username, channel_link), commit=True)

        clear_state(user_id)
        scope_text = "همه فایل‌ها" if target_admin == OWNER_ID else f"ادمین {target_admin}"
        bot.send_message(
            message.chat.id,
            f"✅ کانال اجباری برای {scope_text} ثبت شد.",
            reply_markup=owner_keyboard(user_id)
        )
        return

    if action == "add_channel":
        parts = [part.strip() for part in text.split("|")]

        channel_username = parts[0]
        channel_link = parts[1] if len(parts) > 1 else ""

        if not channel_username:
            bot.send_message(message.chat.id, "❌ اطلاعات کانال ناقص است.")
            return

        channel_id = channel_username

        try:
            chat = bot.get_chat(channel_id)
            resolved_id = str(chat.id)
            resolved_username = getattr(chat, "username", None) or channel_username
        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ کانال پیدا نشد یا ربات در کانال دسترسی لازم ندارد.\n"
                "ربات را داخل کانال ادمین کنید و دوباره تلاش کنید."
            )
            return

        if not channel_link and resolved_username:
            channel_link = "https://t.me/" + str(resolved_username).lstrip("@")

        execute(
            """
            INSERT INTO channels
            (admin_id, channel_id, channel_username, channel_link)
            VALUES (?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (
                user_id,
                resolved_id,
                resolved_username,
                channel_link
            ),
            commit=True
        )

        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "✅ کانال اجباری با موفقیت ثبت شد.",
            reply_markup=admin_keyboard(user_id)
        )
        return

    _old_process_state(message, state)


# =========================
# بررسی دوره‌ای اشتراک‌ها
# =========================

def subscription_checker():
    while True:
        try:
            admins = execute(
                "SELECT * FROM admins WHERE status = 'active'",
                fetchall=True
            )

            current_time = datetime.now()

            for admin in admins:
                try:
                    expire_at = datetime.strptime(
                        admin["expire_at"],
                        "%Y-%m-%d %H:%M:%S"
                    )

                    if expire_at <= current_time:
                        execute(
                            """
                            UPDATE admins
                            SET status = 'expired'
                            WHERE user_id = ?
                            """,
                            (admin["user_id"],),
                            commit=True
                        )

                        safe_send(
                            admin["user_id"],
                            "⚠️ اشتراک شما منقضی شده است.\n"
                            "آپلود فایل و لینک‌های قبلی غیرفعال شدند."
                        )

                except Exception:
                    continue

        except Exception:
            pass

        time.sleep(60)


# =========================
# اجرای برنامه
# =========================


if __name__ == "__main__":
    # ساخت/آماده‌سازی دیتابیس
    init_database()
    ensure_default_plan()

    # اجرای Flask در Thread جداگانه برای دریافت webhook
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True,
        name="flask-server"
    )
    flask_thread.start()

    # بررسی دوره‌ای اشتراک‌ها
    checker_thread = threading.Thread(
        target=subscription_checker,
        daemon=True,
        name="subscription-checker"
    )
    checker_thread.start()

    print("ربات با موفقیت اجرا شد.")
    print(f"Webhook path: {WEBHOOK_PATH}")
    print(f"Webhook base URL configured: {'yes' if WEBHOOK_URL else 'no'}")
    print("Flask health server نیز در پس‌زمینه اجرا شد.")

    # Telegram webhook
    # Telegram sends every new update to the Flask endpoint above.
    # This lets a sleeping Render Free Web Service wake up on demand.
    setup_telegram_webhook()

    # Keep the main process alive while Flask handles webhook requests.
    while True:
        time.sleep(3600)
