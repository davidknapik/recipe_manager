import sqlite3
from flask import Flask, render_template, request, url_for, redirect, flash, g

# --- App and Database Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key' # Needed for flashing messages
DATABASE = 'recipes.db'

def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # This allows accessing columns by name
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- Helper Functions ---
def calculate_recipe_cost(recipe_id):
    """Calculates the total cost of a recipe based on the most recent ingredient prices."""
    db = get_db()
    ingredients = db.execute('''
        SELECT i.name, ri.amount_needed, ri.unit_needed
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id = ?
    ''', (recipe_id,)).fetchall()

    total_cost = 0.0
    cost_breakdown = []

    for item in ingredients:
        latest_purchase = db.execute('''
            SELECT * FROM ingredient_purchases
            WHERE ingredient_id = (SELECT id FROM ingredients WHERE name = ?)
            ORDER BY purchase_date DESC
            LIMIT 1
        ''', (item['name'],)).fetchone()

        if not latest_purchase:
            cost_breakdown.append({'name': item['name'], 'cost': 'N/A', 'note': 'No purchase history'})
            continue

        package_amount = latest_purchase['package_amount']
        # Simple unit conversion
        if latest_purchase['package_unit'].lower() in ['kg', 'kilo'] and item['unit_needed'].lower() == 'g':
            package_amount *= 1000
        elif latest_purchase['package_unit'].lower() in ['l', 'litre'] and item['unit_needed'].lower() == 'ml':
            package_amount *= 1000
        
        cost_per_unit = latest_purchase['price'] / package_amount
        ingredient_cost = item['amount_needed'] * cost_per_unit
        total_cost += ingredient_cost
        cost_breakdown.append({'name': f"{item['amount_needed']} {item['unit_needed']} of {item['name']}", 'cost': f'{ingredient_cost:.2f}'})

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
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('INSERT INTO recipes (name, preparation_instructions, bake_instructions, yield) VALUES (?, ?, ?, ?)',
                           (name, prep, bake, yld))
            db.commit()
            flash('Recipe created successfully! Now add ingredients.', 'success')
            return redirect(url_for('index'))
            
    return render_template('recipe_form.html')

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
            flash('Recipe updated successfully!', 'success')
            return redirect(url_for('recipe_detail', recipe_id=recipe_id))

    return render_template('recipe_form.html', recipe=recipe)


# --- Ingredient Routes ---

@app.route('/ingredients')
def list_ingredients():
    db = get_db()
    # Join to get the ingredient name
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
            
            # Get or create the base ingredient
            cursor.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
            result = cursor.fetchone()
            if result:
                ingredient_id = result['id']
            else:
                cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (name,))
                ingredient_id = cursor.lastrowid

            # Insert the purchase record
            cursor.execute('''
                INSERT INTO ingredient_purchases (ingredient_id, store, package_amount, package_unit, price, purchase_date, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (ingredient_id, store, float(package_amount), package_unit, float(price), purchase_date, expiry_date))
            
            db.commit()
            flash('Ingredient purchase added successfully!', 'success')
            return redirect(url_for('list_ingredients'))

    return render_template('ingredient_form.html')


if __name__ == '__main__':
    # Before running, make sure the database exists.
    # You can run the setup_database() function from the previous script once.
    app.run(debug=True) # debug=True reloads server on code changes