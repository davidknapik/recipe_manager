# Recipe Cost Manager

A simple but powerful web application for managing your recipes and tracking the cost of ingredients. Built with Python and Flask, this tool helps home cooks and bakers understand the real cost of their creations by tracking ingredient purchases and calculating recipe costs based on precise measurements.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Table of Contents

- [Key Features](#key-features)
- [Screenshots](#screenshots)
- [Technology Stack](#technology-stack)
- [Setup and Installation](#setup-and-installation)
- [Usage](#usage)
- [Database Schema](#database-schema)
- [Future Enhancements](#future-enhancements)
- [License](#license)

## Key Features

*   **Recipe Management**: Create, view, and edit recipes with detailed preparation and baking instructions.
*   **Ingredient Database**: Track individual ingredient purchases from different stores, including package size, price, and purchase/expiry dates.
*   **Cost Calculation**: Automatically calculates the cost of a recipe based on the quantity of ingredients used and their most recent purchase price.
*   **Unit Conversion**: Robust system to convert between different units of the same dimension (e.g., grams to kilograms, teaspoons to liters), ensuring accurate cost analysis.
*   **Web-Based UI**: A clean and intuitive web front-end built with Flask for easy data entry and viewing on any device with a browser.
*   **Data Integrity**: Utilizes dropdown menus for units to prevent user input errors and ensure consistency.

## Screenshots

*(Here is where you can add screenshots of your running application)*

**1. Home Page - Recipe List**
*A clean list of all your saved recipes.*
`![Recipe List](path/to/your/screenshot_recipe_list.png)`

**2. Recipe Detail Page**
*View recipe instructions, ingredients, and the calculated cost breakdown.*
`![Recipe Detail](path/to/your/screenshot_recipe_detail.png)`

**3. Edit Recipe & Manage Ingredients**
*The dynamic form for editing recipe details and adding/removing ingredients.*
`![Edit Recipe Form](path/to/your/screenshot_edit_recipe.png)`

**4. Ingredient Purchase List**
*A comprehensive log of all your ingredient purchases.*
`![Ingredient List](path/to/your/screenshot_ingredients.png)`

## Technology Stack

*   **Backend**: Python 3
*   **Web Framework**: Flask
*   **Database**: SQLite 3 (a lightweight, file-based database)
*   **Frontend**: Basic HTML, CSS, and Jinja2 templating

No external packages are required besides **Flask**.

## Setup and Installation

Follow these steps to get the application running on your local machine.

**1. Prerequisites**
*   Make sure you have Python 3 installed. You can check by running `python --version` or `python3 --version`.

**2. Clone the Repository**
```bash
git clone https://github.com/davidknapik/recipe_manager.git
cd recipe_manager
```

**3. (Recommended) Create a Virtual Environment**
It's best practice to create a virtual environment to keep project dependencies isolated.
```bash
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
.\venv\Scripts\activate
```

**4. Install Dependencies**
This project only requires Flask.
```bash
pip install Flask
```

or using the requirements.txt
```bash
pip install -r requirements.txt
```

**5. Initialize the Database**
The application uses a SQLite database named `recipes.db`. If you are starting fresh, you need to create the database and its tables.

You can do this by running the initial recipe_manager.py Python script from the command line (if you have the `setup_database()` function from our earlier discussions) or by ensuring the Flask app creates it on first run (the current `app.py` does not include a setup command, so you might need a separate setup script).

*Using the `setup_db.py` script:*

```bash
python setup_db.py
```

**6. Run the Application**
```bash
flask run
# Or, in debug mode:
python app.py
```
The application will be available at `http://127.0.0.1:5000` in your web browser.

## Usage

1.  **Navigate to the "Ingredients" Page**: Before creating recipes, you need to log your ingredient purchases. Click "Add New Purchase" and fill in the details for items like flour, eggs, etc.
2.  **Navigate to the "Manage Base Ingredients" Page**: Click an ingredient and verify or update its weight to volume information in g/ml. 
3.  **Navigate to the "Recipes" Page**: Click "Add New Recipe".
4.  **Create the Recipe**: Fill in the name and instructions, then click "Create Recipe and Add Ingredients".
5.  **Add Ingredients to the Recipe**: You will be redirected to the edit page. Here, you can select ingredients from your database, specify the amount needed for the recipe, and add them one by one.
6.  **View the Final Recipe**: Once you've added all ingredients, click "View Saved Recipe" to see the full details, including the final calculated cost.

## Database Schema

The application uses four SQL tables to organize data.

**`ingredients`**
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary Key |
| `name` | TEXT | Unique name of the ingredient (e.g., "All-Purpose Flour") |
| `density_g_ml` | REAL | Density of ingredient in g / ml |

**`ingredient_purchases`**
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary Key |
| `ingredient_id` | INTEGER | Foreign Key to `ingredients.id` |
| `store` | TEXT | Store of purchase (e.g., "Tesco") |
| `package_amount` | REAL | Size of the package (e.g., 2, 18) |
| `package_unit` | TEXT | Unit of the package (e.g., "kg", "pack") |
| `price` | REAL | Cost of the package |
| `purchase_date` | TEXT | Date of purchase ("YYYY-MM-DD") |
| `expiry_date` | TEXT | Expiration date ("YYYY-MM-DD") |
| `brand` | TEXT | Manufacturer Name / Brand Name of product |

**`recipes`**
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary Key |
| `name` | TEXT | Unique name of the recipe |
| `preparation_instructions`| TEXT | Main preparation steps |
| `bake_instructions` | TEXT | Baking/cooking temperature and duration |
| `yield` | TEXT | How many servings it produces |

**`recipe_ingredients`** (Linking Table)
| Column | Type | Description |
|---|---|---|
| `recipe_id` | INTEGER | Foreign Key to `recipes.id` |
| `ingredient_id` | INTEGER | Foreign Key to `ingredients.id` |
| `amount_needed` | REAL | Amount of ingredient required |
| `unit_needed` | TEXT | Unit for the recipe (e.g., "g", "ml", "Cup")|
| `sort-order` | INTEGER | Sort order to be used in the recipe |

## Future Enhancements

- [ ] **User Authentication**: Add user accounts to keep recipes private.
- [ ] **Shopping List Generator**: Create a shopping list based on a selected recipe or a meal plan.
- [ ] **Recipe Tagging**: Add tags (e.g., "Dessert", "Vegan", "Quick") for easier filtering.
- [ ] **Image Uploads**: Allow users to upload a photo for each recipe.
- [ ] **REST API**: Develop an API to allow other applications to interact with the recipe data.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.