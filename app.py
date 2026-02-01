import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime

# Load environment variables if env.py exists
if os.path.exists("env.py"):
    import env

# ------------------- APP SETUP -------------------
app = Flask(__name__)
app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/precisiondb")
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

mongo = PyMongo(app)

# ------------------- DECORATORS -------------------
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap

def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrap

# ------------------- AUTH -------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").lower()
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = generate_password_hash(request.form.get("password"))

        # Check if username exists
        if mongo.db.users.find_one({"username": username}):
            flash("Username already exists")
            return redirect(url_for("register"))

        # Insert user
        mongo.db.users.insert_one({
            "username": username,
            "email": email,
            "phone": phone,
            "password": password,
            "role": "user"
        })
        flash("Account created! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")

        user = mongo.db.users.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session["user"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("admin_dashboard") if user["role"] == "admin" else url_for("dashboard"))

        flash("Invalid username or password")
        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ------------------- PAGES -------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/projects")
def projects():
    projects_list = [
        {
            "title": "Residential building extension",
            "description": "Residential building extension project including detailed CAD drawings and construction documentation.",
            "image": "project1.jpg"
        },
        {
            "title": "I beam calculation”",
            "description": "Structural I-beam calculation and installation design for a wall removal project",
            "image": "project2.jpg"
        },
        {
            "title": "Commercial fit-out",
            "description": "Commercial layout drawings and material requirement estimation",
            "image": "project3.jpg"
        },
        {
            "title": "Industrial Warehouse",
            "description": "Large-span warehouse structural and layout drawings.",
            "image": "project4.jpg"
        },
        {
            "title": "Foundation Design",
            "description": "Reinforced concrete foundation plans and sections.",
            "image": "project5.jpg"
        },
        {
            "title": "Renovation Project",
            "description": "As-built drawings and renovation documentation.",
            "image": "project6.jpg"
        },
    ]
    return render_template("projects.html", projects=projects_list)

@app.route("/services")
def services():
    services_list = [
        {"title": "CAD Drafting", "description": "High-quality CAD drafting services."},
        {"title": "Structural Design", "description": "Professional structural engineering solutions."},
    ]
    return render_template("services.html", services=services_list)

# ------------------- DASHBOARD -------------------
@app.route("/dashboard")
@login_required
def dashboard():
    orders = list(mongo.db.orders.find({"client": session["user"]}))
    messages = {}
    for order in orders:
        messages[str(order["_id"])] = list(
            mongo.db.messages.find({"order_id": order["_id"]}).sort("created", 1)
        )
    return render_template("dashboard.html", orders=orders, messages=messages)

@app.route("/upload", methods=["POST"])
@login_required
def upload_order():
    files = request.files.getlist("file")
    saved = []

    for f in files:
        name = secure_filename(f.filename)
        f.save(os.path.join(app.config["UPLOAD_FOLDER"], name))
        saved.append(name)

    mongo.db.orders.insert_one({
        "client": session["user"],
        "files": saved,
        "status": "Received",
        "progress": 0
    })
    return redirect(url_for("dashboard"))

# ------------------- ADMIN -------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    users = list(mongo.db.users.find())
    orders = list(mongo.db.orders.find())
    messages = {}
    for order in orders:
        messages[str(order["_id"])] = list(
            mongo.db.messages.find({"order_id": order["_id"]}).sort("created", 1)
        )
    return render_template("admin.html", users=users, orders=orders, messages=messages)

@app.route("/admin/order/delete/<order_id>", methods=["POST"])
@admin_required
def admin_delete_order(order_id):
    mongo.db.orders.delete_one({"_id": ObjectId(order_id)})
    mongo.db.messages.delete_many({"order_id": ObjectId(order_id)})
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/user/delete/<user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if user and user["username"] != session["user"]:
        mongo.db.users.delete_one({"_id": ObjectId(user_id)})
        mongo.db.orders.delete_many({"client": user["username"]})
    return redirect(url_for("admin_dashboard"))

# ------------------- MESSAGES -------------------
@app.route("/message/send", methods=["POST"])
@login_required
def send_message():
    mongo.db.messages.insert_one({
        "order_id": ObjectId(request.form.get("order_id")),
        "from": session["user"],
        "to": request.form.get("to"),
        "text": request.form.get("text"),
        "created": datetime.utcnow()
    })
    return redirect(request.referrer)

# ------------------- RUN APP -------------------
if __name__ == "__main__":
    app.run(debug=True)
