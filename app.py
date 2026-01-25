import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash

if os.path.exists("env.py"):
    import env

app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)

# -------------------- HOME --------------------
@app.route("/")
def home():
    return render_template("home.html", user=session.get("user"))

# -------------------- PROJECTS --------------------
@app.route("/projects")
def projects():
    projects_list = [
        {"title": "Residential Apartment Design", "description": "Complete CAD drafting for a modern apartment complex in London.", "image": "project1.jpg"},
        {"title": "Commercial Office Renovation", "description": "Construction drawings for office renovation in Manchester.", "image": "project2.jpg"},
        {"title": "Industrial Warehouse Layout", "description": "Warehouse CAD plans including structural and MEP.", "image": "project3.jpg"},
        {"title": "Bridge Engineering Project", "description": "Civil and structural drawings following Eurocodes.", "image": "project4.jpg"},
        {"title": "Retail Store Interior Design", "description": "Interior CAD drawings for retail spaces.", "image": "project5.jpg"},
        {"title": "Luxury Villa Development", "description": "High-end residential construction documentation.", "image": "project6.jpg"},
    ]
    return render_template("projects.html", projects=projects_list, user=session.get("user"))

# -------------------- REGISTER --------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")

        if mongo.db.users.find_one({"username": username}):
            flash("Username already exists")
            return redirect(url_for("register"))

        mongo.db.users.insert_one({
            "username": username,
            "password": generate_password_hash(password)
        })

        session["user"] = username
        return redirect(url_for("home"))

    return render_template("register.html")

# -------------------- LOGIN --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = mongo.db.users.find_one({"username": request.form.get("username").lower()})
        if user and check_password_hash(user["password"], request.form.get("password")):
            session["user"] = user["username"]
            return redirect(url_for("home"))

        flash("Incorrect username or password")

    return render_template("login.html")

# -------------------- LOGOUT --------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# -------------------- ABOUT --------------------
@app.route("/about")
def about():
    return render_template("about.html", user=session.get("user"))

# -------------------- SERVICES --------------------
@app.route("/services")
def services():
    return render_template("services.html", user=session.get("user"))

# -------------------- CONTACT --------------------
@app.route("/contact")
def contact():
    return render_template("contact.html", user=session.get("user"))

if __name__ == "__main__":
    app.run(debug=True)
