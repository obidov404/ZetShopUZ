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
from keyboards import get_categories_keyboard, get_product_keyboard
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

# Initialize database
db = Database()

# User states
user_states: Dict[int, Dict[str, Union[str, int]]] = {}

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    categories = await db.get_categories()
    
    if not categories:
        await message.answer(
            "🛍 Assalomu alaykum! ZetShop katalogiga xush kelibsiz!\n\n"
            "Hozircha katalogda mahsulotlar yo'q. "
            "Iltimos keyinroq qayta urinib ko'ring."
        )
        return
    
    await message.answer(
        "🛍 Assalomu alaykum! ZetShop katalogiga xush kelibsiz!\n\n"
        "Quyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_categories_keyboard(categories)
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
