import sqlite3
import json
from flask import Flask, render_template, request, url_for, redirect, flash, g
from datetime import date

# --- App and Database Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
DATABASE = 'recipes.db'

# --- Unit Definitions and Conversion Logic ---

# Define a single source of truth for all units and their "type" (dimension)
# (abbreviation, full name, dimension)
UNITS = [
    ('g', 'Grams (g)', 'weight'),
    ('kg', 'Kilograms (kg)', 'weight'),
    ('lb', 'Pounds (lb)', 'weight'),
    ('oz', 'Ounces (oz)', 'weight'),
    ('ml', 'Milliliters (ml)', 'volume'),
    ('l', 'Liters (l)', 'volume'),
    ('fl.oz', 'Fluid Ounces-US (fl.oz)', 'volume'),
    ('Gal', 'Gallon(s)-US (gal)', 'volume'),
    ('pnt', 'Pint(s)-US (pnt)', 'volume'),
    ('qrt', 'Quart(s)-US (qrt)', 'volume'),
    ('tsp', 'Teaspoon-US (tsp)', 'volume'),
    ('Tbsp', 'Tablespoon-US (Tbsp)', 'volume'),
    ('Cup', 'Cup(s)-US', 'volume'),
    ('ea', 'Each (ea)', 'quantity'),
    ('pack', 'Pack', 'quantity'),
]

# Create a dictionary for quick dimension lookups: {'g': 'weight', 'kg': 'weight', ...}
UNIT_DIMENSIONS = {unit[0]: unit[2] for unit in UNITS}

# Define conversion factors TO a standard base unit (g for weight, ml for volume)
# This is key for comparing different units of the same dimension.
CONVERSIONS_TO_BASE = {
    # Weight (base: g)
    'g': 1.0,
    'kg': 1000.0,
    'oz': 28.35,
    'lb': 453.59,
    # Volume (base: ml)
    'ml': 1.0,
    'l': 1000.0,
    'tsp': 4.929,
    'Tbsp': 14.787,
    'Cup': 236.588,
    'fl.oz': 29.574,
    'gal': 3785.41,
    'pnt': 473.18,
    'qrt': 946.35,
    # Quantity (base: ea) - 'pack' is treated specially in the logic
    'ea': 1.0,
    'pack': 1.0,
}

# --- Database Connection Handling ---

def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- Helper Functions ---

