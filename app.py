import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime
from flask_mail import Mail, Message

# Load environment variables if exists
if os.path.exists("env.py"):
    import env

# ------------------- APP SETUP -------------------
app = Flask(__name__)

# ------------------- MAIL SETUP -------------------
app.config["MAIL_SERVER"] = "smtp.sendgrid.net"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "apikey"
app.config["MAIL_PASSWORD"] = os.environ.get("SENDGRID_API_KEY")
app.config["MAIL_DEFAULT_SENDER"] = "robertas.sladkevicius@gmail.com"
mail = Mail(app)

# ------------------- MONGODB SETUP -------------------
app.config["MONGO_URI"] = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://robertsladkevicius_db_user1:user1Milijonas2030@cadcluster.5ffsvzf.mongodb.net/CADDB?retryWrites=true&w=majority"
)
mongo = PyMongo(app)

# ------------------- SECRET KEY & UPLOADS -------------------
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key")
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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
            flash("Admin access required")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrap

# ------------------- ROUTES -------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/contact/send", methods=["POST"])
def contact_send():
    data = {
        "name": request.form.get("name"),
        "email": request.form.get("email"),
        "mobile": request.form.get("mobile"),
        "message": request.form.get("message"),
        "created": datetime.utcnow()
    }
    mongo.db.contact_messages.insert_one(data)
    try:
        msg = Message(
            subject="New Contact Form Message",
            sender=app.config["MAIL_DEFAULT_SENDER"],
            recipients=["robertas.sladkevicius@gmail.com"],
            body=f"Name: {data['name']}\nEmail: {data['email']}\nMobile: {data['mobile']}\n\nMessage:\n{data['message']}"
        )
        mail.send(msg)
        flash("Message sent successfully!")
    except Exception as e:
        print("EMAIL ERROR:", e)
        flash("Failed to send email.")
    return redirect(url_for("contact"))

# ------------------- REGISTER / LOGIN -------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").lower()
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = generate_password_hash(request.form.get("password"))

        if mongo.db.users.find_one({"username": username}):
            flash("Username already exists")
            return redirect(url_for("register"))

        mongo.db.users.insert_one({
            "username": username,
            "email": email,
            "phone": phone,
            "password": password,
            "role": "client",
            "lock": False
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
            flash(f"Welcome {user['username']}!")
            return redirect(url_for("admin_dashboard") if user["role"]=="admin" else url_for("dashboard"))

        flash("Invalid username or password")
        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("login"))

# ------------------- DASHBOARD -------------------
@app.route("/dashboard")
@login_required
def dashboard():
    orders = list(mongo.db.orders.find({"clientno": session["user"]}))
    for order in orders:
        msgs = list(mongo.db.contact_messages.find({
            "order_id": str(order["_id"]),
            "$or": [
                {"from": session["user"]},
                {"to": session["user"]}
            ]
        }).sort("created", 1))
        order["messages"] = msgs
    return render_template("dashboard.html", orders=orders)

@app.route("/upload_order", methods=["POST"])
@login_required
def upload_order():
    files = request.files.getlist("file")
    filenames = []
    for f in files:
        filename = f"{datetime.utcnow().timestamp()}_{f.filename}"
        f.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        filenames.append(filename)

    mongo.db.orders.insert_one({
        "clientno": session["user"],
        "status": "Pending",
        "progress": 0,
        "file": filenames,
        "comments": "",
        "date": datetime.utcnow()
    })
    flash("Order uploaded!")
    return redirect(url_for("dashboard"))

@app.route("/delete_order/<order_id>", methods=["POST"])
@login_required
def delete_order(order_id):
    mongo.db.orders.delete_one({"_id": ObjectId(order_id), "clientno": session["user"]})
    mongo.db.contact_messages.delete_many({"order_id": order_id})
    flash("Order and messages deleted")
    return redirect(url_for("dashboard"))

# ------------------- SEND MESSAGE -------------------
@app.route("/send_message", methods=["POST"])
@login_required
def send_message():
    order_id = request.form.get("order_id")
    text = request.form.get("text")
    to_user = request.form.get("to")

    mongo.db.contact_messages.insert_one({
        "from": session["user"],
        "to": to_user,
        "text": text,
        "order_id": order_id,
        "created": datetime.utcnow()
    })
    flash("Message sent!")
    return redirect(request.referrer or url_for("dashboard"))

# ------------------- ADMIN DASHBOARD -------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    orders = list(mongo.db.orders.find())
    users = list(mongo.db.users.find())
    for order in orders:
        msgs = list(mongo.db.contact_messages.find({"order_id": str(order["_id"])}).sort("created", 1))
        order["messages"] = msgs
    return render_template("admin.html", orders=orders, users=users)

@app.route("/admin/delete_order/<order_id>", methods=["POST"])
@admin_required
def admin_delete_order(order_id):
    mongo.db.orders.delete_one({"_id": ObjectId(order_id)})
    mongo.db.contact_messages.delete_many({"order_id": order_id})
    flash("Order and messages deleted")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_user/<user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        mongo.db.orders.delete_many({"clientno": user["username"]})
        mongo.db.users.delete_one({"_id": ObjectId(user_id)})
        flash("User and orders deleted")
    return redirect(url_for("admin_dashboard"))

# ------------------- OTHER PAGES -------------------
@app.route("/projects")
def projects():
    projects_list = [
        {"title": "Residential building extension", "description": "Residential building extension project including detailed CAD drawings and construction documentation.", "image": "extension.jpg"},
        {"title": "I beam calculation", "description": "Structural I-beam calculation and installation design for a wall removal project", "image": "I_beam.jpg"},
        {"title": "Commercial fit-out", "description": "Commercial layout drawings and material requirement estimation", "image": "commercial.jpg"},
        {"title": "Industrial Warehouse", "description": "Large-span warehouse structural and layout drawings.", "image": "industrial.jpg"},
        {"title": "Foundation Design", "description": "Reinforced concrete foundation plans and sections.", "image": "foundation.jpg"},
        {"title": "Renovation Project", "description": "As-built drawings and renovation documentation.", "image": "renovation.jpg"},
    ]
    return render_template("projects.html", projects=projects_list)

@app.route("/services")
def services():
    services_list = [
        {"title": "CAD Drafting", "description": "High-quality CAD drafting services.", "image": "drafting.jpg"},
        {"title": "Structural Design", "description": "Professional structural engineering solutions.", "image": "structural.jpg"},
        {"title": "Civil Engineering", "description": "Drainage, levels & infrastructure.", "image": "civil.jpg"},
        {"title": "MEP Coordination", "description": "Mechanical, electrical & plumbing.", "image": "mep.jpg"},
        {"title": "Interior Layouts", "description": "Office & residential interiors.", "image": "interior_layout.png"},
        {"title": "Construction Docs", "description": "Build-ready documentation.", "image": "docs.jpg"},
    ]
    return render_template("services.html", services=services_list)

# ------------------- RUN APP -------------------
if __name__ == "__main__":
    app.run(debug=True)
