import os
import sys
import logging
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_USER_ID', 0))

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not set")
    sys.exit(1)

if not ADMIN_ID:
    logger.error("ADMIN_USER_ID not set")
    sys.exit(1)

# Initialize router
router = Router(name="main_router")

# Keyboard generators
def get_main_keyboard():
    """Create main keyboard."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    catalog_button = KeyboardButton("🏪 Katalog")
    cart_button = KeyboardButton("🛒 Savatcha")
    orders_button = KeyboardButton("📋 Buyurtmalar")
    info_button = KeyboardButton("ℹ️ Ma'lumot")
    keyboard.add(catalog_button, cart_button)
    keyboard.add(orders_button, info_button)
    return keyboard

def get_admin_keyboard():
    """Create admin panel keyboard."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    products_button = KeyboardButton("📦 Mahsulotlarni boshqarish")
    categories_button = KeyboardButton("📁 Kategoriyalarni boshqarish")
    orders_button = KeyboardButton("📋 Buyurtmalarni ko'rish")
    exit_button = KeyboardButton("🔙 Chiqish")
    keyboard.add(products_button)
    keyboard.add(categories_button, orders_button)
    keyboard.add(exit_button)
    return keyboard

# Command handlers
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    await message.answer(
        "👋 Assalomu alaykum! ZetShop botiga xush kelibsiz!\n\n"
        "🛍 Bizning botda siz quyidagi imkoniyatlarga ega bo'lasiz:\n"
        "- Mahsulotlarni ko'rish va sotib olish\n"
        "- Savatchani boshqarish\n"
        "- Buyurtmalar tarixini ko'rish\n\n"
        "Boshlash uchun quyidagi tugmalardan foydalaning:",
        reply_markup=get_main_keyboard()
    )

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Handle /admin command."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ Kechirasiz, bu buyruq faqat adminlar uchun.")
        return
    
    await message.answer(
        "🔐 Admin panelga xush kelibsiz!\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_admin_keyboard()
    )

# Text message handlers
@router.message(F.text == "🏪 Katalog")
async def show_catalog(message: Message):
    await message.answer(
        "📦 Katalog bo'limi ishga tushirilmoqda..."
    )

@router.message(F.text == "🛒 Savatcha")
async def show_cart(message: Message):
    await message.answer(
        "🛒 Savatchangiz bo'sh."
    )

@router.message(F.text == "📋 Buyurtmalar")
async def show_orders(message: Message):
    await message.answer(
        "📋 Sizning buyurtmalaringiz yo'q."
    )

@router.message(F.text == "ℹ️ Ma'lumot")
async def show_info(message: Message):
    await message.answer(
        "ℹ️ Bot haqida ma'lumot:\n"
        "ZetShop - onlayn do'kon boti."
    )

# Admin panel handlers
@router.message(F.text == "📦 Mahsulotlarni boshqarish")
async def manage_products(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📦 Mahsulotlarni boshqarish bo'limi.")

@router.message(F.text == "📁 Kategoriyalarni boshqarish")
async def manage_categories(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📁 Kategoriyalarni boshqarish bo'limi.")

@router.message(F.text == "📋 Buyurtmalarni ko'rish")
async def manage_orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📋 Buyurtmalarni ko'rish bo'limi.")

@router.message(F.text == "🔙 Chiqish")
async def exit_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "✅ Asosiy menyuga qaytdingiz.",
        reply_markup=get_main_keyboard()
    )

async def main():
    """Main function."""
    # Initialize Bot and Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Include router
    dp.include_router(router)
    
    # Start polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
