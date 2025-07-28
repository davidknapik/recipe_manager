import sqlite3
from datetime import date

# The name of the database file
DB_NAME = 'recipes.db'

def setup_database():
    """Creates the database and tables if they don't already exist."""
    conn = sqlite3.connect(DB_NAME)
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
    print("Database setup is complete.")

def add_ingredient():
    """Adds a new ingredient purchase to the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # Get or create the base ingredient
        ingredient_name = input("Enter ingredient name (e.g., Bread Flour): ").strip()
        cursor.execute("SELECT id FROM ingredients WHERE name = ?", (ingredient_name,))
        result = cursor.fetchone()
        
        if result:
            ingredient_id = result[0]
        else:
            cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (ingredient_name,))
            ingredient_id = cursor.lastrowid
            print(f"Added new base ingredient: '{ingredient_name}'")

        # Get purchase details
        store = input("Enter store (e.g., Tesco): ").strip()
        package_amount = float(input("Enter package amount/size (e.g., 2, 18, 800): "))
        package_unit = input("Enter package unit (e.g., kg, pack of, ml): ").strip()
        price = float(input(f"Enter price for the {package_amount}{package_unit} package: "))
        purchase_date = input("Enter purchase date (YYYY-MM-DD) [default: today]: ").strip() or str(date.today())
        expiry_date = input("Enter expiration date (YYYY-MM-DD) [optional]: ").strip()

        # Insert the purchase record
        cursor.execute('''
        INSERT INTO ingredient_purchases 
            (ingredient_id, store, package_amount, package_unit, price, purchase_date, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ingredient_id, store, package_amount, package_unit, price, purchase_date, expiry_date))
        
        conn.commit()
        print("Successfully added ingredient purchase record.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except ValueError:
        print("Invalid input. Please enter numbers for amounts and prices.")
    finally:
        conn.close()

def add_recipe():
    """Guides user through creating a new recipe and adding its ingredients."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Get recipe details
        name = input("Enter recipe name: ").strip()
        prep_instructions = input("Enter preparation instructions:\n").strip()
        bake_instructions = input("Enter baking instructions (temp, duration, etc.):\n").strip()
        recipe_yield = input("Enter recipe yield (e.g., 12 cookies): ").strip()

        cursor.execute('''
        INSERT INTO recipes (name, preparation_instructions, bake_instructions, yield)
        VALUES (?, ?, ?, ?)
        ''', (name, prep_instructions, bake_instructions, recipe_yield))
        recipe_id = cursor.lastrowid
        print(f"\nRecipe '{name}' created. Now add ingredients.")

        # Add ingredients to the recipe
        while True:
            ingredient_name = input("Enter ingredient name to add (or type 'done' to finish): ").strip()
            if ingredient_name.lower() == 'done':
                break
            
            cursor.execute("SELECT id, name FROM ingredients WHERE name = ?", (ingredient_name,))
            ingredient = cursor.fetchone()
            
            if not ingredient:
                print("Ingredient not found. Please add it via the main menu first.")
                continue

            ingredient_id, name = ingredient
            amount_needed = float(input(f"How much {name} is needed? (e.g., 250): "))
            unit_needed = input(f"What is the unit? (e.g., g, each, ml): ").strip()

            cursor.execute('''
            INSERT INTO recipe_ingredients (recipe_id, ingredient_id, amount_needed, unit_needed)
            VALUES (?, ?, ?, ?)
            ''', (recipe_id, ingredient_id, amount_needed, unit_needed))
            print(f"Added {amount_needed} {unit_needed} of {name} to the recipe.")
        
        conn.commit()
        print("\nRecipe saved successfully!")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except ValueError:
        print("Invalid number entered for amount.")
    finally:
        conn.close()

def calculate_recipe_cost():
    """Calculates and displays the cost of a selected recipe."""
    conn = sqlite3.connect(DB_NAME)
    # Use a dictionary factory to get column names
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        recipe_name = input("Enter the name of the recipe to cost: ").strip()
        cursor.execute("SELECT id FROM recipes WHERE name = ?", (recipe_name,))
        recipe = cursor.fetchone()
        
        if not recipe:
            print("Recipe not found.")
            return

        recipe_id = recipe['id']
        cursor.execute('''
        SELECT
            i.name,
            ri.amount_needed,
            ri.unit_needed
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id = ?
        ''', (recipe_id,))
        
        ingredients_for_recipe = cursor.fetchall()
        total_cost = 0.0

        print(f"\nCost breakdown for '{recipe_name}':")
        for item in ingredients_for_recipe:
            # For each ingredient, find its most recent purchase price
            cursor.execute('''
            SELECT * FROM ingredient_purchases
            WHERE ingredient_id = (SELECT id FROM ingredients WHERE name = ?)
            ORDER BY purchase_date DESC
            LIMIT 1
            ''', (item['name'],))
            
            latest_purchase = cursor.fetchone()
            if not latest_purchase:
                print(f" - No purchase history for {item['name']}. Cannot calculate cost.")
                continue

            # Basic unit conversion (can be expanded)
            # This logic assumes simple conversions. E.g., kg -> g
            package_amount = latest_purchase['package_amount']
            if latest_purchase['package_unit'] == 'kg' and item['unit_needed'] == 'g':
                package_amount *= 1000
            if latest_purchase['package_unit'] == 'l' and item['unit_needed'] == 'ml':
                package_amount *= 1000

            # Calculate cost per unit
            cost_per_unit = latest_purchase['price'] / package_amount
            ingredient_cost = item['amount_needed'] * cost_per_unit
            total_cost += ingredient_cost

            print(f" - {item['amount_needed']} {item['unit_needed']} of {item['name']}: ${ingredient_cost:.2f}")

        print("---------------------------------")
        print(f"TOTAL RECIPE COST: ${total_cost:.2f}")

    finally:
        conn.close()


def main():
    """The main function to run the user interface."""
    setup_database()
    
    while True:
        print("\n--- Recipe & Cost Manager ---")
        print("1. Add Ingredient Purchase")
        print("2. Create New Recipe")
        print("3. Calculate Recipe Cost")
        # Add options for "Update Price", "Edit Recipe" etc. as further development
        print("4. Exit")
        choice = input("Choose an option: ").strip()

        if choice == '1':
            add_ingredient()
        elif choice == '2':
            add_recipe()
        elif choice == '3':
            calculate_recipe_cost()
        elif choice == '4':
            print("Exiting.")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == '__main__':
    main()