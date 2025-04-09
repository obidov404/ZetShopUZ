import aiosqlite
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "catalog.db"):
        self.db_path = db_path

    async def create_tables(self):
        """Create necessary database tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            # Create products table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_file_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    post_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()

    async def add_product(self, image_file_id: str, description: str, price: int, category: str):
        """Add a new product to the database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO products (image_file_id, description, price, category) VALUES (?, ?, ?, ?)',
                (image_file_id, description, price, category)
            )
            await db.commit()

    async def get_products_by_category(self, category: str):
        """Get all products in a specific category."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM products WHERE category = ? ORDER BY post_date DESC',
                (category,)
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def get_categories(self):
        """Get all unique categories."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT DISTINCT category FROM products ORDER BY category'
            ) as cursor:
                categories = await cursor.fetchall()
                return [category[0] for category in categories]

    async def cleanup_old_products(self, days: int = 14):
        """Delete products older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'DELETE FROM products WHERE post_date < ?',
                (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),)
            )
            await db.commit()
            logger.info(f"Cleaned up products older than {days} days")