def calculate_recipe_cost(recipe_id):
    """
    Calculates the total cost of a recipe using a robust unit conversion system.
    """
    db = get_db()
    ingredients = db.execute('''
        SELECT i.name, ri.amount_needed, ri.unit_needed
        FROM recipe_ingredients ri
        -- Also fetch the ingredient's ID and density
        JOIN ingredients i ON ri.ingredient_id = i.id 
        WHERE ri.recipe_id = ?
    ''', (recipe_id,)).fetchall()

    total_cost = 0.0
    cost_breakdown = []

    for item in ingredients:
        recipe_unit = item['unit_needed']
        recipe_amount = item['amount_needed']
        
        latest_purchase = db.execute('''
            SELECT p.*, i.density_g_ml FROM ingredient_purchases p
            JOIN ingredients i ON p.ingredient_id = i.id
            WHERE ingredient_id = (SELECT id FROM ingredients WHERE name = ?)
            ORDER BY purchase_date DESC
            LIMIT 1
        ''', (item['name'],)).fetchone()

        # --- Generate display name with gram equivalent ---
        grams = None
        dimension = UNIT_DIMENSIONS.get(recipe_unit)

        if dimension == 'weight' and recipe_unit != 'g':
            grams = recipe_amount * CONVERSIONS_TO_BASE[recipe_unit]
        elif dimension == 'volume' and latest_purchase and latest_purchase['density_g_ml']:
            base_ml = recipe_amount * CONVERSIONS_TO_BASE[recipe_unit]
            grams = base_ml * latest_purchase['density_g_ml']

        display_grams_str = f" ({round(grams)}g)" if grams is not None else ""
        display_name = f"{recipe_amount} {recipe_unit}{display_grams_str} of {item['name']}"
        # --- End of display name generation ---

        if not latest_purchase:
            cost_breakdown.append({'name': display_name, 'cost': 'N/A', 'note': 'No purchase history'})
            continue

        purchase_unit = latest_purchase['package_unit']
        purchase_amount = latest_purchase['package_amount']
        purchase_price = latest_purchase['price']
        
        # Check if units are compatible (same dimension)
        recipe_dim = UNIT_DIMENSIONS.get(recipe_unit)
        purchase_dim = UNIT_DIMENSIONS.get(purchase_unit)

        cost_note = ""
        ingredient_cost = 0.0 # Default cost is 0

        # Case 1: Dimensions are the same (weight-to-weight, volume-to-volume)
        if recipe_dim == purchase_dim and recipe_dim is not None:
            if recipe_dim == 'quantity':
                items_in_package = purchase_amount if purchase_unit == 'pack' else 1
                cost_per_item = purchase_price / items_in_package
                ingredient_cost = recipe_amount * cost_per_item
            else: # weight or volume
                purchase_amount_in_base = purchase_amount * CONVERSIONS_TO_BASE[purchase_unit]
                cost_per_base_unit = purchase_price / purchase_amount_in_base
                recipe_amount_in_base = recipe_amount * CONVERSIONS_TO_BASE[recipe_unit]
                ingredient_cost = recipe_amount_in_base * cost_per_base_unit
        
        # Case 2: Dimensions are different, requiring density conversion
        elif recipe_dim != purchase_dim and recipe_dim is not None and purchase_dim is not None:
            density = latest_purchase['density_g_ml']
            if density is None:
                cost_note = f"Conversion from {purchase_dim} to {recipe_dim} requires a density value."
            else:
                # Standardize both sides to grams and calculate cost
                if purchase_dim == 'weight':
                    purchase_grams = purchase_amount * CONVERSIONS_TO_BASE[purchase_unit]
                    recipe_ml = recipe_amount * CONVERSIONS_TO_BASE[recipe_unit]
                    recipe_grams = recipe_ml * density
                else: # purchase_dim must be 'volume'
                    purchase_ml = purchase_amount * CONVERSIONS_TO_BASE[purchase_unit]
                    purchase_grams = purchase_ml * density
                    recipe_grams = recipe_amount * CONVERSIONS_TO_BASE[recipe_unit]
                
                cost_per_gram = purchase_price / purchase_grams
                ingredient_cost = recipe_grams * cost_per_gram
        elif recipe_dim == 'quantity' or purchase_dim == 'quantity':
            cost_note = f"Cannot convert between '{purchase_dim}' and '{recipe_dim}'."
        else:
            cost_note = f"Cannot convert from {purchase_unit} to {recipe_unit}"
        
        total_cost += ingredient_cost
        cost_breakdown.append({
            'name': display_name,
            'cost': f'{ingredient_cost:.2f}',
            'note': cost_note
        })

    return {'total': total_cost, 'breakdown': cost_breakdown}

# --- Recipe Routes ---

@app.route('/')
def index():
    db = get_db()
    recipes = db.execute('SELECT * FROM recipes ORDER BY name').fetchall()
    return render_template('index.html', recipes=recipes)

@app.route('/recipe/<int:recipe_id>')
def recipe_detail(recipe_id):
    db = get_db()
    recipe = db.execute('SELECT * FROM recipes WHERE id = ?', (recipe_id,)).fetchone()
    
    # Fetch ingredients along with their density for gram calculation
    ingredients_raw = db.execute('''
        SELECT i.name, i.density_g_ml, ri.amount_needed, ri.unit_needed
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id = ?
    ''', (recipe_id,)).fetchall()

    # Process ingredients to add a display field for the gram equivalent
    ingredients_processed = []
    for item in ingredients_raw:
        item_dict = dict(item) # Convert Row object to a mutable dict
        unit = item_dict['unit_needed']
        amount = item_dict['amount_needed']
        density = item_dict['density_g_ml']
        dimension = UNIT_DIMENSIONS.get(unit)
        
        grams = None # Default to no gram display
        
        if dimension == 'weight' and unit != 'g':
            grams = amount * CONVERSIONS_TO_BASE.get(unit, 0)
        elif dimension == 'volume' and density:
            base_ml = amount * CONVERSIONS_TO_BASE.get(unit, 0)
            grams = base_ml * density
            
        if grams is not None:
            # Add a formatted string to the dictionary for the template
            item_dict['display_grams'] = f"({round(grams)}g)"
        else:
            item_dict['display_grams'] = "" # Keep it empty if no conversion
            
        ingredients_processed.append(item_dict)

    cost_info = calculate_recipe_cost(recipe_id)
    return render_template('recipe_detail.html', 
                           recipe=recipe, 
                           ingredients=ingredients_processed, 
                           cost_info=cost_info)

