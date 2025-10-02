import os
import requests
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from lxml import etree

# --- تنظیمات اولیه ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# بررسی کنید که توکن‌ها وجود دارند
if not TELEGRAM_BOT_TOKEN or not GOOGLE_API_KEY:
raise ValueError("توکن‌های ربات و گوگل API را در Environment Variables تنظیم کنید.")

# پیکربندی مدل هوش مصنوعی Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# --- تعریف پروژه‌ها ---
# نام پروژه را به عنوان کلید و آدرس سایت‌مپ را به عنوان مقدار وارد کنید
PROJECTS = {
    "caspian": {
        "name": "کاسپین ترخیص",
        "sitemap_url": "https://caspiantarkhis.com/post-sitemap.xml"
    },
    "pooyanwood": {
        "name": "پویان وود",
        "sitemap_url": "https://pooyanwood.com/post-sitemap.xml"
    },
    "bardiyawood": {
        "name": "بردیاچوب",
        "sitemap_url": "https://bardiyawood.com/post-sitemap.xml"
    },
    "electrorasa": {
        "name": "الکترورسا",
        "sitemap_url": "https://electrorasa.com/post-sitemap.xml"
    },
    "plgkala": {
        "name": "پی ال جی کالا",
        "sitemap_url": "https://plgkala.com/post-sitemap.xml"
    },

    # می‌توانید پروژه‌های بیشتری اضافه کنید
}

# --- توابع ربات ---

# 1. تابع برای دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """با ارسال دستور /start، لیست پروژه‌ها را به صورت دکمه‌های شیشه‌ای نمایش می‌دهد."""
    keyboard = []
    for key, value in PROJECTS.items():
        keyboard.append([InlineKeyboardButton(value["name"], callback_data=key)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("سلام! لطفاً یک پروژه را برای تحلیل انتخاب کنید:", reply_markup=reply_markup)

# 2. تابع برای مدیریت انتخاب پروژه
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پس از کلیک روی دکمه پروژه، آن را ذخیره کرده و از کاربر عنوان مقاله را می‌پرسد."""
    query = update.callback_query
    await query.answer()

    project_key = query.data
    context.user_data['selected_project'] = PROJECTS[project_key]

    project_name = PROJECTS[project_key]['name']
    await query.edit_message_text(text=f"پروژه انتخاب شده: **{project_name}**\n\nحالا عنوان مقاله یا کلمه کلیدی اصلی خود را وارد کنید:")

# 3. تابع اصلی برای دریافت عنوان و تحلیل سایت‌مپ
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عنوان مقاله را از کاربر دریافت کرده، سایت‌مپ را تحلیل و نتیجه را برمی‌گرداند."""
    if 'selected_project' not in context.user_data:
        await update.message.reply_text("لطفاً ابتدا با ارسال دستور /start یک پروژه را انتخاب کنید.")
        return

    article_title = update.message.text
    project = context.user_data['selected_project']
    sitemap_url = project['sitemap_url']

    await update.message.reply_text("در حال بررسی سایت‌مپ و تحلیل ارتباط معنایی... لطفاً کمی صبر کنید ⌛️")

    try:
        # 1. دریافت سایت مپ
        response = requests.get(sitemap_url)
        response.raise_for_status()  # بررسی خطا در درخواست

        # 2. استخراج تمام URL ها از سایت مپ
        # namespace XML را برای سایت مپ ها در نظر می گیریم
        root = etree.fromstring(response.content)
        urls = [elem.text for elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]

        if not urls:
            await update.message.reply_text("هیچ لینکی در سایت‌مپ پیدا نشد یا فرمت آن پشتیبانی نمی‌شود.")
            return

        # 3. ساخت پرامپت (Prompt) برای مدل Gemini
        prompt = f"""
        شما یک متخصص SEO هستید که وظیفه‌اش پیشنهاد لینک داخلی است.
        عنوان مقاله جدید من این است: "{article_title}"

        این لیست URL های موجود در سایت‌مپ است:
        {", ".join(urls)}

        با توجه به عنوان مقاله من، لطفاً مرتبط‌ترین URLها را از لیست بالا پیدا کن که برای لینک دادن مناسب هستند.
        برای هر URL، یک انکرتکست مناسب (که همان عنوان مقاله آن URL است) پیشنهاد بده.

        خروجی را به صورت یک لیست با فرمت زیر ارائه بده:
        - **انکرتکست:** [انکرتکست پیشنهادی]
        - **لینک:** [آدرس URL]

        فقط لینک‌های با بیشترین ارتباط معنایی را برگردان.
        """

        # 4. ارسال درخواست به API گوگل
        ai_response = model.generate_content(prompt)
        
        # 5. ارسال نتیجه به کاربر
        await update.message.reply_text(ai_response.text)

    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"خطا در دسترسی به سایت‌مپ: {e}")
    except Exception as e:
        await update.message.reply_text(f"یک خطای غیرمنتظره رخ داد: {e}")
    finally:
        # پاک کردن پروژه انتخاب شده برای درخواست بعدی
        del context.user_data['selected_project']


# --- راه‌اندازی ربات ---
def main() -> None:
    """ربات را استارت می‌زند و منتظر دستورات می‌ماند."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # تعریف دستورات و هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # اجرای ربات
    print("ربات در حال اجرا است...")
    application.run_polling()

if __name__ == "__main__":
    main()