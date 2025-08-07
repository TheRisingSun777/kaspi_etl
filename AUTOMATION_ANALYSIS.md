# 🎯 Kaspi ETL Automation Analysis

## 1. 📊 CSV Column → Kaspi API Field Mapping

Based on your M02_SKU_CATALOG structure, here's the mapping:

| CSV Column | Kaspi API Field | Purpose | Notes |
|------------|----------------|---------|-------|
| `SKU_ID` | `merchantProductId` | Internal product identifier | Your unique ID |
| `Kaspi_name_core` | `title` | Product display name | Main product title |
| `Kaspi_art_1` | `masterCode` | Kaspi product code | Links to existing Kaspi product |
| `SKU_ID_KSP` | `code` | Merchant product code | Alternative product code |
| `Initial_KSP_Price` | `price` | Product price | Price in KZT |
| `Stock_entered` | `availableAmount` | Stock quantity | Current inventory |
| `Weight_kg` | `weight` | Product weight | Convert comma to dot (0,95 → 0.95) |
| `Brend` | `brand` | Brand name | Product brand |
| `Model` | `model` | Model name | Product model |
| `Color` | `color` | Color | Product color |
| `Our_Size` | `size` | Size | Product size |
| `Gender` | `gender` | Target gender | Men/Women/Kids |
| `Season` | `season` | Season | All/Winter/Summer |
| `Product_Type` | `category` | Product category | CL/ELS etc. |
| `Sub_Category` | `subcategory` | Product subcategory | More specific category |
| `Store_name` | N/A | Store assignment | Internal use only |

### 🔄 Data Transformations Needed:
- `Weight_kg`: "0,95" → 0.95 (float conversion)
- `Initial_KSP_Price`: Remove spaces, convert to integer
- `Stock_entered`: Convert to integer
- Missing values: Handle empty fields gracefully

---

## 2. 🛤️ Roadmap Choice Analysis

### Option A: Manual-download + Python ETL First
**Pros:**
✅ **Lower risk** - Don't break existing Kaspi store
✅ **Faster initial setup** - Build on existing Excel workflow
✅ **Data validation** - Clean data before API integration
✅ **Gradual learning** - Understand patterns before automation
✅ **Backup workflow** - Manual process remains if API fails

**Cons:**
❌ **Duplicate work** - Will rewrite logic for API later
❌ **Ongoing manual effort** - Still downloading files daily
❌ **Data lag** - Not real-time synchronization
❌ **Error-prone** - Manual steps introduce mistakes

### Option B: API-First Approach
**Pros:**
✅ **Real-time data** - Always current information
✅ **Full automation** - Eliminate manual downloads
✅ **Single source of truth** - API is authoritative
✅ **Future-proof** - Built for scalability

**Cons:**
❌ **Higher risk** - Could break live store operations
❌ **Complex debugging** - API errors affect business
❌ **Learning curve** - Need to understand API thoroughly
❌ **Data quality** - Bad data goes directly to live store

### 🎯 **RECOMMENDATION: Hybrid Approach**

**Phase 1 (Week 1-2): Enhanced Manual + ETL**
- Keep manual downloads but automate processing
- Build robust data validation and cleaning
- Create monitoring dashboard
- Test all logic with historical data

**Phase 2 (Week 3-4): Read-Only API Integration**
- Start with GET endpoints only (orders, products)
- Compare API data with manual downloads
- Build confidence in API reliability
- No changes to live store yet

**Phase 3 (Week 5-6): Limited API Writes**
- Start with stock updates only (low risk)
- Test order status updates
- Monitor for issues carefully

**Phase 4 (Week 7+): Full Automation**
- Product creation/updates
- Price synchronization
- Complete workflow automation

---

## 3. 🔄 Step-by-Step Automation Plan

### **Week 1: Foundation (Manual Enhanced)**

**Day 1 (4 hours)**
1. ✅ Create enhanced CSV parser with data validation
2. ✅ Build size recommendation engine (height/weight → size)
3. ✅ Create WhatsApp message templates

**Day 2 (4 hours)**
4. ✅ Automated Excel processing pipeline
5. ✅ Customer data extraction and validation
6. ✅ Size confirmation workflow automation

**Day 3 (4 hours)**
7. ✅ PDF label generation system
8. ✅ Grouping by model/size logic
9. ✅ Batch printing preparation

### **Week 2: Data Integration**

**Day 4 (4 hours)**
10. ✅ Enhanced database schema with customer data
11. ✅ Order processing workflow automation
12. ✅ Inventory impact tracking