@app.route('/recipe/add', methods=('GET', 'POST'))
def add_recipe():
    if request.method == 'POST':
        name = request.form['name']
        prep = request.form['preparation_instructions']
        bake = request.form['bake_instructions']
        yld = request.form['yield']

        if not name:
            flash('Recipe name is required!', 'error')
            return render_template('recipe_form.html', units=UNITS)
        
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute('INSERT INTO recipes (name, preparation_instructions, bake_instructions, yield) VALUES (?, ?, ?, ?)',
                           (name, prep, bake, yld))
            db.commit()
            new_recipe_id = cursor.lastrowid
            flash('Recipe created successfully! Now add ingredients.', 'success')
            return redirect(url_for('edit_recipe', recipe_id=new_recipe_id))
        except sqlite3.IntegrityError:
            flash('A recipe with this name already exists.', 'error')
            return render_template('recipe_form.html', recipe={'name': name, 'preparation_instructions': prep, 'bake_instructions': bake, 'yield': yld}, units=UNITS)
            
    return render_template('recipe_form.html', units=UNITS)

@app.route('/recipe/edit/<int:recipe_id>', methods=('GET', 'POST'))
def edit_recipe(recipe_id):
    db = get_db()
    recipe = db.execute('SELECT * FROM recipes WHERE id = ?', (recipe_id,)).fetchone()

    if request.method == 'POST':
        name = request.form['name']
        prep = request.form['preparation_instructions']
        bake = request.form['bake_instructions']
        yld = request.form['yield']

        if not name:
            flash('Recipe name is required!', 'error')
        else:
            db.execute('''
                UPDATE recipes SET name = ?, preparation_instructions = ?, bake_instructions = ?, yield = ?
                WHERE id = ?
            ''', (name, prep, bake, yld, recipe_id))
            db.commit()
            flash('Recipe details updated successfully!', 'success')
            return redirect(url_for('edit_recipe', recipe_id=recipe_id))

    recipe_ingredients = db.execute('''
        SELECT i.id, i.name, ri.amount_needed, ri.unit_needed
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id = ? ORDER BY i.name
    ''', (recipe_id,)).fetchall()

    all_ingredients = db.execute('SELECT * FROM ingredients ORDER BY name').fetchall()

    return render_template('recipe_form.html',
                           recipe=recipe,
                           recipe_ingredients=recipe_ingredients,
                           all_ingredients=all_ingredients,
                           units=UNITS)

@app.route('/recipe/delete/<int:recipe_id>', methods=('POST',))
def delete_recipe(recipe_id):
    """Deletes a recipe and its associated ingredients from the database."""
    db = get_db()
    
    # First, delete the links in the recipe_ingredients table
    db.execute('DELETE FROM recipe_ingredients WHERE recipe_id = ?', (recipe_id,))
    
    # Then, delete the recipe itself
    db.execute('DELETE FROM recipes WHERE id = ?', (recipe_id,))
    
    db.commit()
    
    flash('Recipe has been deleted successfully.', 'success')
    return redirect(url_for('index'))


@app.route('/recipe/<int:recipe_id>/add_ingredient', methods=('POST',))
def add_ingredient_to_recipe(recipe_id):
    db = get_db()
    ingredient_id = request.form['ingredient_id']
    amount = request.form['amount_needed']
    unit = request.form['unit_needed']

    if not all([ingredient_id, amount, unit]):
        flash('All ingredient fields are required.', 'error')
    else:
        try:
            db.execute('''
                INSERT INTO recipe_ingredients (recipe_id, ingredient_id, amount_needed, unit_needed)
                VALUES (?, ?, ?, ?)
            ''', (recipe_id, int(ingredient_id), float(amount), unit))
            db.commit()
            flash('Ingredient added to recipe.', 'success')
        except sqlite3.IntegrityError:
            flash('This ingredient is already in the recipe.', 'error')

    return redirect(url_for('edit_recipe', recipe_id=recipe_id))

