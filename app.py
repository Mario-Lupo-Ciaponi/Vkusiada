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

def get_all_ingredients(username):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT ingredients FROM user_info WHERE username = %s", (username,))
        user_info = cursor.fetchone()
        if user_info and user_info['ingredients']:
            ingredients = user_info['ingredients'].split(",")
            return [ingredient.strip() for ingredient in ingredients]
        else:
            return []
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return []
    finally:
        cursor.close()
        connection.close()

    
def get_recipes_from_ingredients(ingredients):
    # Initialize a set to collect recipes that match
    all_recipes = set()

    for ingredient in ingredients:
        # Query TheMealDB API for each ingredient
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ingredient}"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            meals = data.get('meals', [])
            # Add meal IDs or names to the set
            if meals:
                for meal in meals:
                    all_recipes.add((meal['idMeal'], meal['strMeal'], meal['strMealThumb']))
        else:
            print(f"Error fetching data for ingredient: {ingredient}")

    # Return the combined results as a list
    return list(all_recipes)


@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    # Fetch recipe details from TheMealDB API
    api_url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={recipe_id}"
    response = requests.get(api_url)
    recipe = response.json().get("meals")[0]  # Extract the first recipe
    
    if recipe:
        return render_template("recipe-detail.html", recipe=recipe)
    else:
        return render_template("recipe-detail.html", recipe=None)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Basic validation
        if not email or not password:
            flash("Email and password are required!", "danger")
            return redirect('/login')

        # Check user in the database
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                session["user"] = user['username']
                # Redirect after successful login to prevent form resubmission
                return redirect(url_for('home_page'))
            else:
                flash("Invalid email or password!", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect('/login')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Basic validation
        if not username or not email or not password:
            flash("All fields are required!", "danger")
            return redirect('/register')

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Insert into database
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            # Insert user credentials into 'users' table
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed_password)
            )
            connection.commit()

            # Insert default user info into 'user_info' table
            cursor.execute(
                "INSERT INTO user_info (username, ingredients, recipes) VALUES (%s, %s, %s)",
                (username, '', '')  # Explicitly insert empty strings for ingredients and recipes
            )
            connection.commit()

            flash("Registration successful! Please log in.", "success")
            return redirect('/login')  # Redirect to login after registration
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
        finally:
            cursor.close()
            connection.close()

    return render_template('register.html')



@app.route("/contact", methods=["GET", "POST"])
def contact_page():
    if "user" not in session:
        return redirect(url_for("register"))
    
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        print(f"Message from {name}({email}):\n{message}")

        flash("Your message has been sent successfully!", "success")
        return redirect(url_for('contact_page'))

    return render_template("contact.html")

@app.route("/add-ingredients", methods=["GET", "POST"])
def add_ingredients_page():
    if "user" not in session:
        return redirect(url_for("register"))

    username = session["user"]

    if request.method == "POST":
        # Get new ingredients from the form
        new_ingredients = request.form["ingredients"].strip()
        
        # Ensure input is provided
        if not new_ingredients:
            flash("Please provide ingredients to add.", "danger")
            return redirect(url_for("add_ingredients_page"))

        # Split new ingredients by comma and clean them
        new_ingredients = [ingredient.strip() for ingredient in new_ingredients.split(",")]

        # Fetch current ingredients from the user_info table
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT ingredients FROM user_info WHERE username = %s", (username,)
            )
            user_info = cursor.fetchone()

            if user_info:
                current_ingredients = user_info['ingredients']
                if current_ingredients:
                    # Split existing ingredients and clean them
                    current_ingredients = [ingredient.strip() for ingredient in current_ingredients.split(",")]
                else:
                    current_ingredients = []

                # Combine new and existing ingredients, ensuring no duplicates
                all_ingredients = list(set(current_ingredients + new_ingredients))

                # Update the ingredients column in the user_info table
                cursor.execute(
                    "UPDATE user_info SET ingredients = %s WHERE username = %s",
                    (",".join(all_ingredients), username)
                )
                connection.commit()
                flash("Ingredients added successfully!", "success")
            else:
                flash("User not found!", "danger")

        except mysql.connector.Error as err:
            flash(f"Error adding ingredients: {err}", "danger")
            print(f"Database error while adding ingredients: {err}")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for("ingredients_page"))

    return render_template("add-ingredients.html")


@app.route("/ingredients")
def ingredients_page():
    if "user" not in session:
        return redirect(url_for("register"))
    
    username = session["user"]
    ingredients = get_all_ingredients(username)

    return render_template("ingredients-page.html", name=username, ingredients=ingredients)

