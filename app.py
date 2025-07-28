import sqlite3
from flask import Flask, render_template, request, url_for, redirect, flash, g

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
    ('oz', 'Ounces (oz)', 'weight'),
    ('ml', 'Milliliters (ml)', 'volume'),
    ('l', 'Liters (l)', 'volume'),
    ('fl.oz', 'Fluid Ounces (fl.oz)', 'volume'),
    ('tsp', 'Teaspoon (tsp)', 'volume'),
    ('Tbsp', 'Tablespoon (Tbsp)', 'volume'),
    ('Cup', 'Cup(s)', 'volume'),
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
    # Volume (base: ml)
    'ml': 1.0,
    'l': 1000.0,
    'tsp': 4.929,
    'Tbsp': 14.787,
    'Cup': 236.588,
    'fl.oz': 29.574,
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

        if not latest_purchase:
            cost_breakdown.append({'name': item['name'], 'cost': 'N/A', 'note': 'No purchase history'})
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
            'name': f"{item['amount_needed']} {recipe_unit} of {item['name']}",
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
    ingredients = db.execute('''
        SELECT i.name, ri.amount_needed, ri.unit_needed
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id = ?
    ''', (recipe_id,)).fetchall()
    cost_info = calculate_recipe_cost(recipe_id)
    return render_template('recipe_detail.html', recipe=recipe, ingredients=ingredients, cost_info=cost_info)

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

# --- Base Ingredient Management Routes (NEW) ---

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
        # Use .get() to gracefully handle empty input, defaulting to None
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
    purchases = db.execute('''
        SELECT ip.*, i.name 
        FROM ingredient_purchases ip
        JOIN ingredients i ON ip.ingredient_id = i.id
        ORDER BY i.name, ip.purchase_date DESC
    ''').fetchall()
    return render_template('ingredients.html', purchases=purchases)

@app.route('/ingredient/add', methods=('GET', 'POST'))
def add_ingredient():
    if request.method == 'POST':
        name = request.form['name'].strip()
        store = request.form['store']
        package_amount = request.form['package_amount']
        package_unit = request.form['package_unit']
        price = request.form['price']
        purchase_date = request.form['purchase_date']
        expiry_date = request.form['expiry_date']

        if not all([name, store, package_amount, package_unit, price, purchase_date]):
            flash('Please fill all required fields.', 'error')
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
            result = cursor.fetchone()
            if result:
                ingredient_id = result['id']
            else:
                cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (name,))
                ingredient_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO ingredient_purchases (ingredient_id, store, package_amount, package_unit, price, purchase_date, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (ingredient_id, store, float(package_amount), package_unit, float(price), purchase_date, expiry_date))
            db.commit()
            flash('Ingredient purchase added successfully!', 'success')
            return redirect(url_for('list_ingredients'))
            
    return render_template('ingredient_form.html', units=UNITS)

@app.route('/ingredient/edit/<int:purchase_id>', methods=('GET', 'POST'))
def edit_ingredient(purchase_id):
    db = get_db()
    purchase = db.execute('''
        SELECT ip.id, ip.store, ip.package_amount, ip.package_unit, ip.price, ip.purchase_date, ip.expiry_date, i.name
        FROM ingredient_purchases ip
        JOIN ingredients i ON ip.ingredient_id = i.id
        WHERE ip.id = ?
    ''', (purchase_id,)).fetchone()

    if purchase is None:
        flash('Ingredient purchase not found.', 'error')
        return redirect(url_for('list_ingredients'))

    if request.method == 'POST':
        name = request.form['name'].strip()
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
            SET ingredient_id = ?, store = ?, package_amount = ?, package_unit = ?,
                price = ?, purchase_date = ?, expiry_date = ?
            WHERE id = ?
        ''', (ingredient_id, store, float(package_amount), package_unit, float(price),
              purchase_date, expiry_date, purchase_id))
        db.commit()

        flash('Ingredient purchase updated successfully!', 'success')
        return redirect(url_for('list_ingredients'))

    return render_template('ingredient_form.html', purchase=purchase, units=UNITS)

if __name__ == '__main__':
    app.run(debug=True)