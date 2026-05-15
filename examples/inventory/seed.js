// Inventory sample data for saas-graph MongoDB example
// 30 products, 5 warehouses, stock records, ~200 movements

db = db.getSiblingDB("inventory");

// ============================================================
// Products  (30 rows)
// ============================================================

const products = [
  { name: "Wireless Bluetooth Headphones",  sku: "ELEC-001", category: "Electronics",    unit_cost: 35.00, reorder_point: 50,  is_active: true },
  { name: "USB-C Charging Cable 6ft",       sku: "ELEC-002", category: "Electronics",    unit_cost:  4.50, reorder_point: 100, is_active: true },
  { name: "Mechanical Keyboard RGB",        sku: "ELEC-003", category: "Electronics",    unit_cost: 58.00, reorder_point: 30,  is_active: true },
  { name: "27\" 4K Monitor",                sku: "ELEC-004", category: "Electronics",    unit_cost: 220.00,reorder_point: 10,  is_active: true },
  { name: "Portable SSD 1TB",               sku: "ELEC-005", category: "Electronics",    unit_cost: 42.00, reorder_point: 40,  is_active: true },
  { name: "Webcam 1080p",                   sku: "ELEC-006", category: "Electronics",    unit_cost: 18.00, reorder_point: 60,  is_active: true },
  { name: "Cotton Crew T-Shirt",            sku: "CLTH-001", category: "Clothing",       unit_cost:  8.00, reorder_point: 100, is_active: true },
  { name: "Slim Fit Jeans",                 sku: "CLTH-002", category: "Clothing",       unit_cost: 22.00, reorder_point: 50,  is_active: true },
  { name: "Lightweight Rain Jacket",        sku: "CLTH-003", category: "Clothing",       unit_cost: 35.00, reorder_point: 30,  is_active: true },
  { name: "Running Sneakers",               sku: "CLTH-004", category: "Clothing",       unit_cost: 48.00, reorder_point: 40,  is_active: true },
  { name: "Stainless Steel Water Bottle",   sku: "HOME-001", category: "Home & Kitchen", unit_cost:  8.00, reorder_point: 100, is_active: true },
  { name: "Non-Stick Frying Pan 12\"",      sku: "HOME-002", category: "Home & Kitchen", unit_cost: 14.00, reorder_point: 40,  is_active: true },
  { name: "French Press Coffee Maker",      sku: "HOME-003", category: "Home & Kitchen", unit_cost: 10.00, reorder_point: 50,  is_active: true },
  { name: "Bamboo Cutting Board Set",       sku: "HOME-004", category: "Home & Kitchen", unit_cost:  7.00, reorder_point: 60,  is_active: true },
  { name: "LED Desk Lamp Dimmable",         sku: "HOME-005", category: "Home & Kitchen", unit_cost: 12.00, reorder_point: 50,  is_active: true },
  { name: "Yoga Mat Premium 6mm",           sku: "SPRT-001", category: "Sports",         unit_cost: 10.00, reorder_point: 60,  is_active: true },
  { name: "Resistance Bands Set",           sku: "SPRT-002", category: "Sports",         unit_cost:  6.00, reorder_point: 80,  is_active: true },
  { name: "Adjustable Dumbbell Pair",       sku: "SPRT-003", category: "Sports",         unit_cost: 65.00, reorder_point: 15,  is_active: true },
  { name: "Foam Roller 18\"",               sku: "SPRT-004", category: "Sports",         unit_cost:  8.00, reorder_point: 60,  is_active: true },
  { name: "Insulated Gym Bag",              sku: "SPRT-005", category: "Sports",         unit_cost: 15.00, reorder_point: 40,  is_active: true },
  { name: "JavaScript: The Good Parts",     sku: "BOOK-001", category: "Books",          unit_cost: 12.00, reorder_point: 30,  is_active: true },
  { name: "Designing Data-Intensive Apps",  sku: "BOOK-002", category: "Books",          unit_cost: 20.00, reorder_point: 20,  is_active: true },
  { name: "Atomic Habits",                  sku: "BOOK-003", category: "Books",          unit_cost:  6.00, reorder_point: 60,  is_active: true },
  { name: "The Pragmatic Programmer",       sku: "BOOK-004", category: "Books",          unit_cost: 22.00, reorder_point: 15,  is_active: true },
  { name: "Clean Code",                     sku: "BOOK-005", category: "Books",          unit_cost: 16.00, reorder_point: 25,  is_active: true },
  { name: "Deep Work",                      sku: "BOOK-006", category: "Books",          unit_cost:  5.00, reorder_point: 50,  is_active: true },
  { name: "Staff Engineer",                 sku: "BOOK-007", category: "Books",          unit_cost: 14.00, reorder_point: 15,  is_active: false },
  { name: "Protein Shaker Bottle",          sku: "SPRT-006", category: "Sports",         unit_cost:  3.00, reorder_point: 100, is_active: true },
  { name: "Cycling Gloves Padded",          sku: "SPRT-007", category: "Sports",         unit_cost:  8.00, reorder_point: 40,  is_active: true },
  { name: "Tennis Racket Intermediate",     sku: "SPRT-008", category: "Sports",         unit_cost: 32.00, reorder_point: 20,  is_active: true },
];

