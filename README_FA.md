# بسته یک‌سروره چهار ربات Borhan_SK

این بسته از فایل‌های اصلی ارسالی ساخته شده و هر چهار پروژه را در **یک سرویس Python/Flask + Gunicorn** اجرا می‌کند. دیتابیس‌ها جابه‌جا یا ادغام نمی‌شوند.

## مسیرهای ربات‌ها

- File Management: `/filter/telegram-webhook`
- FitBot: `/fit/webhook/<HOOK_PATH>`
- Nima: `/nima/webhook/<BOT_TOKEN>`
- Shop: `/shop/telegram-webhook`

وضعیت سرویس: `/health` و وضعیت بارگذاری هر ربات: `/status`.

## تغییرات انجام‌شده

- حلقه‌های self-ping/Keepalive از FitBot و Shop حذف شده‌اند.
- Nima و File Management حلقه Keepalive نداشتند؛ وب‌هوکشان حفظ شده است.
- ربات File Management همچنان از `DATABASE_URL` فعلی PostgreSQL در Supabase استفاده می‌کند؛ روش یا ساختار دیتابیس آن تغییر نکرده است.
- سه ربات دیگر همچنان از Supabase REST/API خودشان استفاده می‌کنند.
- هر ربات ENV مستقل دارد و آدرس وب‌هوک هر چهار ربات به‌صورت خودکار از `APP_BASE_URL` و مسیر مخصوص خودش ساخته می‌شود.
- برای اینکه متغیرهای درون‌حافظه‌ای ربات‌ها بین چند worker از بین نروند، دستور اجرا عمداً یک worker و ۱۲ thread دارد.

## ۱) مقداردهی ENV

برای هر پروژه فایل `.env.example` همان پوشه را به `.env` تغییر نام بده و مقادیر قدیمی همان ربات را از Render وارد کن:

- `apps/filter/.env`
- `apps/fit/.env`
- `apps/nima/.env`
- `apps/shop/.env`

**هیچ‌کدام از توکن‌ها یا کلیدها را در GitHub عمومی قرار نده.** فایل‌های `.env` در `.gitignore` هستند.

فایل `.env.server.example` را به `.env` در ریشه بسته تغییر نام بده و دامنه اصلی سرور را در آن وارد کن. مقدار `APP_BASE_URL` باید فقط دامنه اصلی باشد، بدون مسیر ربات و بدون `/` انتهایی؛ مثال:

`APP_BASE_URL=https://your-service.onrender.com`

در Render معمولاً `RENDER_EXTERNAL_URL` خودکار فراهم می‌شود، اما برای میزبان‌های دیگر بهتر است `APP_BASE_URL` را دستی تنظیم کنی.

### متغیرهای ضروری هر پروژه

**File Management (`apps/filter/.env`)**

- `BOT_TOKEN`
- `OWNER_ID`
- `DATABASE_URL` — آدرس اتصال PostgreSQL پروژه Supabase فعلی (همان مقدار قبلی Render)
- `WEBHOOK_SECRET` — اختیاری؛ اگر تنظیم شده باشد باید همان مقدار در سرور جدید بماند.

**FitBot (`apps/fit/.env`)**

- `BOT_TOKEN`
- `OWNER_ID`
- `WEBHOOK_SECRET`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SETUP_KEY` (برای endpointهای مدیریتی تنظیم وب‌هوک)

**Nima (`apps/nima/.env`)**

- `BOT_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `OWNER_ID` اختیاری؛ مقدار پیش‌فرض در کد اصلی موجود است.

**Shop (`apps/shop/.env`)**

