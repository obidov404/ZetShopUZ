# ZetShop Bot

A Telegram bot for managing an online shop with admin panel and customer features.

## Features

### Admin Features
- Product management (add, edit, delete)
- Category management
- Order management
- View customer information

### Customer Features
- Browse product catalog by categories
- Add products to cart
- Place orders
- View order history

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables in `.env`:
```
BOT_TOKEN=your_bot_token
DATABASE_URL=sqlite:///zetshop.db
ADMIN_USER_ID=your_telegram_id
```

3. Run the bot:
```bash
python persistent_bot.py
```

## Deployment

This bot is configured to run on Render.com. The `Procfile` and `requirements.txt` are already set up for deployment.
