"""
Database models for the application.
"""
from datetime import datetime
from app import db

class Customer(db.Model):
    """Customer model representing a Telegram user who has placed an order."""
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    orders = db.relationship('Order', backref='customer', lazy=True)
    cart_items = db.relationship('CartItem', backref='customer', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Customer {self.name} (ID: {self.id})>'

class ProductCategory(db.Model):
    """Category model for organizing products."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    products = db.relationship('Product', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<ProductCategory {self.name}>'

class Product(db.Model):
    """Product model representing a product for sale."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Integer, nullable=False)  # Price in UZS (Uzbekistan Som)
    image_url = db.Column(db.String(255), nullable=True)
    is_available = db.Column(db.Boolean, default=True)
    category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    cart_items = db.relationship('CartItem', backref='product', lazy=True)
    
    def __repr__(self):
        return f'<Product {self.name} - {self.price} UZS>'
    
    @property
    def formatted_price(self):
        """Return a formatted price with UZS currency code."""
        # Format with thousand separators and UZS currency code
        return f"{self.price:,} UZS".replace(",", " ")

class CartItem(db.Model):
    """CartItem model representing a product in a customer's cart."""
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<CartItem {self.product_id} ({self.quantity})>'
    
    @property
    def subtotal(self):
        """Calculate subtotal for this cart item."""
        return self.product.price * self.quantity

class Order(db.Model):
    """Order model representing an order placed by a customer."""
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    status = db.Column(db.String(50), default="NEW")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Order {self.id}>'
    
    @property
    def total(self):
        """Calculate total price for this order."""
        return sum(item.subtotal for item in self.items)
        
    @property
    def status_class(self):
        """Return a Bootstrap color class based on the order status."""
        status_map = {
            "NEW": "warning",
            "PROCESSING": "info",
            "SHIPPED": "primary",
            "DELIVERED": "success",
            "CANCELLED": "danger"
        }
        return status_map.get(self.status, "secondary")

class OrderItem(db.Model):
    """OrderItem model representing a product in an order."""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    price = db.Column(db.Integer, nullable=False)  # Store the price at the time of order
    
    def __repr__(self):
        return f'<OrderItem {self.product_id} ({self.quantity})>'
    
    @property
    def subtotal(self):
        """Calculate subtotal for this order item."""
        return self.price * self.quantity