- `BOT_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `WEBHOOK_SECRET` — حتماً یک مقدار قوی و غیر از `change_me`
- `ADMIN_PASSWORD`
- `SESSION_SECRET` — یک کلید تصادفی قوی برای نشست‌های پنل وب (مثلاً با `python -c "import secrets; print(secrets.token_urlsafe(48))"` بساز).
- بقیه تنظیمات فروشگاه را از ENV قبلی همان ربات کپی کن.

## ۲) نصب روی سرور Linux / میزبان Python

داخل پوشه ریشه بسته:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

سپس سرویس را با این دستور اجرا کن:

```bash
gunicorn --workers 1 --threads 12 --worker-class gthread --timeout 120 --bind 0.0.0.0:${PORT:-8000} wsgi:application
```

اگر میزبان از `Procfile` یا `render.yaml` پشتیبانی کند، فایل‌ها از قبل داخل ZIP هستند.

## ۳) متغیرهای محیطی با داشبورد هاست

اگر میزبان اجازه فایل `.env` نمی‌دهد، مقادیر را در تنظیمات Environment همان سرویس با پیشوند پروژه تعریف کن. مثال:

- `FILTER_BOT_TOKEN`, `FILTER_DATABASE_URL`, `FILTER_OWNER_ID`
- `FIT_BOT_TOKEN`, `FIT_OWNER_ID`, `FIT_WEBHOOK_SECRET`, `FIT_SUPABASE_URL`, `FIT_SUPABASE_SERVICE_ROLE_KEY`
- `NIMA_BOT_TOKEN`, `NIMA_SUPABASE_URL`, `NIMA_SUPABASE_KEY`
- `SHOP_BOT_TOKEN`, `SHOP_SUPABASE_URL`, `SHOP_SUPABASE_KEY`, `SHOP_WEBHOOK_SECRET`, `SHOP_ADMIN_PASSWORD`, `SHOP_SESSION_SECRET`

نام متغیر بعد از پیشوند باید دقیقاً همان نام اصلی باشد. مقدار متغیر prefixed در پنل هاست بر مقدار فایل `.env` اولویت دارد.

## ۴) بعد از Deploy

1. آدرس `https://YOUR-SERVER/health` باید `status: ok` بدهد.
2. آدرس `https://YOUR-SERVER/status` باید هر چهار پروژه را `loaded: true` نشان بدهد.
3. آدرس‌های سلامت هر ربات: `/filter/health`، `/fit/health`، `/nima/health` و `/shop/health`.
4. در لاگ‌ها پیام‌های ثبت webhook را بررسی کن و از `getWebhookInfo` یا endpointهای وضعیت موجود هر ربات برای تأیید نهایی استفاده کن.
5. ابتدا هر ربات را با یک پیام `/start` آزمایش کن؛ بعد سرویس قدیمی Render را خاموش کن.

## نکات مهم

- هیچ SQL migration جدیدی برای سه پروژه Supabase دیگر اجرا نمی‌شود. ربات File Management هنگام شروع همان `init_database()` موجود در فایل اصلی را اجرا می‌کند؛ این تابع `CREATE TABLE IF NOT EXISTS`، افزودن ستون/ایندکس‌های لازم و ساخت پلن پیش‌فرض در صورت نبودن را انجام می‌دهد، درست مانند اجرای اصلی ربات.
- `DATABASE_URL` در File Management باید اتصال PostgreSQL خود Supabase باشد. این ربات برخلاف سه پروژه دیگر از Supabase REST استفاده نمی‌کند؛ این موضوع در بسته دست‌نخورده نگه داشته شده است.
- پروژه‌ها باید در یک پردازش بمانند؛ تعداد Gunicorn workers را روی ۱ نگه دار، چون state و handlerهای اصلی بعضی ربات‌ها در حافظه پردازش هستند.
- یک سرویس رایگان که بعد از بیکاری Sleep می‌شود با حذف Keepalive همیشه روشن نمی‌ماند. وب‌هوک درخواست را می‌فرستد، اما اگر میزبان در خواب باشد ممکن است اولین پاسخ با تأخیر سردشدن سرویس مواجه شود. برای پاسخ سریعِ پایدار، میزبان باید واقعاً Always-on باشد.
- میزبانی که پورت خروجی PostgreSQL را مسدود کند، File Management را وصل نخواهد کرد؛ میزبان باید اجازه اتصال TLS به Supabase PostgreSQL و HTTPS خروجی به Telegram/Supabase را بدهد.
- فایل SQL یا داده‌ای از Supabase در این بسته اجرا یا تغییر داده نشده است.
