from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List

def get_categories_keyboard(categories: List[str]) -> ReplyKeyboardMarkup:
    """Create keyboard with category buttons."""
    buttons = []
    # Create rows with 2 buttons each
    for i in range(0, len(categories), 2):
        row = []
        row.append(KeyboardButton(text=categories[i]))
        if i + 1 < len(categories):
            row.append(KeyboardButton(text=categories[i + 1]))
        buttons.append(row)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )
    return keyboard

def get_product_keyboard() -> InlineKeyboardBuilder:
    """Create keyboard for product navigation."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Ortga", callback_data="back_to_categories")
    return builder.as_markup()
