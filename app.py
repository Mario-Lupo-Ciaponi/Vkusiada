from flask import Flask, render_template, request, redirect, flash, url_for, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import requests

app = Flask(__name__)
app.secret_key = '13en2oqiw3uedh23oey8'
app.permanent_session_lifetime = timedelta(days=7)

db_config = {
    'database': 'flask_app',
    'user': 'root',
    'password': 'mS1029384756,.F!',
    'host': 'localhost',
    'port': '3306'
}


def get_db_connection():
    return mysql.connector.connect(**db_config)


def get_all_ingredients(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT i.id, i.name 
            FROM user_ingredients ui
            JOIN ingredients i ON ui.ingredient_id = i.id
            WHERE ui.user_id = %s
            """,
            (user_id,)
        )
        return cursor.fetchall()  # This now returns a list of dictionaries with 'id' and 'name'
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return []
    finally:
        cursor.close()
        connection.close()



def get_recipes_from_ingredients(ingredients):
    all_recipes = set()

    for ingredient in ingredients:
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ingredient}"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            meals = data.get('meals', [])
            if meals:
                for meal in meals:
                    all_recipes.add((meal['idMeal'], meal['strMeal'], meal['strMealThumb']))
        else:
            print(f"Error fetching data for ingredient: {ingredient}")

    return list(all_recipes)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if not username or not email or not password:
            flash("All fields are required!", "danger")
            return redirect('/register')

        hashed_password = generate_password_hash(password)

        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed_password)
            )
            connection.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect('/login')
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
        finally:
            cursor.close()
            connection.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if not email or not password:
            flash("Email and password are required!", "danger")
            return redirect('/login')

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                session["user"] = user['id']
                return redirect(url_for('home_page'))
            else:
                flash("Invalid email or password!", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect('/login')

    return render_template('login.html')


@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    api_url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={recipe_id}"
    response = requests.get(api_url)
    recipe = response.json().get("meals")[0]

    if recipe:
        ingredients = []
        for i in range(1, 21):
            ingredient = recipe.get(f"strIngredient{i}")
            measure = recipe.get(f"strMeasure{i}")
            if ingredient and measure:
                ingredients.append(f"{measure} {ingredient}")

        return render_template("recipe-detail.html", recipe=recipe, ingredients=ingredients)
    else:
        return render_template("recipe-detail.html", recipe=None)

@app.route("/about")
def about_page():
    return render_template("about-page.html")

@app.route("/delete-ingredient/<int:ingredient_id>", methods=["POST"])
def delete_ingredient(ingredient_id):
    if "user" not in session:
        flash("You need to be logged in to delete ingredients.", "danger")
        return redirect(url_for("login"))

    user_id = session["user"]

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        # Delete the ingredient for the specific user
        cursor.execute(
            "DELETE FROM user_ingredients WHERE user_id = %s AND ingredient_id = %s",
            (user_id, ingredient_id)
        )
        connection.commit()
        flash("Ingredient deleted successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Error deleting ingredient: {err}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("ingredients_page"))



@app.route("/add-ingredients", methods=["GET", "POST"])
def add_ingredients_page():
    if "user" not in session:
        return redirect(url_for("register"))

    user_id = session["user"]

    if request.method == "POST":
        new_ingredients = request.form["ingredients"].strip()

        if not new_ingredients:
            flash("Please provide ingredients to add.", "danger")
            return redirect(url_for("add_ingredients_page"))

        # Split new ingredients by commas and clean them
        new_ingredients = [ingredient.strip() for ingredient in new_ingredients.split(",")]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)  # Use dictionary cursor here
        try:
            for ingredient in new_ingredients:
                # Ensure the ingredient exists in the ingredients table
                cursor.execute(
                    "INSERT IGNORE INTO ingredients (name) VALUES (%s)",
                    (ingredient,)
                )
                connection.commit()

                # Fetch the ingredient ID
                cursor.execute(
                    "SELECT id FROM ingredients WHERE name = %s",
                    (ingredient,)
                )
                ingredient_row = cursor.fetchone()
                ingredient_id = ingredient_row["id"]  # Access by key now, since it's a dictionary

                # Insert into user_ingredients table
                cursor.execute(
                    "INSERT IGNORE INTO user_ingredients (user_id, ingredient_id) VALUES (%s, %s)",
                    (user_id, ingredient_id)
                )
                connection.commit()

            flash("Ingredients added successfully!", "success")
        except mysql.connector.Error as err:
            flash(f"Error adding ingredients: {err}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for("ingredients_page"))

    return render_template("add-ingredients.html")



@app.route("/ingredients")
def ingredients_page():
    if "user" not in session:
        return redirect(url_for("register"))

    user_id = session["user"]

    # Fetch the username to pass to the template
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        username = user["username"] if user else "Unknown"
    finally:
        cursor.close()
        connection.close()

    # Get all ingredients for the user
    ingredients = get_all_ingredients(user_id)

    # Pass 'name' (username) to the template
    return render_template("ingredients-page.html", name=username, ingredients=ingredients)



@app.route("/add-recipe", methods=["GET", "POST"])
def add_recipe():
    if "user" not in session:
        flash("You need to be logged in to add recipes.", "danger")
        return redirect(url_for("login"))

    user_id = session["user"]

    if request.method == "POST":
        recipe_name = request.form.get("recipe_name")
        ingredients = request.form.get("ingredients")  # Ingredients as comma-separated values
        instructions = request.form.get("instructions")

        # Basic validation
        if not recipe_name or not ingredients or not instructions:
            flash("All fields are required!", "danger")
            return redirect(url_for("add_recipe"))

        # Save the recipe to the database
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            # Insert the recipe into `saved_recipes` table
            cursor.execute(
                """
                INSERT INTO saved_recipes (user_id, recipe_name, instructions, timestamp)
                VALUES (%s, %s, %s, NOW())
                """,
                (user_id, recipe_name, instructions)
            )
            connection.commit()

            flash("Recipe added successfully!", "success")
            return redirect(url_for("saved_recipes"))
        except mysql.connector.Error as err:
            flash(f"Error adding recipe: {err}", "danger")
            print(f"Database error: {err}")
        finally:
            cursor.close()
            connection.close()

    return render_template("add-recipe.html")


@app.route("/recipe")
def recipe_page():
    if "user" not in session:
        return redirect(url_for("register"))

    user_id = session["user"]
    ingredients = get_all_ingredients(user_id)

    if ingredients:
        recipes = get_recipes_from_ingredients(ingredients)
        if recipes:
            return render_template("recipe-page.html", recipes=recipes, ingredients=ingredients)
        else:
            flash("No recipes found for the provided ingredients.", "warning")
            return render_template("recipe-page.html", recipes=[], ingredients=ingredients)
    else:
        flash("You have no ingredients. Please add some ingredients first.", "danger")
        return render_template("recipe-page.html", recipes=[], ingredients=[])


@app.route("/save-recipe", methods=["POST"])
def save_recipe():
    if "user" not in session:
        flash("You need to be logged in to save recipes.", "danger")
        return redirect(url_for("login"))

    user_id = session["user"]
    recipe_id = request.form.get("recipe_id")
    recipe_name = request.form.get("recipe_name")
    instructions = request.form.get("instructions")  # Instructions from TheMealDB

    # Validate input
    if not recipe_id or not recipe_name or not instructions:
        flash("Invalid recipe data!", "danger")
        return redirect(url_for("recipe_page"))

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO saved_recipes (user_id, recipe_id, recipe_name, instructions)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, recipe_id, recipe_name, instructions)
        )
        connection.commit()
        flash("Recipe saved successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Error saving recipe: {err}", "danger")
        print(f"Database error: {err}")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("saved_recipes"))

@app.route("/saved-recipes")
def saved_recipes():
    if "user" not in session:
        flash("You need to log in to view saved recipes.", "danger")
        return redirect(url_for("login"))

    user_id = session["user"]

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Fetch saved recipes for the logged-in user
        cursor.execute(
            """
            SELECT recipe_id, recipe_name, instructions, timestamp 
            FROM saved_recipes 
            WHERE user_id = %s
            """,
            (user_id,)
        )
        recipes = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f"Error fetching saved recipes: {err}", "danger")
        recipes = []
    finally:
        cursor.close()
        connection.close()

    # Render the saved recipes template
    return render_template("saved-recipes.html", recipes=recipes)

@app.route("/profile")
def profile_page():
    if "user" not in session:
        flash("You need to log in to view your profile.", "danger")
        return redirect(url_for("login"))

    user_id = session["user"]

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Fetch user information
        cursor.execute(
            """
            SELECT username, email, created_at 
            FROM users 
            WHERE id = %s
            """,
            (user_id,)
        )
        user_info = cursor.fetchone()
    except mysql.connector.Error as err:
        flash(f"Error fetching profile information: {err}", "danger")
        user_info = None
    finally:
        cursor.close()
        connection.close()

    # Render the profile page with user info
    return render_template("profile.html", user_info=user_info)


@app.route("/contact", methods=["GET", "POST"])
def contact_page():
    if "user" not in session:
        return redirect(url_for("register"))
    
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        # Basic validation
        if not name or not email or not message:
            flash("All fields are required!", "danger")
            return redirect(url_for("contact_page"))

        try:
            # Log the message or send it via email (you can replace this with email-sending logic)
            print(f"Message from {name} ({email}):\n{message}")
            flash("Your message has been sent successfully!", "success")
        except Exception as err:
            flash(f"Error sending message: {err}", "danger")
        
        return redirect(url_for('contact_page'))

    return render_template("contact.html")



@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/delete-account", methods=["GET", "POST"])
def delete_account():
    if "user" not in session:
        return redirect(url_for("register"))

    user_id = session["user"]
    print(f"User attempting to delete account: {user_id}")  # Debugging log

    if request.method == "POST":
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            # Start a transaction to ensure atomicity
            connection.start_transaction()

            # Delete user-related data in a proper order
            cursor.execute("DELETE FROM user_ingredients WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM saved_recipes WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

            # Commit the transaction
            connection.commit()

            # Flash success message and clear the session
            flash("Your account and all related data have been deleted successfully.", "success")
            session.pop("user", None)

            # Redirect to the registration page
            return redirect(url_for("register"))
        except mysql.connector.Error as err:
            # Rollback the transaction if any error occurs
            connection.rollback()
            flash(f"Error deleting account: {err}", "danger")
            print(f"Database error while deleting account: {err}")
        finally:
            cursor.close()
            connection.close()

    # Render the confirmation page for account deletion
    return render_template("delete-account.html")

@app.route("/")
@app.route("/home")
def home_page():
    if "user" not in session:
        return redirect(url_for("register"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
