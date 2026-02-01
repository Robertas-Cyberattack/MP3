import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime
from flask_mail import Mail, Message

# Load environment variables if env.py exists
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
app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/precisiondb")
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
            return redirect(url_for("home"))
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
            body=f"""
Name: {data['name']}
Email: {data['email']}
Mobile: {data['mobile']}

Message:
{data['message']}
"""
        )
        mail.send(msg)
        flash("Message sent successfully!")
    except Exception as e:
        print("EMAIL ERROR:", e)
        flash("Failed to send email. Check SendGrid settings.")
    return redirect(url_for("contact"))

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

# Dashboard routes placeholders
@app.route("/dashboard")
@login_required
def dashboard():
    return "User dashboard"

@app.route("/admin")
@admin_required
def admin_dashboard():
    return "Admin dashboard"

# ------------------- RUN APP -------------------
if __name__ == "__main__":
    app.run(debug=True)
