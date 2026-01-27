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

# ---------------- CONFIG ----------------
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

# ---------------- AUTH ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")

        if mongo.db.users.find_one({"username": username}):
            flash("User exists")
            return redirect(url_for("register"))

        mongo.db.users.insert_one({
            "username": username,
            "password": generate_password_hash(password),
            "role": "client"
        })

        session["user"] = username
        session["role"] = "client"
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = mongo.db.users.find_one({"username": request.form.get("username").lower()})

        if user and check_password_hash(user["password"], request.form.get("password")):
            session["user"] = user["username"]
            session["role"] = user["role"]

            return redirect(url_for("admin_dashboard") if user["role"] == "admin" else url_for("dashboard"))

        flash("Invalid login")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    orders = mongo.db.orders.find({"client": session["user"]})
    messages = mongo.db.messages.find({
        "$or": [
            {"from": session["user"]},
            {"to": session["user"]}
        ]
    }).sort("created", -1)

    return render_template("dashboard.html", orders=orders, messages=messages)

# ---------------- UPLOAD ORDER ----------------
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

# ---------------- DELETE ORDER (CLIENT) ----------------
@app.route("/order/delete/<order_id>", methods=["POST"])
@login_required
def delete_order_client(order_id):
    mongo.db.orders.delete_one({"_id": ObjectId(order_id), "client": session["user"]})
    return redirect(url_for("dashboard"))

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    users = mongo.db.users.find()
    orders = mongo.db.orders.find()
    messages = mongo.db.messages.find().sort("created", -1)
    return render_template("admin.html", users=users, orders=orders, messages=messages)

# ---------------- ADMIN DELETE ORDER ----------------
@app.route("/admin/order/delete/<order_id>", methods=["POST"])
@admin_required
def admin_delete_order(order_id):
    mongo.db.orders.delete_one({"_id": ObjectId(order_id)})
    return redirect(url_for("admin_dashboard"))

# ---------------- ADMIN DELETE USER ----------------
@app.route("/admin/user/delete/<user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})

    if user and user["username"] != session["user"]:
        mongo.db.users.delete_one({"_id": ObjectId(user_id)})
        mongo.db.orders.delete_many({"client": user["username"]})

    return redirect(url_for("admin_dashboard"))

# ---------------- MESSAGES ----------------
@app.route("/message/send", methods=["POST"])
@login_required
def send_message():
    mongo.db.messages.insert_one({
        "from": session["user"],
        "to": request.form.get("to"),
        "text": request.form.get("text"),
        "created": datetime.utcnow()
    })
    return redirect(request.referrer)

# ---------------- STATIC ----------------
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/services")
def services():
    return render_template("services.html")

@app.route("/projects")
def projects():
    return render_template("projects.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

if __name__ == "__main__":
    app.run(debug=True)
