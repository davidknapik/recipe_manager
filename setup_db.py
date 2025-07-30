# setup_db.py

###############################################################################
# Dump table schema
###############################################################################
# import sqlite3
#
# conn = sqlite3.connect('recipes.db')
# cursor = conn.cursor()
#
# res = conn.execute("SELECT * FROM sqlite_master where type='table'")
# 
# for y in res:
#      print(y)
#
#  conn.commit()
# conn.close()
###############################################################################

import sqlite3

conn = sqlite3.connect('recipes.db')
cursor = conn.cursor()

# Create ingredients table
cursor.execute('''
CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL, 
    desnity_g_ml REAL
)''')

# Create ingredient_purchases table
cursor.execute('''
CREATE TABLE IF NOT EXISTS ingredient_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL,
    brand TEXT,
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
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (recipe_id, ingredient_id),
    FOREIGN KEY (recipe_id) REFERENCES recipes (id),
    FOREIGN KEY (ingredient_id) REFERENCES ingredients (id)
)''')

conn.commit()
conn.close()
print("Database initialized successfully.")