@app.route("/about")
def about_page():
    return render_template("about-page.html")

@app.route("/save-recipe", methods=["POST"])
def save_recipe():
    if "user" not in session:
        flash("You need to be logged in to save recipes.", "danger")
        return redirect(url_for("login"))

    username = session["user"]
    recipe_id = request.form.get("recipe_id")
    recipe_name = request.form.get("recipe_name")
    instructions = request.form.get("instructions")  # Instructions from TheMealDB

    # Validate input
    if not recipe_id or not recipe_name or not instructions:
        flash("Invalid recipe data!", "danger")
        return redirect(url_for("recipe_page"))

    # Save to the database
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        # Insert saved recipe details into the database
        cursor.execute(
            """
            INSERT INTO saved_recipes (username, recipe_id, recipe_name, instructions)
            VALUES (%s, %s, %s, %s)
            """,
            (username, recipe_id, recipe_name, instructions)
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

    username = session["user"]

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT recipe_id, recipe_name, instructions, timestamp FROM saved_recipes WHERE username = %s",
            (username,)
        )
        recipes = cursor.fetchall()

        # Print the fetched recipes for debugging
        print(f"Fetched recipes: {recipes}")

    except mysql.connector.Error as err:
        flash(f"Error fetching saved recipes: {err}", "danger")
        recipes = []
    finally:
        cursor.close()
        connection.close()

    return render_template("saved-recipes.html", recipes=recipes)


@app.route("/recipe")
def recipe_page():
    if "user" not in session:
        return redirect(url_for("register"))
    
    username = session["user"]
    ingredients = get_all_ingredients(username)

    if ingredients:
        recipes = get_recipes_from_ingredients(ingredients)
        if recipes:
            return render_template("recipe-page.html", recipes=recipes, ingredients=ingredients)
        else:
            flash("No recipes found for the provided ingredients. Try with different ingredients!", "warning")
            # Stay on the recipe page and display the message
            return render_template("recipe-page.html", recipes=[], ingredients=ingredients)
    else:
        flash("You have no ingredients. Please add some ingredients first.", "danger")
        # Stay on the recipe page and display the message
        return render_template("recipe-page.html", recipes=[], ingredients=[])
    

@app.route("/", methods=["GET", "POST"])
@app.route("/home", methods=["GET", "POST"])
def home_page():
    if "user" not in session:
        return redirect(url_for("register"))
    
    username = session["user"]
    
    if request.method == "POST":
        # Get new ingredients from the form
        new_ingredients = request.form["ingredients"].strip()
        # Split new ingredients by comma and clean them
        new_ingredients = [ingredient.strip() for ingredient in new_ingredients.split(",")]

        # Fetch current ingredients from the user_info table
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT ingredients FROM user_info WHERE username = %s", (username,)
            )
            user_info = cursor.fetchone()

            if user_info:
                current_ingredients = user_info['ingredients']
                if current_ingredients:
                    # Split existing ingredients and clean them
                    current_ingredients = [ingredient.strip() for ingredient in current_ingredients.split(",")]
                else:
                    current_ingredients = []

                # Combine new and existing ingredients, ensuring no duplicates
                all_ingredients = list(set(current_ingredients + new_ingredients))
                
                # Update the ingredients column in the user_info table
                cursor.execute(
                    "UPDATE user_info SET ingredients = %s WHERE username = %s",
                    (",".join(all_ingredients), username)
                )
                connection.commit()
                flash("Ingredients added successfully!", "success")
            else:
                flash("User not found!", "danger")

        except mysql.connector.Error as err:
            flash(f"Error adding ingredients: {err}", "danger")
        finally:
            cursor.close()
            connection.close()

    return render_template("index.html")



@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/delete-account", methods=["GET", "POST"])
def delete_account():
    if "user" not in session:
        return redirect(url_for("register"))
    
    username = session["user"]
    print(f"User attempting to delete account: {username}")  # Debugging log

    if request.method == "POST":
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            # Start a transaction to ensure atomicity
            connection.start_transaction()

            # Delete from saved_recipes
            cursor.execute("DELETE FROM saved_recipes WHERE username = %s", (username,))
            
            # Delete from user_info
            cursor.execute("DELETE FROM user_info WHERE username = %s", (username,))
            
            # Delete from users
            cursor.execute("DELETE FROM users WHERE username = %s", (username,))

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
    return render_template("delete-account.html", name=username)




if __name__ == "__main__":
    app.run(debug=True)