@app.route('/recipe/<int:recipe_id>/delete_ingredient/<int:ingredient_id>', methods=('POST',))
def delete_ingredient_from_recipe(recipe_id, ingredient_id):
    db = get_db()
    db.execute('DELETE FROM recipe_ingredients WHERE recipe_id = ? AND ingredient_id = ?', (recipe_id, ingredient_id))
    db.commit()
    flash('Ingredient removed from recipe.', 'success')
    return redirect(url_for('edit_recipe', recipe_id=recipe_id))


@app.route('/recipe/<int:recipe_id>/edit_ingredient/<int:ingredient_id>', methods=('GET', 'POST'))
def edit_recipe_ingredient(recipe_id, ingredient_id):
    db = get_db()

    if request.method == 'POST':
        new_ingredient_id = request.form['ingredient_id']
        amount_needed = request.form['amount_needed']
        unit_needed = request.form['unit_needed']

        try:
            db.execute('''
                UPDATE recipe_ingredients
                SET ingredient_id = ?, amount_needed = ?, unit_needed = ?
                WHERE recipe_id = ? AND ingredient_id = ?
            ''', (new_ingredient_id, amount_needed, unit_needed, recipe_id, ingredient_id))
            db.commit()
            flash('Recipe ingredient updated successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Could not update: That ingredient is already in the recipe.', 'error')
        
        return redirect(url_for('edit_recipe', recipe_id=recipe_id))

    recipe_ingredient = db.execute('''
        SELECT * FROM recipe_ingredients WHERE recipe_id = ? AND ingredient_id = ?
    ''', (recipe_id, ingredient_id)).fetchone()

    if recipe_ingredient is None:
        flash('Recipe ingredient not found.', 'error')
        return redirect(url_for('edit_recipe', recipe_id=recipe_id))

    all_ingredients = db.execute('SELECT * FROM ingredients ORDER BY name').fetchall()

    return render_template('edit_recipe_ingredient.html', recipe_id=recipe_id,
                           recipe_ingredient=recipe_ingredient, all_ingredients=all_ingredients, units=UNITS)

# --- Base Ingredient Management Routes ---

@app.route('/ingredients/base')
def list_base_ingredients():
    """Lists all unique ingredients for editing their base properties (like density)."""
    db = get_db()
    ingredients = db.execute('SELECT * FROM ingredients ORDER BY name').fetchall()
    return render_template('base_ingredients.html', ingredients=ingredients)

