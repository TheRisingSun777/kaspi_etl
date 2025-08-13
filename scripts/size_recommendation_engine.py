#!/usr/bin/env python3
"""
Size Recommendation Engine for Kaspi Orders

Adds CLI to write recommendations into SQLite from explicit args or by scanning
inbound WhatsApp messages stored in `wa_inbox`.

Usage examples:
- ./venv/bin/python scripts/size_recommendation_engine.py --order-id 607640463 \
    --height 178 --weight 82
- ./venv/bin/python scripts/size_recommendation_engine.py --scan-inbox
"""
import argparse
import json
import logging
import pathlib
import re
import sqlite3
from dataclasses import dataclass

# Setup paths
DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "db" / "erp.db"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class SizeRecommendation:
    """Size recommendation result"""
    recommended_size: str
    confidence_score: float
    reasoning: str
    alternative_sizes: list


class SizeRecommendationEngine:
    """Engine for recommending clothing sizes based on customer measurements"""
    
    # Size charts for different product types and genders
    SIZE_CHARTS = {
        'CL': {  # Clothing
            'Men': {
                'height_weight_matrix': {
                    # Format: (height_min, height_max, weight_min, weight_max): size
                    (165, 170, 60, 70): 'S',
                    (165, 170, 70, 80): 'M',
                    (165, 170, 80, 90): 'L',
                    (170, 175, 60, 70): 'S',
                    (170, 175, 70, 80): 'M',
                    (170, 175, 80, 90): 'L',
                    (170, 175, 90, 100): 'XL',
                    (175, 180, 65, 75): 'M',
                    (175, 180, 75, 85): 'L',
                    (175, 180, 85, 95): 'XL',
                    (175, 180, 95, 105): '2XL',
                    (180, 185, 70, 80): 'L',
                    (180, 185, 80, 90): 'XL',
                    (180, 185, 90, 100): '2XL',
                    (180, 185, 100, 110): '3XL',
                    (185, 195, 75, 85): 'XL',
                    (185, 195, 85, 95): '2XL',
                    (185, 195, 95, 110): '3XL',
                    (185, 195, 110, 125): '4XL',
                },
                'chest_sizes': {
                    'S': (86, 92),   # chest circumference in cm
                    'M': (92, 98),
                    'L': (98, 104),
                    'XL': (104, 112),
                    '2XL': (112, 120),
                    '3XL': (120, 128),
                    '4XL': (128, 136),
                }
            },
            'Women': {
                'height_weight_matrix': {
                    (155, 165, 45, 55): 'S',
                    (155, 165, 55, 65): 'M',
                    (155, 165, 65, 75): 'L',
                    (165, 170, 50, 60): 'S',
                    (165, 170, 60, 70): 'M',
                    (165, 170, 70, 80): 'L',
                    (165, 170, 80, 90): 'XL',
                    (170, 175, 55, 65): 'M',
                    (170, 175, 65, 75): 'L',
                    (170, 175, 75, 85): 'XL',
                    (170, 175, 85, 95): '2XL',
                    (175, 180, 60, 70): 'L',
                    (175, 180, 70, 80): 'XL',
                    (175, 180, 80, 90): '2XL',
                },
                'chest_sizes': {
                    'S': (82, 86),
                    'M': (86, 90),
                    'L': (90, 96),
                    'XL': (96, 102),
                    '2XL': (102, 108),
                    '3XL': (108, 114),
                }
            },
            'Kids': {
                'age_height_matrix': {
                    # Format: (age_min, age_max, height_min, height_max): size
                    (2, 3, 85, 95): '22',
                    (3, 4, 95, 105): '24',
                    (4, 5, 105, 115): '26',
                    (5, 6, 115, 125): '28',
                    (6, 7, 125, 135): '30',
                    (7, 8, 135, 145): '32',
                    (8, 9, 145, 155): '34',
                },
                'height_sizes': {
                    '22': (85, 95),
                    '24': (95, 105),
                    '26': (105, 115),
                    '28': (115, 125),
                    '30': (125, 135),
                    '32': (135, 145),
                    '34': (145, 155),
                }
            }
        }
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def recommend_size(self, 
                      height_cm: int, 
                      weight_kg: int, 
                      gender: str, 
                      product_type: str,
                      age: int | None = None) -> SizeRecommendation:
        """
        Recommend size based on customer measurements
        
        Args:
            height_cm: Customer height in centimeters
            weight_kg: Customer weight in kilograms
            gender: 'Men', 'Women', or 'Kids'
            product_type: Product category (e.g., 'CL' for clothing)
            age: Age in years (required for kids)
            
        Returns:
            SizeRecommendation object with recommended size and details
        """
        
        if product_type not in self.SIZE_CHARTS:
            return SizeRecommendation(
                recommended_size="M",  # Default fallback
                confidence_score=0.1,
                reasoning=f"Unknown product type: {product_type}",
                alternative_sizes=["S", "L"]
            )
        
        if gender not in self.SIZE_CHARTS[product_type]:
            return SizeRecommendation(
                recommended_size="M",  # Default fallback
                confidence_score=0.1,
                reasoning=f"Unknown gender: {gender}",
                alternative_sizes=["S", "L"]
            )
        
        size_chart = self.SIZE_CHARTS[product_type][gender]
        
        if gender == 'Kids':
            return self._recommend_kids_size(height_cm, age, size_chart)
        else:
            return self._recommend_adult_size(height_cm, weight_kg, size_chart)
    
    def _recommend_adult_size(self, height_cm: int, weight_kg: int, size_chart: dict) -> SizeRecommendation:
        """Recommend size for adults based on height/weight matrix"""
        
        best_match = None
        best_score = 0
        alternatives = []
        
        for (h_min, h_max, w_min, w_max), size in size_chart['height_weight_matrix'].items():
            score = 0
            
            # Calculate how well the measurements fit this size range
            if h_min <= height_cm <= h_max:
                score += 0.5  # Height fits perfectly
            else:
                # Penalty for height outside range
                height_distance = min(abs(height_cm - h_min), abs(height_cm - h_max))
                score += max(0, 0.5 - (height_distance / 20))  # Reduce score based on distance
            
            if w_min <= weight_kg <= w_max:
                score += 0.5  # Weight fits perfectly
            else:
                # Penalty for weight outside range
                weight_distance = min(abs(weight_kg - w_min), abs(weight_kg - w_max))
                score += max(0, 0.5 - (weight_distance / 10))  # Reduce score based on distance
            
            if score > best_score:
                if best_match:
                    alternatives.append(best_match)
                best_match = (size, score)
                best_score = score
            elif score > 0.3:  # Good alternative
                alternatives.append((size, score))
        
        if best_match:
            recommended_size, confidence = best_match
            
            # Generate reasoning
            reasoning = f"Based on height {height_cm}cm and weight {weight_kg}kg"
            if confidence > 0.8:
                reasoning += " - excellent fit"
            elif confidence > 0.6:
                reasoning += " - good fit"
            else:
                reasoning += " - approximate fit"
            
            # Sort alternatives by score and extract size names
            alternatives.sort(key=lambda x: x[1], reverse=True)
            alt_sizes = [alt[0] for alt in alternatives[:3]]
            
            return SizeRecommendation(
                recommended_size=recommended_size,
                confidence_score=confidence,
                reasoning=reasoning,
                alternative_sizes=alt_sizes
            )
        
        # Fallback if no match found
        return SizeRecommendation(
            recommended_size="M",
            confidence_score=0.2,
            reasoning=f"No exact match for height {height_cm}cm, weight {weight_kg}kg - using default",
            alternative_sizes=["S", "L", "XL"]
        )
    
    def _recommend_kids_size(self, height_cm: int, age: int | None, size_chart: dict) -> SizeRecommendation:
        """Recommend size for kids based on height and age"""
        
        if age:
            # Try age-height matrix first
            for (age_min, age_max, h_min, h_max), size in size_chart['age_height_matrix'].items():
                if age_min <= age <= age_max and h_min <= height_cm <= h_max:
                    return SizeRecommendation(
                        recommended_size=size,
                        confidence_score=0.9,
                        reasoning=f"Perfect match for age {age} and height {height_cm}cm",
                        alternative_sizes=[]
                    )
        
        # Fall back to height-only matching
        best_match = None
        best_distance = float('inf')
        
        for size, (h_min, h_max) in size_chart['height_sizes'].items():
            if h_min <= height_cm <= h_max:
                return SizeRecommendation(
                    recommended_size=size,
                    confidence_score=0.8,
                    reasoning=f"Good fit for height {height_cm}cm",
                    alternative_sizes=[]
                )
            
            # Calculate distance to this size range
            distance = min(abs(height_cm - h_min), abs(height_cm - h_max))
            if distance < best_distance:
                best_distance = distance
                best_match = size
        
        if best_match:
            confidence = max(0.3, 1.0 - (best_distance / 20))
            return SizeRecommendation(
                recommended_size=best_match,
                confidence_score=confidence,
                reasoning=f"Approximate fit for height {height_cm}cm (closest available size)",
                alternative_sizes=[]
            )
        
        # Ultimate fallback
        return SizeRecommendation(
            recommended_size="26",
            confidence_score=0.1,
            reasoning="Default kids size - please verify",
            alternative_sizes=["24", "28"]
        )
    
    def get_size_confirmation_message(self, 
                                    customer_name: str,
                                    product_name: str,
                                    recommendation: SizeRecommendation) -> str:
        """Generate WhatsApp message for size confirmation"""
        
        message = f"Привет {customer_name}! 👋\n\n"
        message += f"Для товара '{product_name}' мы рекомендуем размер: *{recommendation.recommended_size}*\n\n"
        message += f"Обоснование: {recommendation.reasoning}\n"
        
        if recommendation.confidence_score > 0.8:
            message += "✅ Мы уверены в этом размере!\n"
        elif recommendation.confidence_score > 0.6:
            message += "👍 Хороший выбор размера\n"
        else:
            message += "⚠️ Приблизительный размер, пожалуйста проверьте\n"
        
        if recommendation.alternative_sizes:
            message += f"\nАльтернативные размеры: {', '.join(recommendation.alternative_sizes)}\n"
        
        message += "\nПожалуйста, подтвердите размер или сообщите ваши предпочтения! 📏"
        
        return message
    
    def save_recommendation(self, 
                          order_id: str, 
                          recommendation: SizeRecommendation,
                          customer_height: int,
                          customer_weight: int) -> None:
        """Save recommendation to database for tracking (minimal schema)."""

        con = sqlite3.connect(DB_PATH)
        try:
            cur = con.cursor()

            # Create table if not exists (minimal columns per Phase 3 spec)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS size_recommendations (
                    order_id TEXT,
                    height INTEGER,
                    weight INTEGER,
                    final_size TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Insert minimal record
            cur.execute(
                """
                INSERT INTO size_recommendations (order_id, height, weight, final_size)
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_id,
                    int(customer_height),
                    int(customer_weight),
                    recommendation.recommended_size,
                ),
            )

            con.commit()
            self.logger.info(f"Saved size recommendation for order {order_id}")

        except Exception as e:
            self.logger.error(f"Error saving recommendation: {e}")
        finally:
            con.close()


def _ensure_table() -> None:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS size_recommendations (
                order_id TEXT,
                height INTEGER,
                weight INTEGER,
                final_size TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        con.commit()
    finally:
        con.close()


_H_RE = re.compile(r"(\d{2,3})\s*(см|cm)", re.IGNORECASE)
_W_RE = re.compile(r"(\d{2,3})\s*(кг|kg)", re.IGNORECASE)


def _extract_hw(text: str, parsed_json: str | None) -> tuple[int | None, int | None]:
    h = w = None
    if parsed_json:
        try:
            data = json.loads(parsed_json)
            if isinstance(data, dict):
                if "height_cm" in data:
                    h = int(data["height_cm"])  # type: ignore[arg-type]
                if "weight_kg" in data:
                    w = int(data["weight_kg"])  # type: ignore[arg-type]
        except Exception:
            pass
    if h is None:
        m = _H_RE.search(text or "")
        if m:
            h = int(m.group(1))
    if w is None:
        m = _W_RE.search(text or "")
        if m:
            w = int(m.group(1))
    return h, w


def _upsert_recommendation(order_id: str, height: int, weight: int, final_size: str) -> None:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        # Deduplicate by order_id: if exists, skip
        cur.execute("SELECT COUNT(1) FROM size_recommendations WHERE order_id = ?", (order_id,))
        if cur.fetchone()[0]:
            return
        cur.execute(
            """
            INSERT INTO size_recommendations (order_id, height, weight, final_size)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, int(height), int(weight), final_size),
        )
        con.commit()
    finally:
        con.close()


