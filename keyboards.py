from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from app import app
from models import ProductCategory, Product

def get_main_keyboard():
    """
    Creates the main keyboard with buttons:
    - Catalog (Katalog)
    - Cart (Savatcha)
    - Information (Ma'lumot)
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    catalog_button = KeyboardButton("🏪 Katalog")
    cart_button = KeyboardButton("🛒 Savatcha")
    info_button = KeyboardButton("ℹ️ Ma'lumot")
    keyboard.add(catalog_button, cart_button)
    keyboard.add(info_button)
    return keyboard

def get_phone_keyboard():
    """
    Creates a keyboard with a button to share phone number
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    phone_button = KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)
    keyboard.add(phone_button)
    return keyboard

def get_back_keyboard():
    """
    Creates a keyboard with just a back button
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    back_button = KeyboardButton("⬅️ Ortga")
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
    
    with app.app_context():
        categories = ProductCategory.query.all()
        
        for category in categories:
            # Count products in this category
            product_count = Product.query.filter_by(category_id=category.id, is_available=True).count()
            
            button = InlineKeyboardButton(
                text=f"{category.name} ({product_count} ta)",
                callback_data=f"category_{category.id}"
            )
            markup.add(button)
    
    return markup

def get_products_keyboard(category_id):
    """
    Creates an inline keyboard with products from a specific category
    """
    markup = InlineKeyboardMarkup(row_width=1)
    
    with app.app_context():
        category = ProductCategory.query.get(category_id)
        if not category:
            return markup
            
        products = Product.query.filter_by(category_id=category_id, is_available=True).all()
        
        for product in products:
            button = InlineKeyboardButton(
                text=f"{product.name} - {product.formatted_price}",
                callback_data=f"product_{product.id}"
            )
            markup.add(button)
        
        # Add back button
        back_button = InlineKeyboardButton(
            text="⬅️ Ortga",
            callback_data="back_to_categories"
        )
        markup.add(back_button)
    
    return markup

def get_product_detail_keyboard(product_id):
    """
    Creates an inline keyboard for a product detail view with 
    add to cart button and back button
    """
    markup = InlineKeyboardMarkup(row_width=2)
    
    # Add to cart button
    add_cart_button = InlineKeyboardButton(
        text="🛒 Savatga qo'shish",
        callback_data=f"add_to_cart_{product_id}"
    )
    
    # Get product's category for back button
    with app.app_context():
        product = Product.query.get(product_id)
        if not product:
            return markup
        
        category_id = product.category_id
    
    # Back to category button
    back_button = InlineKeyboardButton(
        text="⬅️ Ortga",
        callback_data=f"back_to_products_{category_id}"
    )
    
    markup.add(add_cart_button, back_button)
    return markup

def get_cart_keyboard():
    """
    Creates a keyboard for cart management
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    checkout_button = KeyboardButton("✅ Buyurtma berish")
    clear_button = KeyboardButton("🗑 Savatni tozalash")
    back_button = KeyboardButton("⬅️ Ortga")
    keyboard.add(checkout_button)
    keyboard.add(clear_button, back_button)
    return keyboard

def get_confirm_order_keyboard():
    """
    Creates a keyboard for confirming or canceling an order
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    confirm_button = KeyboardButton("✅ Tasdiqlash")
    cancel_button = KeyboardButton("❌ Bekor qilish")
    keyboard.add(confirm_button, cancel_button)
    return keyboard

def get_quantity_keyboard():
    """
    Creates an inline keyboard for selecting quantity
    """
    markup = InlineKeyboardMarkup(row_width=5)
    
    # Add number buttons 1-5
    buttons = []
    for i in range(1, 6):
        buttons.append(InlineKeyboardButton(
            text=str(i),
            callback_data=f"qty_{i}"
        ))
    markup.add(*buttons)
    
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
    products_button = KeyboardButton("🏷️ Mahsulotlarni boshqarish")
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
    
    with app.app_context():
        products = Product.query.all()
        
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
    
    return markup
