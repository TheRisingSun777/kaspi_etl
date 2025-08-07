#!/usr/bin/env python3
"""
Size Recommendation Engine for Kaspi Orders
Recommends clothing sizes based on customer height/weight and product type
"""
import pandas as pd
import sqlite3
import pathlib
import logging
from typing import Dict, Optional, Tuple
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
                      age: Optional[int] = None) -> SizeRecommendation:
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
    
    def _recommend_adult_size(self, height_cm: int, weight_kg: int, size_chart: Dict) -> SizeRecommendation:
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
    
    def _recommend_kids_size(self, height_cm: int, age: Optional[int], size_chart: Dict) -> SizeRecommendation:
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
        """Save recommendation to database for tracking"""
        
        con = sqlite3.connect(DB_PATH)
        try:
            cur = con.cursor()
            
            # Create table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS size_recommendations (
                    order_id TEXT,
                    recommended_size TEXT,
                    confidence_score REAL,
                    reasoning TEXT,
                    customer_height INTEGER,
                    customer_weight INTEGER,
                    alternative_sizes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    final_size TEXT,
                    customer_confirmed BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Insert recommendation
            cur.execute("""
                INSERT INTO size_recommendations 
                (order_id, recommended_size, confidence_score, reasoning, 
                 customer_height, customer_weight, alternative_sizes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                recommendation.recommended_size,
                recommendation.confidence_score,
                recommendation.reasoning,
                customer_height,
                customer_weight,
                ','.join(recommendation.alternative_sizes)
            ))
            
            con.commit()
            self.logger.info(f"Saved size recommendation for order {order_id}")
            
        except Exception as e:
            self.logger.error(f"Error saving recommendation: {e}")
        finally:
            con.close()


def main():
    """Test the size recommendation engine"""
    engine = SizeRecommendationEngine()
    
    # Test cases
    test_cases = [
        {
            'name': 'Typical male customer',
            'height': 175,
            'weight': 80,
            'gender': 'Men',
            'product_type': 'CL'
        },
        {
            'name': 'Female customer',
            'height': 165,
            'weight': 60,
            'gender': 'Women',
            'product_type': 'CL'
        },
        {
            'name': 'Kids customer',
            'height': 120,
            'weight': 25,
            'gender': 'Kids',
            'product_type': 'CL',
            'age': 5
        }
    ]
    
    print("🧮 SIZE RECOMMENDATION ENGINE TEST")
    print("=" * 50)
    
    for test in test_cases:
        print(f"\n📏 Testing: {test['name']}")
        print(f"   Height: {test['height']}cm, Weight: {test['weight']}kg")
        
        recommendation = engine.recommend_size(
            height_cm=test['height'],
            weight_kg=test['weight'],
            gender=test['gender'],
            product_type=test['product_type'],
            age=test.get('age')
        )
        
        print(f"   ✅ Recommended size: {recommendation.recommended_size}")
        print(f"   📊 Confidence: {recommendation.confidence_score:.1%}")
        print(f"   💭 Reasoning: {recommendation.reasoning}")
        
        if recommendation.alternative_sizes:
            print(f"   🔄 Alternatives: {', '.join(recommendation.alternative_sizes)}")
        
        # Test message generation
        message = engine.get_size_confirmation_message(
            customer_name="Али",
            product_name="Футболка черная",
            recommendation=recommendation
        )
        print(f"\n💬 WhatsApp message preview:")
        print("   " + message.replace('\n', '\n   '))


if __name__ == "__main__":
    main()
