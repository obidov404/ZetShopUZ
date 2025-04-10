import os
import logging
import asyncio
from datetime import datetime
from typing import Union, Dict, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from database import Database
from keyboards import get_categories_keyboard, get_product_keyboard, get_main_menu_keyboard, get_admin_keyboard
from utils import extract_product_info, format_price

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize router
router = Router(name="catalog_router")

# Constants
CHANNEL_ID = -1002348319543
CHANNEL_USERNAME = "@ZetShopUz"

# Admin list - add admin user IDs here
ADMIN_IDS = [636974091]  # Replace with actual admin user IDs

# Initialize database
db = Database()

# User states
user_states: Dict[int, Dict[str, Union[str, int]]] = {}

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    await message.answer(
        "🛍 Assalomu alaykum! ZetShop katalogiga xush kelibsiz!\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_menu_keyboard()
    )

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Handle /admin command."""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ Bu buyruq faqat adminlar uchun")
        return
    
    await message.answer(
        "👨‍💼 Admin panel",
        reply_markup=get_admin_keyboard()
    )

@router.message(F.text == "📋 Katalog")
async def show_catalog(message: Message):
    """Show product categories."""
    categories = await db.get_categories()
    
    if not categories:
        await message.answer(
            "❌ Hozircha katalogda mahsulotlar yo'q.\n"
            "Iltimos keyinroq qayta urinib ko'ring."
        )
        return
    
    await message.answer(
        "📋 Kategoriyalardan birini tanlang:",
        reply_markup=get_categories_keyboard(categories)
    )

@router.message(F.text == "ℹ️ Ma'lumot")
async def show_info(message: Message):
    """Show bot information."""
    await message.answer(
        "ℹ️ ZetShop - bu online do'kon\n\n"
        "🛍 Bizda siz uchun eng sifatli va arzon mahsulotlar mavjud.\n\n"
        "📞 Aloqa: +998901234567\n"
        "📍 Manzil: Toshkent shahri\n"
        "📱 Telegram: @ZetShopUz"
    )

@router.message(F.text)
async def handle_category_selection(message: Message):
    """Handle category selection."""
    products = await db.get_products_by_category(message.text)
    
    if not products:
        await message.answer(
            f"❌ Kechirasiz, \"{message.text}\" kategoriyasida hozircha mahsulotlar yo'q.\n"
            f"Iltimos boshqa kategoriyani tanlang."
        )
        return
    
    # Save user's current category and product index
    user_states[message.from_user.id] = {
        "category": message.text,
        "products": products,
        "current_index": 0
    }
    
    # Show first product
    product = products[0]
    await message.answer_photo(
        photo=product['image_file_id'],
        caption=(
            f"{product['description']}\n\n"
            f"💰 Narxi: {format_price(product['price'])}"
        ),
        reply_markup=get_product_keyboard()
    )

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    """Handle back button press."""
    categories = await db.get_categories()
    await callback.message.answer(
        "📋 Kategoriyalardan birini tanlang:",
        reply_markup=get_categories_keyboard(categories)
    )
    await callback.answer()

@router.callback_query(F.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery):
    """Handle admin add product button."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Bu tugma faqat adminlar uchun", show_alert=True)
        return
    
    await callback.message.answer(
        "➕ Yangi mahsulot qo'shish uchun quyidagi formatda xabar yuboring:\n\n"
        "[Rasm]\n"
        "Mahsulot nomi va tavsifi\n"
        "Narxi: XXX so'm\n"
        "#kategoriya"
    )
    await callback.answer()

@router.callback_query(F.data == "admin_edit_products")
async def admin_edit_products(callback: CallbackQuery):
    """Handle admin edit products button."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Bu tugma faqat adminlar uchun", show_alert=True)
        return
    
    categories = await db.get_categories()
    if not categories:
        await callback.answer("❌ Hozircha mahsulotlar yo'q", show_alert=True)
        return
    
    await callback.message.answer(
        "✏️ Tahrirlash uchun kategoriyani tanlang:",
        reply_markup=get_categories_keyboard(categories)
    )
    await callback.answer()

@router.callback_query(F.data == "admin_edit_info")
async def admin_edit_info(callback: CallbackQuery):
    """Handle admin edit info button."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Bu tugma faqat adminlar uchun", show_alert=True)
        return
    
    await callback.message.answer(
        "📝 Ma'lumotni tahrirlash uchun quyidagi formatda xabar yuboring:\n\n"
        "Ma'lumot matni\n\n"
        "Misol:\n"
        "ℹ️ ZetShop - bu online do'kon\n"
        "🛍 Bizda siz uchun eng sifatli va arzon mahsulotlar mavjud.\n"
        "📞 Aloqa: +998901234567\n"
        "📍 Manzil: Toshkent shahri\n"
        "📱 Telegram: @ZetShopUz"
    )
    await callback.answer()

async def process_channel_post(message: Message):
    """Process new channel post."""
    # Check if message is from our channel
    if message.chat.id != CHANNEL_ID:
        return
    
    # Get photo
    photo = message.photo[-1] if message.photo else None
    if not photo:
        logger.info("Skipping post without photo")
        return
    
    # Extract product info
    price, category, description = extract_product_info(message.caption or "")
    if not all([price, category]):
        logger.info("Skipping post without price or category")
        return
    
    # Save product to database
    await db.add_product(
        image_file_id=photo.file_id,
        description=description,
        price=price,
        category=category
    )
    logger.info(f"Added new product in category: {category}")

async def cleanup_task():
    """Periodic cleanup task."""
    await db.cleanup_old_products()

async def main():
    """Main function."""
    # Get bot token from env
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN not set in environment variables")
        return
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    try:
        # Initialize database
        await db.create_tables()
        
        # Setup scheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(cleanup_task, 'interval', hours=24)
        scheduler.start()
        
        # Include router
        dp.include_router(router)
        
        # Register channel post handler
        dp.channel_post.register(process_channel_post)
        
        # Start polling
        logger.info("Starting bot...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
