#!/usr/bin/env python3
"""
ZetShopUz Telegram Bot - Single File Version
This file contains all the essential components of the ZetShopUz e-commerce Telegram bot
for easy migration to GitHub and Render.com.

This single file combines:
- Database models and configuration
- Bot initialization and setup
- Message handlers for all bot functionality
- Keyboard generation
- State management
- Main execution code

For deployment to Render.com, you'll still need:
- render.yaml (for Blueprint deployment)
- requirements.txt
- .env file with BOT_TOKEN and DATABASE_URL

Author: Obidov Ulugbek
License: Proprietary
"""

import os
import sys
import json
import time
import logging
import asyncio
import requests
from datetime import datetime
from dotenv import load_dotenv

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

# Get bot token from environment variable
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable not set")
    sys.exit(1)

# Required packages
try:
    from aiogram import Bot, Dispatcher, Router, F, types
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.filters import Command, Text, StateFilter
    from aiogram.types import (Message, CallbackQuery,
                             ReplyKeyboardMarkup, KeyboardButton,
                             InlineKeyboardMarkup, InlineKeyboardButton,
                             ReplyKeyboardRemove, BotCommand)
    from aiogram.methods.set_my_commands import SetMyCommands
    
    from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey, DateTime, func
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, relationship, scoped_session
except ImportError:
    logger.error("Missing required packages. Install them with: pip install aiogram sqlalchemy psycopg2-binary python-dotenv")
    sys.exit(1)

# ====================================================================
# DATABASE CONFIGURATION & MODELS
# ====================================================================

# Get database URL from environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set")
    sys.exit(1)

# Set up SQLAlchemy
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = scoped_session(sessionmaker(bind=engine))

# Define models
class ProductCategory(Base):
    """Category model for organizing products."""
    __tablename__ = 'product_category'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    products = relationship('Product', back_populates='category')
    
    def __repr__(self):
        return f'<ProductCategory {self.name}>'
        
