import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from functools import wraps

# Load environment variables
if os.path.exists("env.py"):
    import env

app = Flask(__name__)

# -------------------- CONFIG --------------------
app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

mongo = PyMongo(app)

# -------------------- DECORATORS --------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            flash("Please login first")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access only")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated


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

        if mongo.db.users.find_one({"username": username}):
            flash("Username already exists")
            return redirect(url_for("register"))

        mongo.db.users.insert_one({
            "username": username,
            "password": generate_password_hash(password),
            "email": email,
            "phone": phone,
            "role": "client",
            "lock": False
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

        if user:
            if user.get("lock"):
                flash("Account is locked. Contact admin.")
                return redirect(url_for("login"))

            if check_password_hash(user["password"], password):
                session["user"] = username
                session["role"] = user["role"]

                if user["role"] == "admin":
                    return redirect(url_for("admin_dashboard"))
                return redirect(url_for("dashboard"))

        flash("Invalid username or password")
        return redirect(url_for("login"))

    return render_template("login.html")


# -------------------- LOGOUT --------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out")
    return redirect(url_for("login"))


# -------------------- CLIENT DASHBOARD --------------------
@app.route("/dashboard")
@login_required
def dashboard():
    orders = list(mongo.db.orders.find({"client": session["user"]}))
    return render_template("dashboard.html", orders=orders, user=session.get("user"))


# -------------------- FILE UPLOAD --------------------
@app.route("/upload", methods=["POST"])
@login_required
def upload_order():
    files = request.files.getlist("file")

    if not files or files[0].filename == "":
        flash("No file selected")
        return redirect(url_for("dashboard"))

    saved_files = []
    for file in files:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        saved_files.append(filename)

    mongo.db.orders.insert_one({
        "client": session["user"],
        "files": saved_files,
        "status": "Received",
        "progress": 0
    })

    flash("Order uploaded successfully")
    return redirect(url_for("dashboard"))


# -------------------- CLIENT DELETE ORDER --------------------
@app.route("/order/delete/<order_id>", methods=["POST"])
@login_required
def delete_order(order_id):
    order = mongo.db.orders.find_one({"_id": ObjectId(order_id)})

    if not order or order["client"] != session["user"]:
        flash("Not authorized")
        return redirect(url_for("dashboard"))

    for filename in order.get("files", []):
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(path):
            os.remove(path)

    mongo.db.orders.delete_one({"_id": ObjectId(order_id)})

    flash("Order deleted")
    return redirect(url_for("dashboard"))


# -------------------- ADMIN DASHBOARD --------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    users = list(mongo.db.users.find())
    orders = list(mongo.db.orders.find())
    return render_template("admin.html", users=users, orders=orders, user=session.get("user"))


# -------------------- ADMIN UPDATE USER --------------------
@app.route("/admin/update_user/<user_id>", methods=["POST"])
@admin_required
def update_user(user_id):
    email = request.form.get("email")
    phone = request.form.get("phone")
    role = request.form.get("role")
    lock = request.form.get("lock") == "True"

    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"email": email, "phone": phone, "role": role, "lock": lock}}
    )

    flash("User updated")
    return redirect(url_for("admin_dashboard"))


# -------------------- ADMIN UPDATE ORDER --------------------
@app.route("/admin/update/<order_id>", methods=["POST"])
@admin_required
def update_order(order_id):
    status = request.form.get("status")
    progress = int(request.form.get("progress"))

    mongo.db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": status, "progress": progress}}
    )

    flash("Order updated")
    return redirect(url_for("admin_dashboard"))


# -------------------- ADMIN DELETE ORDER --------------------
@app.route("/admin/delete/<order_id>", methods=["POST"])
@admin_required
def admin_delete_order(order_id):
    order = mongo.db.orders.find_one({"_id": ObjectId(order_id)})

    if order:
        for filename in order.get("files", []):
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            if os.path.exists(path):
                os.remove(path)

        mongo.db.orders.delete_one({"_id": ObjectId(order_id)})

    flash("Order deleted")
    return redirect(url_for("admin_dashboard"))


# -------------------- STATIC PAGES --------------------
@app.route("/projects")
def projects():
    projects_list = [
        {"title": "Residential CAD", "description": "Detailed residential CAD projects.", "image": "placeholder.jpg"},
        {"title": "Commercial CAD", "description": "High-rise and office projects.", "image": "placeholder.jpg"},
        {"title": "Structural Drafting", "description": "Eurocode-compliant structures.", "image": "placeholder.jpg"},
        {"title": "Civil Engineering", "description": "Drainage, roads, infrastructure.", "image": "placeholder.jpg"},
        {"title": "MEP Coordination", "description": "Mechanical, electrical & plumbing.", "image": "placeholder.jpg"},
        {"title": "Interior Layouts", "description": "Office and residential interiors.", "image": "placeholder.jpg"},
    ]
    return render_template("projects.html", projects=projects_list, user=session.get("user"))


@app.route("/services")
def services():
    return render_template("services.html", user=session.get("user"))


@app.route("/about")
def about():
    return render_template("about.html", user=session.get("user"))


@app.route("/contact")
def contact():
    return render_template("contact.html", user=session.get("user"))


# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(debug=True)
