import re
from typing import Optional, Tuple

# Category mapping
CATEGORY_MAPPING = {
    'koylak': "Ko'ylaklar",
    'shortik': "Shortiklar",
    'krassovka': "Krasovkalar",
    'sumka': "Sumkalar",
    'kurtka': "Kurtkalar",
    'shim': "Shimlar",
    'futbolka': "Futbolkalar",
    'tufli': "Tuflilar",
    'etik': "Etiklar",
    'kepka': "Kepkalar"
}


def extract_price(text: str) -> Optional[int]:
    """Extract price from text in UZS."""
    # Look for price patterns like "Narxi: 150 000 so'm" or "150000 so'm"
    price_pattern = r'(?:narxi:?\s*)?(\d+(?:[ ,]\d+)*)\s*(?:so[\'']m|сум)'
    match = re.search(price_pattern, text.lower())
    if match:
        # Remove spaces and commas from the price string
        price_str = re.sub(r'[ ,]', '', match.group(1))
        try:
            return int(price_str)
        except ValueError:
            return None
    return None

def extract_category(text: str) -> Optional[str]:
    """Extract category from hashtags."""
    # Look for hashtags that match our categories
    for tag, category in CATEGORY_MAPPING.items():
        if f'#{tag}' in text.lower():
            return category
    return None

def format_price(price: int) -> str:
    """Format price with spaces for thousands."""
    return f"{price:,}".replace(',', ' ') + " so'm"

def extract_product_info(text: str) -> Tuple[Optional[int], Optional[str], str]:
    """Extract price, category and clean description from text."""
    price = extract_price(text)
    category = extract_category(text)
    
    # Clean description by removing extra whitespace
    description = ' '.join(text.split())
    
    return price, category, description
