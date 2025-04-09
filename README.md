# ZetShop Catalog Bot

A Telegram bot that monitors the @ZetShopUz channel and creates a product catalog from posts.

## Features

- Monitors @ZetShopUz channel for new product posts
- Automatically extracts product information from posts
- Categorizes products based on hashtags
- Shows products to users by category
- Automatically cleans up old products (14 days)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:
- BOT_TOKEN: Your Telegram bot token

3. Run the bot:
```bash
python bot.py
```

## Deployment

The bot is ready for deployment on platforms like Heroku or Render.com using the included Procfile.
