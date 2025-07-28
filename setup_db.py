# setup_db.py
import sqlite3

conn = sqlite3.connect('recipes.db')
cursor = conn.cursor()

# Create ingredients table
cursor.execute('''
CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
)''')

# Create ingredient_purchases table
cursor.execute('''
CREATE TABLE IF NOT EXISTS ingredient_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL,
    store TEXT,
    package_amount REAL NOT NULL,
    package_unit TEXT NOT NULL,
    price REAL NOT NULL,
    purchase_date TEXT NOT NULL,
    expiry_date TEXT,
    FOREIGN KEY (ingredient_id) REFERENCES ingredients (id)
)''')

# Create recipes table
cursor.execute('''
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    preparation_instructions TEXT,
    bake_instructions TEXT,
    yield TEXT
)''')

# Create recipe_ingredients linking table
cursor.execute('''
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    amount_needed REAL NOT NULL,
    unit_needed TEXT NOT NULL,
    PRIMARY KEY (recipe_id, ingredient_id),
    FOREIGN KEY (recipe_id) REFERENCES recipes (id),
    FOREIGN KEY (ingredient_id) REFERENCES ingredients (id)
)''')

conn.commit()
conn.close()
print("Database initialized successfully.")