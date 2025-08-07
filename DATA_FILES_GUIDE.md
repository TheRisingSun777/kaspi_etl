# 📁 Data Files Guide - Kaspi ETL System

## 🎯 **What Each File Does (Simple Explanation)**

### 1. **M02_SKU_CATALOG Sample for gpt.csv** 
**What it is:** Your main product catalog/mapping file
**What it does:** 
- Contains ALL your products (325 items)
- Maps your internal SKU codes to Kaspi product codes
- Stores product information (brand, model, color, size, etc.)
- **NOT for controlling prices/stock** - just for mapping/reference

**Key columns:**
- `SKU_ID` = Your internal product code
- `Kaspi_art_1` = Kaspi's product code (if product exists on Kaspi)
- `Kaspi_name_core` = Product name for Kaspi
- `Stock_entered` = Current stock quantity
- `Initial_KSP_Price` = Price in Kaspi
- `Store_name` = Which store this belongs to (UNIVERSAL, ONLYFIT, M_GROUP)

### 2. **stock_on_hand.csv**
**What it is:** Current inventory levels
**What it does:**
- Shows how many items you have in stock RIGHT NOW
- Used for inventory management
- **This controls your stock levels**

### 3. **ActiveOrders 31.7.25.xlsx**
**What it is:** Current/new orders from Kaspi
**What it does:**
- Shows orders that just came in
- Contains customer details, product info, order status
- **This is what you need to fulfill**

### 4. **ArchiveOrders since 1.7.25.xlsx**
**What it is:** Historical order data
**What it does:**
- Past orders (for analysis and reporting)
- Sales history
- **This helps you understand what sells well**

### 5. **Purchase inquiry made by me.xlsx**
**What it is:** Purchase orders to suppliers
**What it does:**
- What you ordered from your suppliers
- When items will arrive
- **This helps track incoming inventory**

---

## 🔄 **How They Work Together**

```
📊 M02_SKU_CATALOG.csv (Master Product List)
    ↓ (maps products)
📦 stock_on_hand.csv (Current Stock)
    ↓ (affects)
🛒 ActiveOrders.xlsx (New Orders)
    ↓ (creates need for)
📋 Purchase inquiry.xlsx (Buy More Stock)
```

---

## 🎯 **The SKU Catalog File Explained**

### **What it DOES:**
✅ **Product Mapping**: Links your internal codes to Kaspi codes
✅ **Product Information**: Stores brand, model, color, size
✅ **Store Assignment**: Shows which store each product belongs to
✅ **Reference Data**: Used by other scripts to understand products

### **What it DOESN'T do:**
❌ **Control Prices**: Prices are set in Kaspi dashboard
❌ **Control Stock**: Stock is managed in `stock_on_hand.csv`
❌ **Control Sales**: Sales happen through Kaspi orders

### **Example:**
```
SKU_ID: CL_OC_MEN_PRINT51_BLACK_S
Kaspi_art_1: 103217238 (Kaspi's product code)
Store_name: UNIVERSAL (which store it belongs to)
Stock_entered: 301 (current stock)
```

---

## 🚀 **How API Integration Works**

### **Current Setup (Safe Mode):**
1. **Catalog File** → Loaded into database
2. **Stock File** → Shows current inventory
3. **Orders** → Shows what customers want
4. **No API Changes** → Your Kaspi store stays unchanged

### **Future API Integration:**
1. **Read from Kaspi**: Get current products/prices
2. **Compare**: See what's different
3. **Update**: Only change what needs changing
4. **Sync**: Keep everything in sync

---

## 📋 **Your Current Workflow**

### **Daily Process:**
1. **Check ActiveOrders.xlsx** → See new orders
2. **Check stock_on_hand.csv** → See what you have
3. **Fulfill orders** → Ship products
4. **Update stock** → Reduce quantities
5. **Check Purchase inquiry.xlsx** → See what's coming

### **Weekly Process:**
1. **Update M02_SKU_CATALOG.csv** → Add new products
2. **Update stock_on_hand.csv** → Update inventory
3. **Review ArchiveOrders.xlsx** → Analyze sales

---

## 🎯 **Why No API Changes Right Now**

### **Good Reasons:**
✅ **Duplicate SKUs**: Same product in multiple stores
✅ **Mapping Not Ready**: Need to clean up product codes
✅ **Safe Testing**: Don't want to break your live store
✅ **Manual Control**: You control prices/stock manually

### **When You'll Use API:**
🔄 **Automatic Stock Updates**: Sync inventory automatically
🔄 **Price Updates**: Change prices in bulk
🔄 **Product Creation**: Add new products automatically
🔄 **Order Management**: Accept/process orders automatically

---

## 📊 **Your Current Data Status**

### **Products by Store:**
- **UNIVERSAL**: 196 products (OC brand)
- **ONLYFIT**: 67 products (New-Clo brand)  
- **M_GROUP**: 17 products (EPSON printers)

### **Products with Kaspi Codes:**
- **264 products** have Kaspi codes (ready for API)
- **61 products** need Kaspi codes assigned

### **Next Steps:**
1. **Clean up catalog** → Remove duplicates
2. **Assign Kaspi codes** → Link to existing products
3. **Test API safely** → Small changes first
4. **Full integration** → Automatic sync

---

## 💡 **Simple Summary**

**Think of it like this:**
- **Catalog File** = Your product catalog (like a phone book)
- **Stock File** = Your warehouse inventory
- **Orders** = Customer requests
- **API** = Automatic assistant (not ready yet)

**Right now:** Everything works manually (safe)
**Later:** API will automate everything (when ready)

Does this make sense? What would you like me to explain more about?
