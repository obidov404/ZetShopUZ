import os
import sys
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, CommandStart, Text, StateFilter
from aiogram.types import (Message, CallbackQuery,
                         ReplyKeyboardMarkup, KeyboardButton,
                         InlineKeyboardMarkup, InlineKeyboardButton,
                         ReplyKeyboardRemove, BotCommand)
from aiogram.methods import SetMyCommands
from aiogram.enums import ParseMode

from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get configuration from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = int(os.getenv('ADMIN_USER_ID'))

if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable not set")
    sys.exit(1)

if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set")
    sys.exit(1)

if not ADMIN_ID:
    logger.error("ADMIN_USER_ID environment variable not set")
    sys.exit(1)

# Database setup
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = scoped_session(sessionmaker(bind=engine))

# Initialize router
router = Router(name="main_router")

# States
class AdminState(StatesGroup):
    manage_products = State()
    add_product = State()
    edit_product = State()
    confirm_delete = State()
    add_category = State()
    edit_category = State()

class OrderState(StatesGroup):
    awaiting_phone = State()
    awaiting_address = State()
    confirm_order = State()

# Database Models
class ProductCategory(Base):
    """Category model for organizing products."""
    __tablename__ = 'product_category'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    products = relationship('Product', back_populates='category')
    
    def __repr__(self):
        return f'<ProductCategory {self.name}>'

class Product(Base):
    """Product model representing items for sale."""
    __tablename__ = 'product'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    image_url = Column(String(255), nullable=True)
    is_available = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey('product_category.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    category = relationship('ProductCategory', back_populates='products')
    order_items = relationship('OrderItem', back_populates='product')
    
    @property
    def formatted_price(self):
        """Return formatted price with currency."""
        return f"{self.price:,} UZS".replace(",", " ")

class Customer(Base):
    """Customer model for users who place orders."""
    __tablename__ = 'customer'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    orders = relationship('Order', back_populates='customer')

class Order(Base):
    """Order model for customer purchases."""
    __tablename__ = 'order'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    status = Column(String(20), default='pending')
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    customer = relationship('Customer', back_populates='orders')
    items = relationship('OrderItem', back_populates='order')
    
    @property
    def total(self):
        """Calculate total order price."""
        return sum(item.subtotal for item in self.items)

class OrderItem(Base):
    """Order item model for products in an order."""
    __tablename__ = 'order_item'
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('order.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('product.id'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    price = Column(Integer, nullable=False)
    
    order = relationship('Order', back_populates='items')
    product = relationship('Product', back_populates='order_items')
    
    @property
    def subtotal(self):
        """Calculate subtotal for this item."""
        return self.price * self.quantity

def init_db():
    """Initialize the database."""
    Base.metadata.create_all(engine)
    logger.info("Database tables created")

def get_session():
    """Get a new database session."""
    return Session()

# Command Handlers
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    session = get_session()
    
    # Create or get customer
    customer = session.query(Customer).filter_by(telegram_id=message.from_user.id).first()
    if not customer:
        customer = Customer(
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )
        session.add(customer)
        session.commit()
    
    # Welcome message
    await message.answer(
        "👋 Assalomu alaykum! ZetShop botiga xush kelibsiz!\n\n"
        "🛍 Bizning botda siz quyidagi imkoniyatlarga ega bo'lasiz:\n"
        "- Mahsulotlarni ko'rish va sotib olish\n"
        "- Savatchani boshqarish\n"
        "- Buyurtmalar tarixini ko'rish\n\n"
        "Boshlash uchun quyidagi tugmalardan foydalaning:",
        reply_markup=get_main_keyboard()
    )
    
    session.close()

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

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    help_text = (
        "🤖 ZetShop bot yordam:\n\n"
        "Asosiy buyruqlar:\n"
        "/start - Botni ishga tushirish\n"
        "/help - Ushbu yordam xabarini ko'rsatish\n"
        "/admin - Admin panel (faqat adminlar uchun)\n\n"
        "Qo'shimcha ma'lumot olish uchun admin bilan bog'laning."
    )
    await message.answer(help_text)

# Keyboard Generators
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

async def on_startup():
    """Startup tasks."""
    # Initialize database
    init_db()
    
    # Set bot commands
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="admin", description="Admin panel")
    ]
    
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    await bot(SetMyCommands(commands=commands))
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Log startup
    bot_info = await bot.get_me()
    logger.info(f"Bot @{bot_info.username} started!")
    logger.info(f"Bot ID: {bot_info.id}")
    logger.info(f"Admin ID: {ADMIN_ID}")

async def main():
    """Main function."""
    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    
    # Include router
    dp.include_router(router)
    
    # Register startup
    dp.startup.register(on_startup)
    
    # Start polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
