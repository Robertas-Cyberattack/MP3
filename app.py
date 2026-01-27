import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime

if os.path.exists("env.py"):
    import env

app = Flask(__name__)
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

mongo = PyMongo(app)

# ---------------- DECORATORS ----------------
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user" not in session:
            flash("Please login first")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap

def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access only")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrap

# ---------------- AUTH ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")
        user = mongo.db.users.find_one({"username": username})
        if user:
            if check_password_hash(user["password"], password):
                session["user"] = user["username"]
                session["role"] = user["role"]
                return redirect(url_for("admin_dashboard") if user["role"] == "admin" else url_for("dashboard"))
        flash("Invalid username or password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out")
    return redirect(url_for("login"))

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# ---------------- DASHBOARD (CLIENT) ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    orders = list(mongo.db.orders.find({"client": session["user"]}))

    # Load messages for each order
    messages = {}
    for order in orders:
        messages[str(order["_id"])] = list(
            mongo.db.messages.find({"order_id": order["_id"]}).sort("created", 1)
        )

    return render_template("dashboard.html", orders=orders, messages=messages)

# ---------------- UPLOAD ORDER ----------------
@app.route("/upload", methods=["POST"])
@login_required
def upload_order():
    files = request.files.getlist("file")
    saved = []

    for f in files:
        if f.filename:
            filename = secure_filename(f.filename)
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            saved.append(filename)

    mongo.db.orders.insert_one({
        "client": session["user"],
        "files": saved,
        "status": "Received",
        "progress": 0
    })
    flash("Order uploaded successfully")
    return redirect(url_for("dashboard"))

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    users = list(mongo.db.users.find())
    orders = list(mongo.db.orders.find())

    # Load messages for each order
    messages = {}
    for order in orders:
        messages[str(order["_id"])] = list(
            mongo.db.messages.find({"order_id": order["_id"]}).sort("created", 1)
        )

    return render_template("admin.html", users=users, orders=orders, messages=messages)

# ---------------- DELETE ORDER ----------------
@app.route("/admin/order/delete/<order_id>", methods=["POST"])
@admin_required
def admin_delete_order(order_id):
    order = mongo.db.orders.find_one({"_id": ObjectId(order_id)})
    if order:
        # Delete files
        for f in order.get("files", []):
            path = os.path.join(app.config["UPLOAD_FOLDER"], f)
            if os.path.exists(path):
                os.remove(path)
        mongo.db.orders.delete_one({"_id": ObjectId(order_id)})
        mongo.db.messages.delete_many({"order_id": ObjectId(order_id)})
        flash("Order deleted")
    return redirect(url_for("admin_dashboard"))

# ---------------- DELETE USER ----------------
@app.route("/admin/user/delete/<user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if user and user["username"] != session["user"]:
        mongo.db.users.delete_one({"_id": ObjectId(user_id)})
        # Delete all orders & messages of that user
        orders = list(mongo.db.orders.find({"client": user["username"]}))
        for order in orders:
            mongo.db.messages.delete_many({"order_id": order["_id"]})
            mongo.db.orders.delete_one({"_id": order["_id"]})
        flash(f"User {user['username']} deleted")
    return redirect(url_for("admin_dashboard"))

# ---------------- SEND MESSAGE ----------------
@app.route("/message/send", methods=["POST"])
@login_required
def send_message():
    order_id = request.form.get("order_id")
    mongo.db.messages.insert_one({
        "order_id": ObjectId(order_id),
        "from": session["user"],
        "to": request.form.get("to"),
        "text": request.form.get("text"),
        "created": datetime.utcnow()
    })
    flash("Message sent")
    return redirect(request.referrer)

# ---------------- PROJECTS PAGE ----------------
@app.route("/projects")
def projects():
    # 6 hard-coded projects
    projects_list = [
        {"title": "Residential CAD", "description": "Detailed residential CAD projects.", "image": "placeholder.jpg"},
        {"title": "Commercial CAD", "description": "High-rise and office projects.", "image": "placeholder.jpg"},
        {"title": "Structural Drafting", "description": "Eurocode-compliant structures.", "image": "placeholder.jpg"},
        {"title": "Civil Engineering", "description": "Drainage, roads, infrastructure.", "image": "placeholder.jpg"},
        {"title": "MEP Coordination", "description": "Mechanical, electrical & plumbing.", "image": "placeholder.jpg"},
        {"title": "Interior Layouts", "description": "Office and residential interiors.", "image": "placeholder.jpg"},
    ]
    return render_template("projects.html", projects=projects_list)

# ---------------- STATIC PAGES ----------------
@app.route("/services")
def services():
    return render_template("services.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
