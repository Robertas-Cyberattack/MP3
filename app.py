import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime

app = Flask(__name__)

# --- KONFIGŪRACIJA ---
app.config["MONGO_URI"] = "mongodb+srv://robertsladkevicius_db_user1:user1Milijonas2030@cadcluster.5ffsvzf.mongodb.net/CADDB?retryWrites=true&w=majority"
app.secret_key = "super-secret-key"
mongo = PyMongo(app)

# --- APSAUGA (DECORATORS) ---
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
            flash("Tik administratoriui!")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrap

# --- PAGRINDINIAI PUSLAPIAI ---
@app.route("/")
def home(): return render_template("home.html")

@app.route("/projects")
def projects(): return render_template("projects.html")

# --- LOGIN / REGISTER ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").lower().strip()
        if mongo.db.users.find_one({"username": username}):
            flash("Vartotojas jau egzistuoja")
            return redirect(url_for("register"))

        mongo.db.users.insert_one({
            "username": username,
            "email": request.form.get("email"),
            "phone": request.form.get("phone"),
            "password": generate_password_hash(request.form.get("password")),
            "role": "client",
            "lock": False
        })
        flash("Registracija sėkminga! Prisijunkite.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").lower().strip()
        password = request.form.get("password")
        user = mongo.db.users.find_one({"username": username})

        if user and check_password_hash(user["password"], password):
            if user.get("lock"):
                flash("Jūsų paskyra užblokuota!")
                return redirect(url_for("login"))
            
            session["user"] = user["username"]
            session["role"] = user.get("role", "client")
            return redirect(url_for("admin_dashboard" if session["role"] == "admin" else "dashboard"))

        flash("Neteisingi duomenys")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- KLIENTO PUSLAPIS ---
@app.route("/dashboard")
@login_required
def dashboard():
    orders = list(mongo.db.orders.find({"clientno": session["user"]}))
    for order in orders:
        order["messages"] = list(mongo.db.contact_messages.find({"order_id": str(order["_id"])}))
    return render_template("dashboard.html", orders=orders)

# --- ADMIN FUNKCIJOS ---
@app.route("/admin")
@admin_required
def admin_dashboard():
    orders = list(mongo.db.orders.find())
    users = list(mongo.db.users.find())
    messages_map = {}
    for order in orders:
        messages_map[str(order["_id"])] = list(mongo.db.contact_messages.find({"order_id": str(order["_id"])}))
    return render_template("admin.html", orders=orders, users=users, messages=messages_map)

@app.route("/admin/delete_user/<user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    mongo.db.users.delete_one({"_id": ObjectId(user_id)})
    flash("Vartotojas ištrintas")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/toggle_block/<user_id>", methods=["POST"])
@admin_required
def toggle_block(user_id):
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    new_status = not user.get("lock", False)
    mongo.db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"lock": new_status}})
    flash("Statusas pakeistas")
    return redirect(url_for("admin_dashboard"))

# --- ŽINUTĖS ---
@app.route("/send_message", methods=["POST"])
@login_required
def send_message():
    mongo.db.contact_messages.insert_one({
        "from": session["user"],
        "to": request.form.get("to"),
        "text": request.form.get("text"),
        "order_id": request.form.get("order_id"),
        "created": datetime.utcnow()
    })
    flash("Žinutė išsiųsta")
    return redirect(request.referrer)

if __name__ == "__main__":
    app.run(debug=True)