@app.route('/ingredient/base/edit/<int:ingredient_id>', methods=('GET', 'POST'))
def edit_base_ingredient(ingredient_id):
    """Handles editing a base ingredient's name and density."""
    db = get_db()
    ingredient = db.execute('SELECT * FROM ingredients WHERE id = ?', (ingredient_id,)).fetchone()

    if ingredient is None:
        flash('Base ingredient not found.', 'error')
        return redirect(url_for('list_base_ingredients'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        density_str = request.form.get('density_g_ml')
        density = float(density_str) if density_str else None

        db.execute('UPDATE ingredients SET name = ?, density_g_ml = ? WHERE id = ?',
                   (name, density, ingredient_id))
        db.commit()
        flash(f"'{name}' has been updated.", 'success')
        return redirect(url_for('list_base_ingredients'))

    return render_template('base_ingredient_form.html', ingredient=ingredient)


# --- Ingredient Purchase Routes ---

@app.route('/ingredients')
def list_ingredients():
    db = get_db()

    page = request.args.get('page', 1, type=int)
    per_page = 25
    offset = (page - 1) * per_page

    sort_by = request.args.get('sort_by', 'purchase_date')
    order = request.args.get('order', 'desc')

    allowed_sort_columns = {
        'name': 'i.name',
        'store': 'ip.store',
        'purchase_date': 'ip.purchase_date'
    }
    sort_column = allowed_sort_columns.get(sort_by, 'ip.purchase_date')
    
    if order not in ['asc', 'desc']:
        order = 'desc'

    query = f'''
        SELECT ip.*, i.name
        FROM ingredient_purchases ip JOIN ingredients i ON ip.ingredient_id = i.id
        ORDER BY {sort_column} {order}
        LIMIT ? OFFSET ?
    '''
    purchases = db.execute(query, (per_page, offset)).fetchall()

    total_purchases = db.execute('SELECT COUNT(id) FROM ingredient_purchases').fetchone()[0]
    total_pages = (total_purchases + per_page - 1) // per_page

    return render_template('ingredients.html', purchases=purchases,
                           page=page, total_pages=total_pages,
                           sort_by=sort_by, order=order)

@app.route('/ingredient/add', methods=('GET', 'POST'))
def add_ingredient():
    db = get_db()
    if request.method == 'POST':
        # This POST logic is unchanged
        name = request.form['name'].strip()
        brand = request.form['brand'].strip()
        store = request.form['store']
        package_amount = request.form['package_amount']
        package_unit = request.form['package_unit']
        price = request.form['price']
        purchase_date = request.form['purchase_date']
        expiry_date = request.form['expiry_date']

        if not all([name, store, package_amount, package_unit, price, purchase_date]):
            flash('Please fill all required fields.', 'error')
        else:
            cursor = db.cursor()
            cursor.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
            result = cursor.fetchone()
            if result:
                ingredient_id = result['id']
            else:
                cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (name,))
                ingredient_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO ingredient_purchases (ingredient_id, brand, store, package_amount, package_unit, price, purchase_date, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ingredient_id, brand, store, float(package_amount), package_unit, float(price), purchase_date, expiry_date))
            db.commit()
            flash('Ingredient purchase added successfully!', 'success')
            return redirect(url_for('list_ingredients'))
    
    # For a GET request, prepare data for the auto-fill form
    all_ingredients = db.execute('SELECT id, name FROM ingredients ORDER BY name').fetchall()
    
    latest_purchases_data = {}
    for ingredient in all_ingredients:
        latest_purchase = db.execute('''
            SELECT brand, store, package_amount, package_unit, price
            FROM ingredient_purchases
            WHERE ingredient_id = ?
            ORDER BY purchase_date DESC
            LIMIT 1
        ''', (ingredient['id'],)).fetchone()
        
        if latest_purchase:
            # Store the data using the ingredient's name as the key
            latest_purchases_data[ingredient['name']] = {
                'brand': latest_purchase['brand'],
                'store': latest_purchase['store'],
                'package_amount': latest_purchase['package_amount'],
                'package_unit': latest_purchase['package_unit'],
                'price': latest_purchase['price']
            }
            
    return render_template('ingredient_form.html',
                           units=UNITS,
                           today_date=date.today().isoformat(),
                           all_ingredients=all_ingredients,
                           # Pass the raw dictionary, NOT a JSON string
                           latest_purchases_data=latest_purchases_data)

@app.route('/ingredient/edit/<int:purchase_id>', methods=('GET', 'POST'))
def edit_ingredient(purchase_id):
    db = get_db()
    purchase = db.execute('''
        SELECT ip.id, ip.brand, ip.store, ip.package_amount, ip.package_unit, ip.price, ip.purchase_date, ip.expiry_date, i.name
        FROM ingredient_purchases ip
        JOIN ingredients i ON ip.ingredient_id = i.id
        WHERE ip.id = ?
    ''', (purchase_id,)).fetchone()

    if purchase is None:
        flash('Ingredient purchase not found.', 'error')
        return redirect(url_for('list_ingredients'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        brand = request.form['brand'].strip()
        store = request.form['store']
        package_amount = request.form['package_amount']
        package_unit = request.form['package_unit']
        price = request.form['price']
        purchase_date = request.form['purchase_date']
        expiry_date = request.form['expiry_date']

        if not all([name, store, package_amount, package_unit, price, purchase_date]):
            flash('Please fill all required fields.', 'error')
            return render_template('ingredient_form.html', purchase=purchase, units=UNITS)

        cursor = db.cursor()
        cursor.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
        result = cursor.fetchone()
        if result:
            ingredient_id = result['id']
        else:
            cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (name,))
            ingredient_id = cursor.lastrowid

        cursor.execute('''
            UPDATE ingredient_purchases
            SET ingredient_id = ?, brand = ?, store = ?, package_amount = ?, package_unit = ?,
                price = ?, purchase_date = ?, expiry_date = ?
            WHERE id = ?
        ''', (ingredient_id, brand, store, float(package_amount), package_unit, float(price),
              purchase_date, expiry_date, purchase_id))
        db.commit()

        flash('Ingredient purchase updated successfully!', 'success')
        return redirect(url_for('list_ingredients'))

    return render_template('ingredient_form.html', purchase=purchase, units=UNITS)

if __name__ == '__main__':
    app.run(debug=True)