def run_single(order_id: str, height: int, weight: int) -> str:
    engine = SizeRecommendationEngine()
    rec = engine.recommend_size(height_cm=height, weight_kg=weight, gender='Men', product_type='CL')
    _upsert_recommendation(order_id, height, weight, rec.recommended_size)
    return rec.recommended_size


def _count_recs(order_id: str) -> int:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("SELECT COUNT(1) FROM size_recommendations WHERE order_id = ?", (order_id,))
        return int(cur.fetchone()[0])
    finally:
        con.close()


def run_scan_inbox(limit: int | None = None) -> int:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        q = "SELECT id, order_id, text, parsed_json, created_at FROM wa_inbox ORDER BY created_at DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        rows = cur.execute(q).fetchall()
    finally:
        con.close()

    inserted = 0
    for row in rows:
        inbox_id, order_id, text, parsed_json, created_at = row
        use_order_id = order_id if order_id and str(order_id).strip() else inbox_id
        h, w = _extract_hw(str(text or ""), str(parsed_json or ""))
        if h is None or w is None:
            continue
        engine = SizeRecommendationEngine()
        rec = engine.recommend_size(height_cm=int(h), weight_kg=int(w), gender='Men', product_type='CL')
        before = _count_recs(str(use_order_id))
        _upsert_recommendation(str(use_order_id), int(h), int(w), rec.recommended_size)
        after = _count_recs(str(use_order_id))
        if after > before:
            inserted += 1
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Size Recommendation Engine CLI")
    mx = parser.add_mutually_exclusive_group(required=True)
    mx.add_argument("--scan-inbox", action="store_true", help="Scan wa_inbox for new height/weight messages and insert recommendations")
    mx.add_argument("--order-id", type=str, help="Order ID to write recommendation for (requires --height and --weight)")
    parser.add_argument("--height", type=int, help="Height in cm")
    parser.add_argument("--weight", type=int, help="Weight in kg")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit when scanning inbox")

    args = parser.parse_args()
    _ensure_table()

    if args.scan_inbox:
        inserted = run_scan_inbox(limit=args.limit)
        logger.info(f"Inserted {inserted} recommendations from inbox")
        return 0

    if args.order_id and (args.height is None or args.weight is None):
        parser.error("--order-id requires --height and --weight")
    final = run_single(args.order_id, args.height, args.weight)
    logger.info(f"Order {args.order_id}: final_size={final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