db.products.insertMany(products);
const productIds = db.products.find({}, { _id: 1 }).toArray().map(p => p._id);

// ============================================================
// Warehouses  (5 rows)
// ============================================================

const warehouses = [
  { name: "East Coast Hub",    city: "Newark",      state: "NJ", capacity: 50000 },
  { name: "West Coast Hub",    city: "Los Angeles",  state: "CA", capacity: 60000 },
  { name: "Midwest Center",    city: "Chicago",      state: "IL", capacity: 40000 },
  { name: "Southeast Depot",   city: "Atlanta",      state: "GA", capacity: 35000 },
  { name: "Northwest Depot",   city: "Seattle",      state: "WA", capacity: 30000 },
];

db.warehouses.insertMany(warehouses);
const warehouseIds = db.warehouses.find({}, { _id: 1 }).toArray().map(w => w._id);

// ============================================================
// Stock  (one record per product per warehouse = ~150 rows)
// ============================================================

const stockDocs = [];
for (const pid of productIds) {
  for (const wid of warehouseIds) {
    if (Math.random() > 0.15) {
      stockDocs.push({
        product_id: pid,
        warehouse_id: wid,
        quantity: Math.floor(Math.random() * 400) + 10,
        last_updated: new Date(Date.now() - Math.floor(Math.random() * 30) * 86400000),
      });
    }
  }
}
db.stock.insertMany(stockDocs);

// ============================================================
// Movements  (~200 rows over the past 90 days)
// ============================================================

const movementTypes = ["inbound", "outbound", "transfer"];
const movementDocs = [];
for (let i = 0; i < 200; i++) {
  const typeIdx = Math.random();
  const mtype = typeIdx < 0.4 ? "inbound" : typeIdx < 0.8 ? "outbound" : "transfer";
  const pid = productIds[Math.floor(Math.random() * productIds.length)];
  const wid = warehouseIds[Math.floor(Math.random() * warehouseIds.length)];
  const daysAgo = Math.floor(Math.random() * 90);

  movementDocs.push({
    product_id: pid,
    warehouse_id: wid,
    type: mtype,
    quantity: Math.floor(Math.random() * 100) + 1,
    reference: mtype === "inbound" ? "PO-" + (1000 + i) : "SHP-" + (5000 + i),
    created_at: new Date(Date.now() - daysAgo * 86400000),
  });
}
db.movements.insertMany(movementDocs);

// ============================================================
// Indexes
// ============================================================

db.products.createIndex({ sku: 1 }, { unique: true });
db.products.createIndex({ category: 1 });
db.stock.createIndex({ product_id: 1, warehouse_id: 1 }, { unique: true });
db.stock.createIndex({ warehouse_id: 1 });
db.movements.createIndex({ product_id: 1 });
db.movements.createIndex({ warehouse_id: 1 });
db.movements.createIndex({ created_at: -1 });
db.movements.createIndex({ type: 1 });

print("✓ Seeded inventory database: 30 products, 5 warehouses, "
      + stockDocs.length + " stock records, 200 movements");
