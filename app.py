import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash

# Load env.py if present (local development)
if os.path.exists("env.py"):
    import env

app = Flask(__name__)

# -------------------- CONFIG --------------------
app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)

# -------------------- HOME --------------------
@app.route("/")
def home():
    return render_template("home.html", user=session.get("user"))

# -------------------- REGISTER --------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")
        email = request.form.get("email")
        phone = request.form.get("phone")

        # Check if user already exists
        if mongo.db.users.find_one({"username": username}):
            flash("Username already exists")
            return redirect(url_for("register"))

        # Create CLIENT user
        mongo.db.users.insert_one({
            "username": username,
            "password": generate_password_hash(password),
            "email": email,
            "phone": phone,
            "role": "client"
        })

        session["user"] = username
        session["role"] = "client"

        flash("Registration successful")
        return redirect(url_for("dashboard"))

    return render_template("register.html")

# -------------------- LOGIN --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")

        user = mongo.db.users.find_one({"username": username})

        if user and check_password_hash(user["password"], password):
            session["user"] = username
            session["role"] = user["role"]

            flash(f"Welcome back, {username}")

            # Redirect based on role
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("dashboard"))

        flash("Invalid username or password")
        return redirect(url_for("login"))

    return render_template("login.html")

# -------------------- LOGOUT --------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out")
    return redirect(url_for("login"))

# -------------------- CLIENT DASHBOARD --------------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    orders = mongo.db.orders.find({"client": session["user"]})
    return render_template("dashboard.html", orders=orders, user=session.get("user"))

# -------------------- ADMIN DASHBOARD --------------------
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("home"))

    orders = mongo.db.orders.find()
    users = mongo.db.users.find()

    return render_template(
        "admin.html",
        orders=orders,
        users=users,
        user=session.get("user")
    )

# -------------------- PROJECTS --------------------
@app.route("/projects")
def projects():
    projects_list = [
        {
            "title": "Residential Apartment Design",
            "description": "Complete CAD drafting for residential project",
            "image": "project1.jpg"
        },
        {
            "title": "Office Renovation",
            "description": "Construction documentation for office renovation",
            "image": "project2.jpg"
        }
    ]
    return render_template("projects.html", projects=projects_list, user=session.get("user"))

# -------------------- SERVICES --------------------
@app.route("/services")
def services():
    return render_template("services.html", user=session.get("user"))

# -------------------- ABOUT --------------------
@app.route("/about")
def about():
    return render_template("about.html", user=session.get("user"))

# -------------------- CONTACT --------------------
@app.route("/contact")
def contact():
    return render_template("contact.html", user=session.get("user"))

# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(debug=True)