**Day 5 (4 hours)**
13. ✅ Dashboard improvements (real-time order status)
14. ✅ Alert system for low stock/urgent orders
15. ✅ Data quality monitoring

**Day 6 (4 hours)**
16. ✅ WhatsApp integration (Twilio/360dialog setup)
17. ✅ Automated size confirmation messages
18. ✅ Response processing automation

### **Week 3: API Read Integration**

**Day 7 (4 hours)**
19. ✅ Kaspi API GET endpoints implementation
20. ✅ Order fetching automation
21. ✅ Data comparison and validation

**Day 8 (4 hours)**
22. ✅ Product catalog synchronization (read-only)
23. ✅ Price monitoring and alerts
24. ✅ Stock level verification

**Day 9 (4 hours)**
25. ✅ Customer data integration (phone numbers)
26. ✅ Order status tracking improvements
27. ✅ Real-time dashboard updates

### **Week 4: API Write Integration (Safe)**

**Day 10 (4 hours)**
28. ✅ Stock update API implementation
29. ✅ Order status update automation
30. ✅ Safe testing protocols

**Day 11 (4 hours)**
31. ✅ Order acceptance automation
32. ✅ Assembly status management
33. ✅ Delivery coordination

**Day 12 (4 hours)**
34. ✅ Label generation via API
35. ✅ Kaspi Delivery integration
36. ✅ PDF processing automation

### **Week 5: Full Automation**

**Day 13 (4 hours)**
37. ✅ Product creation/update via API
38. ✅ Price synchronization automation
39. ✅ Bulk operations optimization

**Day 14 (4 hours)**
40. ✅ Complete workflow integration
41. ✅ Error handling and recovery
42. ✅ Monitoring and alerting

**Day 15 (4 hours)**
43. ✅ Performance optimization
44. ✅ Final testing and validation
45. ✅ Documentation and training

### **Week 6: Production & Monitoring**

**Day 16 (4 hours)**
46. ✅ Production deployment
47. ✅ Live monitoring setup
48. ✅ Backup procedures

---

## 🎯 **Key Automation Components**

### **1. Size Recommendation Engine**
```python
def recommend_size(height_cm, weight_kg, gender, product_type):
    # Logic based on your sizing charts
    # Returns recommended size with confidence score
```

### **2. WhatsApp Integration**
```python
def send_size_confirmation(phone, customer_name, product, recommended_size):
    # Twilio/360dialog API integration
    # Template: "Hi {name}, for {product} we recommend size {size}"
```

### **3. PDF Label Automation**
```python
def generate_shipping_labels(orders_batch):
    # Group by model/size
    # Generate PDF labels
    # Prepare for batch printing
```

### **4. Order Processing Pipeline**
```python
def process_daily_orders():
    # Fetch new orders (API or manual)
    # Size recommendations
    # WhatsApp confirmations
    # Label generation
    # Inventory updates
```

---

## 📋 **Technical Implementation Notes**

### **Database Schema Updates**
```sql
-- Add customer interaction tracking
ALTER TABLE orders ADD COLUMN customer_phone TEXT;
ALTER TABLE orders ADD COLUMN size_confirmed BOOLEAN DEFAULT FALSE;
ALTER TABLE orders ADD COLUMN whatsapp_sent TIMESTAMP;
ALTER TABLE orders ADD COLUMN label_generated TIMESTAMP;

-- Add size recommendation tracking
CREATE TABLE size_recommendations (
    order_id TEXT,
    recommended_size TEXT,
    confidence_score REAL,
    customer_height INTEGER,
    customer_weight INTEGER,
    final_size TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### **Configuration Management**
```python
# config.py
WHATSAPP_API_KEY = os.getenv('WHATSAPP_API_KEY')
KASPI_API_TOKEN = os.getenv('KASPI_TOKEN')
SIZE_RECOMMENDATION_RULES = {
    'CL': {  # Clothing
        'Men': {...},
        'Women': {...},
        'Kids': {...}
    }
}
```

---

## 🚀 **Final Workflow: "One Button Operation"**

**Single Command:**
```bash
python scripts/daily_operations.py
```

**What it does:**
1. ✅ Fetch new orders (API)
2. ✅ Process customer data
3. ✅ Generate size recommendations
4. ✅ Send WhatsApp confirmations
5. ✅ Generate shipping labels
6. ✅ Update inventory
7. ✅ Update order statuses
8. ✅ Generate daily reports

**Result:** ~100 orders/day processed in 5 minutes instead of 8 hours!

---

This plan transforms your manual 8-hour daily process into a 5-minute automated workflow while maintaining safety and data quality throughout the transition.