class Product(Base):
    """Product model representing a product for sale."""
    __tablename__ = 'product'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)  # Price in UZS (Uzbekistan Som)
    image_url = Column(String(255), nullable=True)
    is_available = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey('product_category.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    category = relationship('ProductCategory', back_populates='products')
    order_items = relationship('OrderItem', back_populates='product')
    cart_items = relationship('CartItem', back_populates='product')
    
    @property
    def formatted_price(self):
        """Return a formatted price with UZS currency code."""
        # Format with thousand separators and UZS currency code
        return f"{self.price:,} UZS".replace(",", " ")
    
    def __repr__(self):
        return f'<Product {self.name} - {self.price} UZS>'
        
class Customer(Base):
    """Customer model representing a Telegram user who has placed an order."""
    __tablename__ = 'customer'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    address = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    orders = relationship('Order', back_populates='customer')
    cart_items = relationship('CartItem', back_populates='customer', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Customer {self.name} (ID: {self.id})>'
        
class Order(Base):
    """Order model representing an order placed by a customer."""
    __tablename__ = 'order'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    status = Column(String(50), default="NEW")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    customer = relationship('Customer', back_populates='orders')
    items = relationship('OrderItem', back_populates='order', cascade="all, delete-orphan")
    
    @property
    def total(self):
        """Calculate total price for this order."""
        return sum(item.subtotal for item in self.items)
        
    def __repr__(self):
        return f'<Order {self.id}>'
        
class OrderItem(Base):
    """OrderItem model representing a product in an order."""
    __tablename__ = 'order_item'
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('order.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('product.id'), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    price = Column(Integer, nullable=False)  # Store the price at the time of order
    
    # Relationships
    order = relationship('Order', back_populates='items')
    product = relationship('Product', back_populates='order_items')
    
    @property
    def subtotal(self):
        """Calculate subtotal for this order item."""
        return self.price * self.quantity
    
    def __repr__(self):
        return f'<OrderItem {self.product_id} ({self.quantity})>'
        
class CartItem(Base):
    """CartItem model representing a product in a customer's cart."""
    __tablename__ = 'cart_item'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('product.id'), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    customer = relationship('Customer', back_populates='cart_items')
    product = relationship('Product', back_populates='cart_items')
    
    @property
    def subtotal(self):
        """Calculate subtotal for this cart item."""
        return self.product.price * self.quantity
    
    def __repr__(self):
        return f'<CartItem {self.product_id} ({self.quantity})>'

# Create tables if they don't exist
def init_db():
    Base.metadata.create_all(engine)
    logger.info("Database tables created")

# Create a session for database operations
def get_session():
    return Session()

# Sample data initialization function
def add_sample_data():
    session = get_session()
    
    # Check if we already have categories
    if session.query(ProductCategory).count() > 0:
        logger.info("Sample data already exists, skipping initialization")
        session.close()
        return
    
    try:
        # Add categories
        electronics = ProductCategory(
            name="Elektronika",
            description="Telefonlar, noutbuklar, televizorlar va boshqa elektronika mahsulotlari",
            image_url="https://i.imgur.com/JQJMcQb.jpeg"
        )
        
        appliances = ProductCategory(
            name="Maishiy texnika",
            description="Muzlatgichlar, kir yuvish mashinalari va boshqa maishiy texnikalar",
            image_url="https://i.imgur.com/hEZGV9V.jpeg"
        )
        
        session.add_all([electronics, appliances])
        session.commit()
        
        # Add products
        smartphone = Product(
            name="Xiaomi Redmi Note 10",
            description="6.43 dyumli AMOLED ekran, 48MP kamera, 5000mAh batareya",
            price=2500000,
            image_url="https://i.imgur.com/GJu2zNR.jpeg",
            is_available=True,
            category=electronics
        )
        
        laptop = Product(
            name="HP Laptop 15",
            description="Intel Core i5, 8GB RAM, 512GB SSD, Windows 10",
            price=6000000,
            image_url="https://i.imgur.com/QbYjQEK.jpeg",
            is_available=True,
            category=electronics
        )
        
        refrigerator = Product(
            name="Samsung Muzlatgich",
            description="Ikki eshikli, No Frost, 350 litr, A++ energiya tejamkorligi",
            price=7500000,
            image_url="https://i.imgur.com/0MMSuFV.jpeg",
            is_available=True,
            category=appliances
        )
        
        washing_machine = Product(
            name="Kir yuvish mashinasi",
            description="LG markali, 7kg yuklanish, 1200 ayl/min, A+++ class",
            price=4200000,
            image_url="https://i.imgur.com/QzfWcFc.jpeg",
            is_available=True,
            category=appliances
        )
        
        session.add_all([smartphone, laptop, refrigerator, washing_machine])
        session.commit()
        
        logger.info("Sample data added successfully")
    
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding sample data: {e}")
    
    finally:
        session.close()

# ====================================================================
# STATE DEFINITIONS
# ====================================================================

# Catalog browsing states
class CatalogState(StatesGroup):
    browse_categories = State()  # Browsing categories
    browse_products = State()  # Browsing products in a category
    view_product = State()  # Viewing a specific product
    add_to_cart = State()  # Adding product to cart with quantity

# Shopping cart states
class CartState(StatesGroup):
    view_cart = State()  # Viewing current cart
    edit_cart = State()  # Editing items in cart
    checkout = State()  # Proceeding to checkout

# Order form states
class OrderForm(StatesGroup):
    name = State()  # First state for ordering
    phone = State()  # Second state
    address = State()  # Third state
    confirm = State()  # Final confirmation state

# Admin states
class AdminState(StatesGroup):
    main_menu = State()  # Admin main menu
    manage_products = State()  # Product management menu
    select_product = State()  # Selecting product to edit/delete
    edit_product = State()  # Editing product details
    edit_name = State()  # Editing product name
    edit_description = State()  # Editing product description
    edit_price = State()  # Editing product price
    edit_image = State()  # Editing product image
    confirm_delete = State()  # Confirming product deletion

# ====================================================================
# KEYBOARD FUNCTIONS
# ====================================================================

def get_main_keyboard():
    """
    Creates the main keyboard with buttons:
    - Catalog (Katalog)
    - Cart (Savatcha)
    - Information (Ma'lumot)
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    catalog_button = KeyboardButton("🛍 Katalog")
    cart_button = KeyboardButton("🛒 Savatcha")
    info_button = KeyboardButton("ℹ️ Ma'lumot")
    keyboard.add(catalog_button)
    keyboard.add(cart_button, info_button)
    return keyboard

def get_phone_keyboard():
    """
    Creates a keyboard with a button to share phone number
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    phone_button = KeyboardButton("📱 Telefon raqamimni jo'natish", request_contact=True)
    keyboard.add(phone_button)
    return keyboard

def get_back_keyboard():
    """
    Creates a keyboard with just a back button
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    back_button = KeyboardButton("🔙 Ortga")
    keyboard.add(back_button)
    return keyboard

def get_cancel_keyboard():
    """
    Creates a keyboard with just a cancel button
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    cancel_button = KeyboardButton("❌ Bekor qilish")
    keyboard.add(cancel_button)
    return keyboard

def get_categories_keyboard():
    """
    Creates an inline keyboard with all available categories
    """
    markup = InlineKeyboardMarkup(row_width=1)
    
    session = get_session()
    categories = session.query(ProductCategory).all()
    
    for category in categories:
        button = InlineKeyboardButton(
            text=category.name,
            callback_data=f"category_{category.id}"
        )
        markup.add(button)
    
    session.close()
    return markup

def get_products_keyboard(category_id):
    """
    Creates an inline keyboard with products from a specific category
    """
    markup = InlineKeyboardMarkup(row_width=1)
    
    session = get_session()
    products = session.query(Product).filter_by(
        category_id=category_id, 
        is_available=True
    ).all()
    
    for product in products:
        button = InlineKeyboardButton(
            text=f"{product.name} - {product.formatted_price}",
            callback_data=f"product_{product.id}"
        )
        markup.add(button)
    
    # Add back button
    back_button = InlineKeyboardButton(
        text="⬅️ Kategoriyalarga qaytish",
        callback_data="back_to_categories"
    )
    markup.add(back_button)
    
    session.close()
    return markup

def get_product_detail_keyboard(product_id):
    """
    Creates an inline keyboard for a product detail view with 
    add to cart button and back button
    """
    markup = InlineKeyboardMarkup(row_width=1)
    add_to_cart_button = InlineKeyboardButton(
        text="🛒 Savatchaga qo'shish",
        callback_data=f"add_to_cart_{product_id}"
    )
    
    session = get_session()
    product = session.query(Product).get(product_id)
    category_id = product.category_id
    session.close()
    
    back_button = InlineKeyboardButton(
        text="⬅️ Mahsulotlarga qaytish",
        callback_data=f"back_to_products_{category_id}"
    )
    
    markup.add(add_to_cart_button)
    markup.add(back_button)
    return markup

def get_cart_keyboard():
    """
    Creates a keyboard for cart management
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    order_button = KeyboardButton("✅ Buyurtma berish")
    clear_button = KeyboardButton("🗑 Savatchani tozalash")
    back_button = KeyboardButton("🔙 Ortga")
    keyboard.add(order_button)
    keyboard.add(clear_button, back_button)
    return keyboard

def get_confirm_order_keyboard():
    """
    Creates a keyboard for confirming or canceling an order
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    confirm_button = KeyboardButton("✅ Buyurtmani tasdiqlash")
    cancel_button = KeyboardButton("❌ Bekor qilish")
    keyboard.add(confirm_button)
    keyboard.add(cancel_button)
    return keyboard

def get_quantity_keyboard():
    """
    Creates an inline keyboard for selecting quantity
    """
    markup = InlineKeyboardMarkup(row_width=5)
    buttons = []
    
    # Add buttons for 1-5
    for i in range(1, 6):
        button = InlineKeyboardButton(
            text=str(i),
            callback_data=f"qty_{i}"
        )
        buttons.append(button)
    
    # Add buttons for 6-10
    more_buttons = []
    for i in range(6, 11):
        button = InlineKeyboardButton(
            text=str(i),
            callback_data=f"qty_{i}"
        )
        more_buttons.append(button)
    
    markup.row(*buttons)
    markup.row(*more_buttons)
    
    # Add cancel button
    cancel_button = InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="cancel_add_to_cart"
    )
    markup.add(cancel_button)
    
    return markup

def get_admin_keyboard():
    """
    Creates admin panel keyboard
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    products_button = KeyboardButton("📦 Mahsulotlarni boshqarish")
    categories_button = KeyboardButton("📁 Kategoriyalarni boshqarish")
    orders_button = KeyboardButton("📋 Buyurtmalarni ko'rish")
    exit_button = KeyboardButton("🔙 Chiqish")
    keyboard.add(products_button)
    keyboard.add(categories_button, orders_button)
    keyboard.add(exit_button)
    return keyboard

def get_admin_product_keyboard(product_id):
    """
    Creates inline keyboard for admin product management
    """
    markup = InlineKeyboardMarkup(row_width=2)
    # Edit buttons
    edit_name_button = InlineKeyboardButton(
        text="✏️ Nomni tahrirlash", 
        callback_data=f"admin_edit_name_{product_id}"
    )
    edit_desc_button = InlineKeyboardButton(
        text="✏️ Tavsifni tahrirlash", 
        callback_data=f"admin_edit_desc_{product_id}"
    )
    edit_price_button = InlineKeyboardButton(
        text="✏️ Narxni tahrirlash", 
        callback_data=f"admin_edit_price_{product_id}"
    )
    edit_image_button = InlineKeyboardButton(
        text="✏️ Rasmni tahrirlash", 
        callback_data=f"admin_edit_image_{product_id}"
    )
    # Delete button
    delete_button = InlineKeyboardButton(
        text="🗑️ O'chirish", 
        callback_data=f"admin_delete_{product_id}"
    )
    # Back button
    back_button = InlineKeyboardButton(
        text="⬅️ Ortga", 
        callback_data="admin_back_to_products"
    )
    # Add buttons to markup
    markup.add(edit_name_button, edit_desc_button)
    markup.add(edit_price_button, edit_image_button)
    markup.add(delete_button)
    markup.add(back_button)
    return markup

def get_admin_confirm_delete_keyboard(product_id):
    """
    Creates inline keyboard for confirming product deletion
    """
    markup = InlineKeyboardMarkup(row_width=2)
    confirm_button = InlineKeyboardButton(
        text="✅ Ha, o'chirish", 
        callback_data=f"admin_confirm_delete_{product_id}"
    )
    cancel_button = InlineKeyboardButton(
        text="❌ Yo'q, bekor qilish", 
        callback_data=f"admin_cancel_delete_{product_id}"
    )
    markup.add(confirm_button, cancel_button)
    return markup

def get_admin_products_keyboard():
    """
    Creates inline keyboard with all products for admin
    """
    markup = InlineKeyboardMarkup(row_width=1)
    
    session = get_session()
    products = session.query(Product).all()
    
    for product in products:
        button = InlineKeyboardButton(
            text=f"{product.name} - {product.formatted_price}",
            callback_data=f"admin_product_{product.id}"
        )
        markup.add(button)
    
    # Add back button
    back_button = InlineKeyboardButton(
        text="⬅️ Ortga", 
        callback_data="admin_back_to_menu"
    )
    markup.add(back_button)
    
    session.close()
    return markup

# ====================================================================
# BOT INITIALIZATION
# ====================================================================

# Get bot token from environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable not set")
    sys.exit(1)

# Get admin ID from environment variables (default is 5610950813 for @Obidov_Ulugbek)
ADMIN_ID = int(os.environ.get("ADMIN_ID", "5610950813"))

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ====================================================================
# HANDLERS
# ====================================================================

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """
    Handles the /start command - sends welcome message and shows main keyboard
    """
    await message.answer(
        "🇺🇿 Assalomu alaykum! ZetShopUz botiga xush kelibsiz! "
        "Iltimos, quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_keyboard()
    )

@dp.message_handler(Text(text="ℹ️ Ma'lumot"))
async def show_info(message: types.Message):
    """
    Handles info button press - shows information about ZetShopUz
    """
    info_text = (
        "🏢 <b>ZetShopUz</b> - bu zamonaviy elektron do'kon!\n\n"
        "🛒 Bizda turli xil mahsulotlarni qulaylik bilan xarid qilishingiz mumkin.\n\n"
        "✅ <b>Afzalliklarimiz:</b>\n"
        "- Qulay o'zbek tilidagi interfeys\n"
        "- Xavfsiz va tezkor yetkazib berish\n"
        "- Sifatli mahsulotlar\n"
        "- 24/7 mijozlar bilan aloqa\n\n"
        "📞 <b>Aloqa uchun:</b>\n"
        "- Telegram: @Obidov_Ulugbek\n"
        "- Telefon: +99899*******\n"
    )
    await message.answer(info_text, parse_mode="HTML")

@dp.message_handler(Text(text="🛍 Katalog"))
async def show_catalog(message: types.Message):
    """
    Shows the product catalog categories
    """
    await state.set_state(CatalogState.browse_categories)
    await message.answer(
        "Quyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_categories_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data.startswith('category_'), state=CatalogState.browse_categories)
async def process_category_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Process the selected category and show products
    """
    await callback_query.answer()
    
    # Extract category_id from callback data
    category_id = int(callback_query.data.split('_')[1])
    
    # Store the selected category id in state
    async with state.proxy() as data:
        data['category_id'] = category_id
    
    # Get category name
    session = get_session()
    category = session.query(ProductCategory).get(category_id)
    category_name = category.name if category else "Kategoriya"
    session.close()
    
    # Update state
    await state.set_state(CatalogState.browse_products)
    
    # Show products in the selected category
    await callback_query.message.edit_text(
        f"📂 {category_name} kategoriyasidagi mahsulotlar:",
        reply_markup=get_products_keyboard(category_id)
    )

@dp.callback_query_handler(lambda c: c.data == 'back_to_categories', state=CatalogState.browse_products)
async def go_back_to_categories(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Go back to categories list
    """
    await callback_query.answer()
    await state.set_state(CatalogState.browse_categories)
    
    await callback_query.message.edit_text(
        "Quyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_categories_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data.startswith('product_'), state=CatalogState.browse_products)
async def process_product_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Show details for selected product
    """
    await callback_query.answer()
    
    # Extract product_id from callback data
    product_id = int(callback_query.data.split('_')[1])
    
    # Store the selected product id in state
    async with state.proxy() as data:
        data['product_id'] = product_id
    
    # Get product details
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        # Update state
        await state.set_state(CatalogState.view_product)
        
        # Create product detail message
        product_text = (
            f"📦 <b>{product.name}</b>\n\n"
            f"📝 <b>Tavsif:</b> {product.description}\n\n"
            f"💰 <b>Narxi:</b> {product.formatted_price}"
        )
        
        # Send product image if available, otherwise just text
        if product.image_url:
            await callback_query.message.delete()  # Delete previous message
            await bot.send_photo(
                callback_query.from_user.id,
                photo=product.image_url,
                caption=product_text,
                parse_mode="HTML",
                reply_markup=get_product_detail_keyboard(product_id)
            )
        else:
            await callback_query.message.edit_text(
                product_text,
                parse_mode="HTML",
                reply_markup=get_product_detail_keyboard(product_id)
            )
    else:
        await callback_query.message.edit_text(
            "⚠️ Kechirasiz, mahsulot topilmadi.",
            reply_markup=get_categories_keyboard()
        )
        await state.set_state(CatalogState.browse_categories)
    
    session.close()

@dp.callback_query_handler(lambda c: c.data.startswith('back_to_products_'), state=CatalogState.view_product)
async def go_back_to_products(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Go back to products in the current category
    """
    await callback_query.answer()
    
    # Extract category_id from callback data
    category_id = int(callback_query.data.split('_')[3])
    
    # Store the selected category id in state
    async with state.proxy() as data:
        data['category_id'] = category_id
    
    # Get category name
    session = get_session()
    category = session.query(ProductCategory).get(category_id)
    category_name = category.name if category else "Kategoriya"
    session.close()
    
    # Update state
    await state.set_state(CatalogState.browse_products)
    
    # Show products in the selected category
    await callback_query.message.delete()  # Delete photo message if any
    await bot.send_message(
        callback_query.from_user.id,
        f"📂 {category_name} kategoriyasidagi mahsulotlar:",
        reply_markup=get_products_keyboard(category_id)
    )

@dp.callback_query_handler(lambda c: c.data.startswith('add_to_cart_'), state=CatalogState.view_product)
async def add_to_cart(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Start the process of adding a product to cart
    """
    await callback_query.answer()
    
    # Extract product_id from callback data
    product_id = int(callback_query.data.split('_')[3])
    
    # Store the selected product id in state
    async with state.proxy() as data:
        data['product_id'] = product_id
    
    # Get product details
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        # Update state
        await CatalogState.add_to_cart.set()
        
        # Ask for quantity
        await callback_query.message.edit_caption(
            f"📦 <b>{product.name}</b>\n\n"
            f"💰 <b>Narxi:</b> {product.formatted_price}\n\n"
            f"🔢 Iltimos, miqdorni tanlang:",
            parse_mode="HTML",
            reply_markup=get_quantity_keyboard()
        )
    else:
        await callback_query.message.edit_caption(
            "⚠️ Kechirasiz, mahsulot topilmadi.",
            reply_markup=None
        )
        await state.set_state(CatalogState.browse_categories)
    
    session.close()

@dp.callback_query_handler(lambda c: c.data.startswith('qty_'), state=CatalogState.add_to_cart)
async def process_quantity(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Process the selected quantity and add product to cart
    """
    await callback_query.answer()
    
    # Extract quantity from callback data
    quantity = int(callback_query.data.split('_')[1])
    
    # Get state data
    async with state.proxy() as data:
        product_id = data['product_id']
    
    # Get product details and add to cart
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        # Check if customer exists or create new one
        customer = session.query(Customer).filter_by(
            telegram_id=callback_query.from_user.id
        ).first()
        
        if not customer:
            # For cart, we'll create a temporary customer that will be completed during checkout
            customer = Customer(
                telegram_id=callback_query.from_user.id,
                name=callback_query.from_user.full_name or "Unknown",
                phone="Not provided",
                address="Not provided"
            )
            session.add(customer)
            session.commit()
        
        # Check if product already in cart
        cart_item = session.query(CartItem).filter_by(
            customer_id=customer.id,
            product_id=product_id
        ).first()
        
        if cart_item:
            # Update quantity if already in cart
            cart_item.quantity += quantity
        else:
            # Add new cart item
            cart_item = CartItem(
                customer_id=customer.id,
                product_id=product_id,
                quantity=quantity
            )
            session.add(cart_item)
        
        session.commit()
        
        # Notify success
        success_text = (
            f"✅ <b>{product.name}</b> savatchaga qo'shildi!\n"
            f"📦 Miqdor: {quantity} dona\n\n"
            f"🛒 Savatchani ko'rish uchun \"Savatcha\" tugmasini bosing."
        )
        
        await callback_query.message.delete()  # Delete previous message
        await bot.send_message(
            callback_query.from_user.id,
            success_text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        
        # Reset state
        await state.clear()
        
    else:
        await callback_query.message.edit_caption(
            "⚠️ Kechirasiz, mahsulot topilmadi.",
            reply_markup=None
        )
        await state.clear()
    
    session.close()

@dp.callback_query_handler(lambda c: c.data == 'cancel_add_to_cart', state=CatalogState.add_to_cart)
async def cancel_add_to_cart(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Cancel adding product to cart
    """
    await callback_query.answer()
    
    # Get state data
    async with state.proxy() as data:
        product_id = data['product_id']
    
    # Get product details
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        # Update state back to view product
        await state.set_state(CatalogState.view_product)
        
        # Show product details again
        product_text = (
            f"📦 <b>{product.name}</b>\n\n"
            f"📝 <b>Tavsif:</b> {product.description}\n\n"
            f"💰 <b>Narxi:</b> {product.formatted_price}"
        )
        
        await callback_query.message.edit_caption(
            product_text,
            parse_mode="HTML",
            reply_markup=get_product_detail_keyboard(product_id)
        )
    else:
        await callback_query.message.edit_caption(
            "⚠️ Kechirasiz, mahsulot topilmadi.",
            reply_markup=None
        )
        await state.clear()
    
    session.close()

@dp.message_handler(Text(equals="🛒 Savatcha"))
async def show_cart(message: types.Message, state: FSMContext):
    """
    Show the user's shopping cart
    """
    session = get_session()
    
    # Find customer
    customer = session.query(Customer).filter_by(
        telegram_id=message.from_user.id
    ).first()
    
    if not customer or not customer.cart_items:
        await message.answer(
            "🛒 Sizning savatchangiz bo'sh. "
            "Mahsulotlarni ko'rish uchun \"Katalog\" tugmasini bosing.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        session.close()
        return
    
    # Set state
    await state.set_state(CartState.view_cart)
    
    # Calculate total
    total = sum(item.subtotal for item in customer.cart_items)
    
    # Create cart message
    cart_text = "🛒 <b>Sizning savatchangiz:</b>\n\n"
    
    for item in customer.cart_items:
        product = item.product
        cart_text += (
            f"📦 <b>{product.name}</b>\n"
            f"💰 {product.formatted_price} x {item.quantity} = "
            f"{item.subtotal:,} UZS".replace(",", " ") + "\n\n"
        )
    
    cart_text += f"💵 <b>Jami:</b> {total:,} UZS".replace(",", " ")
    
    await message.answer(
        cart_text,
        parse_mode="HTML",
        reply_markup=get_cart_keyboard()
    )
    
    session.close()

@router.message(Text(text="🗑 Savatchani tozalash"), StateFilter(CartState.view_cart))
async def clear_cart(message: Message, state: FSMContext):
    """
    Clear the user's shopping cart
    """
    session = get_session()
    
    # Find customer
    customer = session.query(Customer).filter_by(
        telegram_id=message.from_user.id
    ).first()
    
    if customer:
        # Delete all cart items
        for item in customer.cart_items:
            session.delete(item)
        session.commit()
    
    session.close()
    
    await message.answer(
        "✅ Savatcha tozalandi!",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()

@router.message(Text(text="🔙 Ortga"), StateFilter(CartState.view_cart))
async def back_to_main(message: Message, state: FSMContext):
    """
    Go back to main menu from any state
    """
    await message.answer(
        "Asosiy menyu:",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()

@router.message(Text(text="✅ Buyurtma berish"), StateFilter(CartState.view_cart))
async def start_checkout(message: Message, state: FSMContext):
    """
    Start the checkout process from the cart
    """
    # Update state to start the order form
    await state.set_state(OrderForm.name)
    
    await message.answer(
        "🧾 <b>Buyurtma berish</b>\n\n"
        "Iltimos, to'liq ismingizni kiriting:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@router.message(F.text != "❌ Bekor qilish", StateFilter(OrderForm.name))
async def process_name(message: Message, state: FSMContext):
    """
    Process user's name during checkout
    """
    # Save name to state
    async with state.proxy() as data:
        data['name'] = message.text
    
    # Move to next state
    await state.set_state(OrderForm.phone)
    
    await message.answer(
        "📱 Iltimos, telefon raqamingizni kiriting yoki pastdagi tugmani bosing:",
        reply_markup=get_phone_keyboard()
    )

@router.message(F.text != "❌ Bekor qilish", StateFilter(OrderForm.phone))
async def process_phone(message: Message, state: FSMContext):
    """
    Process user's phone number (text input) during checkout
    """
    # Validate phone number (basic check)
    phone = message.text.strip()
    
    if len(phone) < 9:
        await message.answer(
            "⚠️ Iltimos, to'g'ri telefon raqamini kiriting:",
            reply_markup=get_phone_keyboard()
        )
        return
    
    # Save phone to state
    async with state.proxy() as data:
        data['phone'] = phone
    
    # Move to next state
    await state.set_state(OrderForm.address)
    
    await message.answer(
        "🏠 Iltimos, manzilni kiriting (shahar, ko'cha, uy):",
        reply_markup=get_cancel_keyboard()
    )

@dp.message_handler(content_types=ContentType.CONTACT, state=OrderForm.phone)
async def process_phone_contact(message: types.Message, state: FSMContext):
    """
    Process user's phone number (shared via button) during checkout
    """
    # Save phone from contact
    async with state.proxy() as data:
        data['phone'] = message.contact.phone_number
    
    # Move to next state
    await state.set_state(OrderForm.address)
    
    await message.answer(
        "🏠 Iltimos, manzilni kiriting (shahar, ko'cha, uy):",
        reply_markup=get_cancel_keyboard()
    )

@dp.message_handler(lambda message: message.text != "❌ Bekor qilish", state=OrderForm.address)
async def process_address(message: types.Message, state: FSMContext):
    """
    Process user's address and show order confirmation
    """
    # Save address to state
    async with state.proxy() as data:
        data['address'] = message.text
    
    # Move to confirmation state
    await state.set_state(OrderForm.confirm)
    
    # Get cart items
    session = get_session()
    customer = session.query(Customer).filter_by(
        telegram_id=message.from_user.id
    ).first()
    
    if not customer or not customer.cart_items:
        await message.answer(
            "⚠️ Savatchada mahsulotlar yo'q!",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        session.close()
        return
    
    # Calculate total
    total = sum(item.subtotal for item in customer.cart_items)
    
    # Create order summary message
    order_text = "🧾 <b>Buyurtma ma'lumotlari:</b>\n\n"
    
    # Add personal info
    async with state.proxy() as data:
        order_text += (
            f"👤 <b>Ism:</b> {data['name']}\n"
            f"📱 <b>Telefon:</b> {data['phone']}\n"
            f"🏠 <b>Manzil:</b> {data['address']}\n\n"
        )
    
    # Add cart items
    order_text += "<b>Buyurtma tarkibi:</b>\n\n"
    
    for item in customer.cart_items:
        product = item.product
        order_text += (
            f"📦 {product.name}\n"
            f"💰 {product.formatted_price} x {item.quantity} = "
            f"{item.subtotal:,} UZS".replace(",", " ") + "\n\n"
        )
    
    order_text += f"💵 <b>Jami summa:</b> {total:,} UZS".replace(",", " ")
    
    await message.answer(
        order_text + "\n\n"
        "Iltimos, buyurtmani tasdiqlang:",
        parse_mode="HTML",
        reply_markup=get_confirm_order_keyboard()
    )
    
    session.close()

@dp.message_handler(Text(equals="✅ Buyurtmani tasdiqlash"), state=OrderForm.confirm)
async def confirm_order(message: types.Message, state: FSMContext):
    """
    Confirm the order and save to database
    """
    session = get_session()
    
    # Find customer
    customer = session.query(Customer).filter_by(
        telegram_id=message.from_user.id
    ).first()
    
    if not customer or not customer.cart_items:
        await message.answer(
            "⚠️ Savatchada mahsulotlar yo'q!",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        session.close()
        return
    
    try:
        # Update customer info
        async with state.proxy() as data:
            customer.name = data['name']
            customer.phone = data['phone']
            customer.address = data['address']
        
        # Create new order
        new_order = Order(
            customer_id=customer.id,
            status="NEW",
            notes="Telegram bot orqali buyurtma"
        )
        session.add(new_order)
        session.flush()  # Get the order ID
        
        # Add order items
        for cart_item in customer.cart_items:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=cart_item.product_id,
                quantity=cart_item.quantity,
                price=cart_item.product.price  # Save current price
            )
            session.add(order_item)
        
        # Clear cart
        for cart_item in customer.cart_items:
            session.delete(cart_item)
        
        # Commit changes
        session.commit()
        
        # Send success message to customer
        await message.answer(
            "✅ Buyurtmangiz qabul qilindi!\n\n"
            f"📋 Buyurtma raqami: #{new_order.id}\n\n"
            "🕒 Tez orada operatorimiz siz bilan bog'lanadi.\n"
            "Savolingiz bo'lsa, @Obidov_Ulugbek ga murojaat qiling.",
            reply_markup=get_main_keyboard()
        )
        
        # Send notification to admin
        admin_message = (
            "🔔 <b>Yangi buyurtma!</b>\n\n"
            f"📋 <b>Buyurtma raqami:</b> #{new_order.id}\n"
            f"📅 <b>Sana:</b> {new_order.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"👤 <b>Mijoz:</b> {customer.name}\n"
            f"📱 <b>Telefon:</b> {customer.phone}\n"
            f"🏠 <b>Manzil:</b> {customer.address}\n\n"
            f"💵 <b>Jami summa:</b> {new_order.total:,} UZS".replace(",", " ")
        )
        
        # Add order items to admin message
        admin_message += "\n\n<b>Buyurtma tarkibi:</b>\n"
        for item in new_order.items:
            admin_message += (
                f"- {item.product.name} x {item.quantity} = "
                f"{item.subtotal:,} UZS\n".replace(",", " ")
            )
        
        await bot.send_message(
            ADMIN_ID, 
            admin_message,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        await message.answer(
            "⚠️ Buyurtma yaratishda xatolik yuz berdi. "
            "Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning.",
            reply_markup=get_main_keyboard()
        )
    
    finally:
        session.close()
        await state.clear()

@router.message(Text(text="❌ Bekor qilish"), StateFilter(OrderForm.name, OrderForm.phone, OrderForm.address, OrderForm.confirm))
async def cancel_order(message: Message, state: FSMContext):
    """
    Cancel the order process
    """
    await message.answer(
        "❌ Buyurtma bekor qilindi.",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()

# Admin handlers
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    """
    Show admin panel if the user is an admin
    """
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Kechirasiz, sizda administrator huquqlari yo'q.")
        return
    
    await state.set_state(AdminState.main_menu)
    
    await message.answer(
        "👨‍💼 <b>Administrator paneli</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@dp.message_handler(Text(text="📦 Mahsulotlarni boshqarish"), state=AdminState.main_menu)
async def admin_manage_products(message: types.Message, state: FSMContext):
    """
    Show product management menu for admin
    """
    await state.set_state(AdminState.manage_products)
    
    await message.answer(
        "📦 <b>Mahsulotlarni boshqarish</b>\n\n"
        "Quyidagi mahsulotlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_products_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data == 'admin_back_to_menu', state=AdminState.manage_products)
async def admin_back_to_menu(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Return to admin main menu
    """
    await callback_query.answer()
    await state.set_state(AdminState.main_menu)
    
    await callback_query.message.delete()
    await bot.send_message(
        callback_query.from_user.id,
        "👨‍💼 <b>Administrator paneli</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@dp.message_handler(Text(text="🔙 Chiqish"), state=AdminState.main_menu)
async def admin_exit(message: types.Message, state: FSMContext):
    """
    Exit admin panel
    """
    await message.answer(
        "✅ Administrator panelidan chiqildi.",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()

@router.callback_query(F.data.startswith('admin_product_'), StateFilter(AdminState.manage_products))
async def admin_select_product(callback_query: CallbackQuery, state: FSMContext):
    """
    Show product details for admin with edit/delete options
    """
    await callback_query.answer()
    
    # Extract product_id from callback data
    product_id = int(callback_query.data.split('_')[2])
    
    # Store the selected product id in state
    async with state.proxy() as data:
        data['product_id'] = product_id
    
    # Get product details
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        # Update state
        await state.set_state(AdminState.edit_product)
        
        # Create product detail message
        product_text = (
            f"📦 <b>{product.name}</b>\n\n"
            f"📝 <b>Tavsif:</b> {product.description}\n\n"
            f"💰 <b>Narxi:</b> {product.formatted_price}\n\n"
            f"🔗 <b>Rasm URL:</b> {product.image_url or 'Mavjud emas'}\n\n"
            f"📂 <b>Kategoriya:</b> {product.category.name}\n\n"
            f"✅ <b>Mavjud:</b> {'Ha' if product.is_available else 'Yo`q'}"
        )
        
        # Send product image if available, otherwise just text
        if product.image_url:
            await callback_query.message.delete()  # Delete previous message
            await bot.send_photo(
                callback_query.from_user.id,
                photo=product.image_url,
                caption=product_text,
                parse_mode="HTML",
                reply_markup=get_admin_product_keyboard(product_id)
            )
        else:
            await callback_query.message.edit_text(
                product_text,
                parse_mode="HTML",
                reply_markup=get_admin_product_keyboard(product_id)
            )
    else:
        await callback_query.message.edit_text(
            "⚠️ Kechirasiz, mahsulot topilmadi.",
            reply_markup=get_admin_products_keyboard()
        )
        await state.set_state(AdminState.manage_products)
    
    session.close()

@dp.callback_query_handler(lambda c: c.data == 'admin_back_to_products', state=AdminState.edit_product)
async def admin_back_to_products(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Go back to products list in admin panel
    """
    await callback_query.answer()
    await state.set_state(AdminState.manage_products)
    
    await callback_query.message.delete()  # Delete current message (could be an image)
    await bot.send_message(
        callback_query.from_user.id,
        "📦 <b>Mahsulotlarni boshqarish</b>\n\n"
        "Quyidagi mahsulotlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_products_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_edit_name_'), state=AdminState.edit_product)
async def admin_edit_name(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Start editing product name
    """
    await callback_query.answer()
    
    # Store product ID
    product_id = int(callback_query.data.split('_')[3])
    async with state.proxy() as data:
        data['product_id'] = product_id
    
    # Change state
    await AdminState.edit_name.set()
    
    await callback_query.message.delete()  # Delete current message
    await bot.send_message(
        callback_query.from_user.id,
        "✏️ Mahsulot uchun yangi nomni kiriting:",
        reply_markup=get_cancel_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_edit_desc_'), state=AdminState.edit_product)
async def admin_edit_description(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Start editing product description
    """
    await callback_query.answer()
    
    # Store product ID
    product_id = int(callback_query.data.split('_')[3])
    async with state.proxy() as data:
        data['product_id'] = product_id
    
    # Change state
    await AdminState.edit_description.set()
    
    await callback_query.message.delete()  # Delete current message
    await bot.send_message(
        callback_query.from_user.id,
        "✏️ Mahsulot uchun yangi tavsifni kiriting:",
        reply_markup=get_cancel_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_edit_price_'), state=AdminState.edit_product)
async def admin_edit_price(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Start editing product price
    """
    await callback_query.answer()
    
    # Store product ID
    product_id = int(callback_query.data.split('_')[3])
    async with state.proxy() as data:
        data['product_id'] = product_id
    
    # Change state
    await AdminState.edit_price.set()
    
    await callback_query.message.delete()  # Delete current message
    await bot.send_message(
        callback_query.from_user.id,
        "✏️ Mahsulot uchun yangi narxni kiriting (faqat raqam, UZS):",
        reply_markup=get_cancel_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_edit_image_'), state=AdminState.edit_product)
async def admin_edit_image(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Start editing product image URL
    """
    await callback_query.answer()
    
    # Store product ID
    product_id = int(callback_query.data.split('_')[3])
    async with state.proxy() as data:
        data['product_id'] = product_id
    
    # Change state
    await AdminState.edit_image.set()
    
    await callback_query.message.delete()  # Delete current message
    await bot.send_message(
        callback_query.from_user.id,
        "✏️ Mahsulot uchun yangi rasm URL manzilini kiriting:",
        reply_markup=get_cancel_keyboard()
    )

@dp.message_handler(lambda message: message.text != "❌ Bekor qilish", state=AdminState.edit_name)
async def admin_process_edit_name(message: types.Message, state: FSMContext):
    """
    Process the new product name
    """
    # Get product ID from state
    async with state.proxy() as data:
        product_id = data['product_id']
    
    # Update product name
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        old_name = product.name
        product.name = message.text
        session.commit()
        
        await message.answer(
            f"✅ Mahsulot nomi yangilandi!\n\n"
            f"⬅️ Eski: {old_name}\n"
            f"➡️ Yangi: {product.name}"
        )
    else:
        await message.answer("⚠️ Kechirasiz, mahsulot topilmadi.")
    
    session.close()
    
    # Return to product editing
    await state.set_state(AdminState.manage_products)
    await message.answer(
        "📦 <b>Mahsulotlarni boshqarish</b>\n\n"
        "Quyidagi mahsulotlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_products_keyboard()
    )

@dp.message_handler(lambda message: message.text != "❌ Bekor qilish", state=AdminState.edit_description)
async def admin_process_edit_description(message: types.Message, state: FSMContext):
    """
    Process the new product description
    """
    # Get product ID from state
    async with state.proxy() as data:
        product_id = data['product_id']
    
    # Update product description
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        product.description = message.text
        session.commit()
        
        await message.answer(
            f"✅ Mahsulot tavsifi yangilandi!"
        )
    else:
        await message.answer("⚠️ Kechirasiz, mahsulot topilmadi.")
    
    session.close()
    
    # Return to product editing
    await state.set_state(AdminState.manage_products)
    await message.answer(
        "📦 <b>Mahsulotlarni boshqarish</b>\n\n"
        "Quyidagi mahsulotlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_products_keyboard()
    )

@dp.message_handler(lambda message: message.text != "❌ Bekor qilish", state=AdminState.edit_price)
async def admin_process_edit_price(message: types.Message, state: FSMContext):
    """
    Process the new product price
    """
    # Validate price
    try:
        new_price = int(message.text.replace(" ", ""))
        if new_price <= 0:
            raise ValueError("Price must be positive")
    except ValueError:
        await message.answer(
            "⚠️ Iltimos, to'g'ri narxni kiriting (faqat raqam, UZS):"
        )
        return
    
    # Get product ID from state
    async with state.proxy() as data:
        product_id = data['product_id']
    
    # Update product price
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        old_price = product.price
        product.price = new_price
        session.commit()
        
        await message.answer(
            f"✅ Mahsulot narxi yangilandi!\n\n"
            f"⬅️ Eski: {old_price:,} UZS\n".replace(",", " ") +
            f"➡️ Yangi: {new_price:,} UZS".replace(",", " ")
        )
    else:
        await message.answer("⚠️ Kechirasiz, mahsulot topilmadi.")
    
    session.close()
    
    # Return to product editing
    await state.set_state(AdminState.manage_products)
    await message.answer(
        "📦 <b>Mahsulotlarni boshqarish</b>\n\n"
        "Quyidagi mahsulotlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_products_keyboard()
    )

@dp.message_handler(lambda message: message.text != "❌ Bekor qilish", state=AdminState.edit_image)
async def admin_process_edit_image(message: types.Message, state: FSMContext):
    """
    Process the new product image URL
    """
    # Get product ID from state
    async with state.proxy() as data:
        product_id = data['product_id']
    
    # Update product image URL
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        product.image_url = message.text
        session.commit()
        
        await message.answer(
            f"✅ Mahsulot rasmi yangilandi!"
        )
        
        # Try to send the image to verify it
        try:
            await bot.send_photo(
                message.from_user.id,
                photo=product.image_url,
                caption=f"📦 <b>{product.name}</b> - yangi rasm",
                parse_mode="HTML"
            )
        except Exception as e:
            await message.answer(
                f"⚠️ Rasm yuklashda xatolik: {str(e)}\n"
                "URL to'g'ri ekanligini tekshiring."
            )
    else:
        await message.answer("⚠️ Kechirasiz, mahsulot topilmadi.")
    
    session.close()
    
    # Return to product editing
    await state.set_state(AdminState.manage_products)
    await message.answer(
        "📦 <b>Mahsulotlarni boshqarish</b>\n\n"
        "Quyidagi mahsulotlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_products_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_delete_'), state=AdminState.edit_product)
async def admin_delete_product(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Ask for confirmation before deleting a product
    """
    await callback_query.answer()
    
    # Extract product_id from callback data
    product_id = int(callback_query.data.split('_')[2])
    
    # Store the selected product id in state
    async with state.proxy() as data:
        data['product_id'] = product_id
    
    # Get product details
    session = get_session()
    product = session.query(Product).get(product_id)
    product_name = product.name if product else "Unknown"
    session.close()
    
    # Update state
    await state.set_state(AdminState.confirm_delete)
    
    # Ask for confirmation
    await callback_query.message.edit_caption(
        f"⚠️ <b>Diqqat!</b>\n\n"
        f"Siz <b>{product_name}</b> mahsulotini o'chirishni xohlaysizmi?",
        parse_mode="HTML",
        reply_markup=get_admin_confirm_delete_keyboard(product_id)
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_confirm_delete_'), state=AdminState.confirm_delete)
async def admin_confirm_delete_product(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Confirm and delete product
    """
    await callback_query.answer()
    
    # Extract product_id from callback data
    product_id = int(callback_query.data.split('_')[3])
    
    # Delete product
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        product_name = product.name
        
        try:
            # Delete related cart items first
            cart_items = session.query(CartItem).filter_by(product_id=product_id).all()
            for item in cart_items:
                session.delete(item)
            
            # Delete the product
            session.delete(product)
            session.commit()
            
            await callback_query.message.delete()  # Delete confirmation message
            await bot.send_message(
                callback_query.from_user.id,
                f"✅ Mahsulot <b>{product_name}</b> muvaffaqiyatli o'chirildi.",
                parse_mode="HTML"
            )
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting product: {e}")
            await callback_query.message.edit_caption(
                f"⚠️ Mahsulotni o'chirishda xatolik yuz berdi: {str(e)}",
                reply_markup=None
            )
    else:
        await callback_query.message.edit_caption(
            "⚠️ Kechirasiz, mahsulot topilmadi.",
            reply_markup=None
        )
    
    session.close()
    
    # Return to products list
    await state.set_state(AdminState.manage_products)
    await bot.send_message(
        callback_query.from_user.id,
        "📦 <b>Mahsulotlarni boshqarish</b>\n\n"
        "Quyidagi mahsulotlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_products_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_cancel_delete_'), state=AdminState.confirm_delete)
async def admin_cancel_delete_product(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Cancel product deletion
    """
    await callback_query.answer()
    
    # Extract product_id from callback data
    product_id = int(callback_query.data.split('_')[3])
    
    # Get product details again
    session = get_session()
    product = session.query(Product).get(product_id)
    
    if product:
        # Update state
        await state.set_state(AdminState.edit_product)
        
        # Create product detail message
        product_text = (
            f"📦 <b>{product.name}</b>\n\n"
            f"📝 <b>Tavsif:</b> {product.description}\n\n"
            f"💰 <b>Narxi:</b> {product.formatted_price}\n\n"
            f"🔗 <b>Rasm URL:</b> {product.image_url or 'Mavjud emas'}\n\n"
            f"📂 <b>Kategoriya:</b> {product.category.name}\n\n"
            f"✅ <b>Mavjud:</b> {'Ha' if product.is_available else 'Yo`q'}"
        )
        
        # Show product details again
        await callback_query.message.edit_caption(
            product_text,
            parse_mode="HTML",
            reply_markup=get_admin_product_keyboard(product_id)
        )
    else:
        await callback_query.message.edit_text(
            "⚠️ Kechirasiz, mahsulot topilmadi.",
            reply_markup=None
        )
        
        # Return to products list
        await state.set_state(AdminState.manage_products)
        await bot.send_message(
            callback_query.from_user.id,
            "📦 <b>Mahsulotlarni boshqarish</b>\n\n"
            "Quyidagi mahsulotlardan birini tanlang:",
            parse_mode="HTML",
            reply_markup=get_admin_products_keyboard()
        )
    
    session.close()

# ====================================================================
# ERROR HANDLERS
# ====================================================================

@dp.error()
async def errors_handler(event: types.ErrorEvent):
    """
    Handle errors in update processing
    """
    # Log the error
    logger.error(f"Update {event.update} caused error {event.exception}")
    
    # Try to notify the user if possible
    if event.update.message:
        await event.update.message.answer(
            "⚠️ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
        )
    
    return True

# ====================================================================
# MAIN FUNCTION
# ====================================================================

async def on_startup():
    """
    Tasks to execute on startup
    """
    # Initialize database
    init_db()
    
    # Add sample data if needed
    add_sample_data()
    
    # Set bot commands in menu
    commands = [
        BotCommand(command="/start", description="Botni ishga tushirish"),
        BotCommand(command="/help", description="Yordam olish"),
        BotCommand(command="/admin", description="Admin panel (faqat adminlar uchun)")
    ]
    await bot(SetMyCommands(commands=commands))
    
    # Log bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot @{bot_info.username} started!")
    logger.info(f"Bot ID: {bot_info.id}")
    logger.info(f"Bot username: @{bot_info.username}")
    logger.info(f"Bot link: https://t.me/{bot_info.username}")
    logger.info(f"Admin ID: {ADMIN_ID}")

async def main():
    """
    Main function to start the bot
    """
    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Create and include router
    router = Router()
    dp.include_router(router)
    
    # Register all handlers here
    # TODO: Move your handlers to use router instead of dp
    
    # Start polling
    await on_startup()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    # Start the bot
    asyncio.run(main())
