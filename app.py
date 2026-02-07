import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime
from flask_mail import Mail, Message

# Load env vars
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
mongo_uri = os.environ.get("MONGO_URI")
if not mongo_uri:
    raise RuntimeError("MONGO_URI environment variable is not set")

app.config["MONGO_URI"] = mongo_uri
mongo = PyMongo(app)

# ------------------- SECRET & UPLOADS -------------------
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
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
    return render_template("contact.html", google_maps_key=app.config["GOOGLE_MAPS_KEY"])

@app.route("/contact/send", methods=["POST"])
def contact_send():
    data = {
        "type": "contact_form",
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
            recipients=["robertas.sladkevicius@gmail.com"],
            body=f"""Name: {data['name']}
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
        flash("Failed to send email.")

    return redirect(url_for("contact"))

# ------------------- REGISTER / LOGIN -------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
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
            "role": "client"
        })

        flash("Account created! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = mongo.db.users.find_one({"username": request.form.get("username")})

        if user and check_password_hash(user["password"], request.form.get("password")):
            session["user"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("admin_dashboard") if user["role"] == "admin" else url_for("dashboard"))

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
        order["messages"] = list(mongo.db.contact_messages.find({
            "type": "order_message",
            "$or": [
                {"order_id": str(order["_id"]), "to": session["user"]},
                {"order_id": str(order["_id"]), "from": session["user"]}
            ]
        }).sort("created", 1))

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
        "date": datetime.utcnow()
    })

    flash("Order uploaded!")
    return redirect(url_for("dashboard"))

@app.route("/delete_order/<order_id>", methods=["POST"])
@login_required
def delete_order(order_id):
    mongo.db.orders.delete_one({"_id": ObjectId(order_id), "clientno": session["user"]})
    flash("Order deleted")
    return redirect(url_for("dashboard"))

# ------------------- ADMIN DASHBOARD -------------------
@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    orders = list(mongo.db.orders.find())
    users = list(mongo.db.users.find({"role": "client"}))
    messages = list(
        mongo.db.contact_messages
        .find({"type": "order_message"})
        .sort("created", 1)
    )
    return render_template("admin.html", orders=orders, users=users, messages=messages)

@app.route("/update_order/<order_id>", methods=["POST"])
@login_required
@admin_required
def update_order(order_id):
    status = request.form.get("status")
    if not status:
        flash("Status cannot be empty")
        return redirect(request.referrer)

    mongo.db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": status}}
    )

    flash("Order status updated!")
    return redirect(request.referrer)

#------------ Google maps ------------------
app.config["GOOGLE_MAPS_KEY"] = os.environ.get("GOOGLE_MAPS_KEY")

# ------------------- MESSAGES -------------------
@app.route("/send_message", methods=["POST"])
@login_required
def send_message():
    mongo.db.contact_messages.insert_one({
        "type": "order_message",
        "from": session["user"],
        "to": request.form.get("to"),
        "text": request.form.get("text"),
        "order_id": request.form.get("order_id") or "general",
        "created": datetime.utcnow()
    })

    flash("Message sent!")
    return redirect(request.referrer)

# ------------------- PROJECTS / SERVICES -------------------
@app.route("/projects")
def projects():
    projects_list = [
        {"title": "Commercial Projects", "description": "Design and layout for retail, office, and mixed-use spaces.", "image": "commercial.jpg"},
        {"title": "Industrial Facilities", "description": "Planning and structural support for factories, warehouses, and production units.", "image": "industrial.jpg"},
        {"title": "Interior Layouts", "description": "Optimized interior design for functional and aesthetic spaces.", "image": "interior_layout.png"},
        {"title": "Extensions", "description": "Seamless building expansions maintaining structural integrity.", "image": "extension.jpg"},
        {"title": "Foundations & Structural Work", "description": "Detailed foundation design and load-bearing analysis.", "image": "foundation.jpg"},
        {"title": "Renovations", "description": "Upgrading existing structures with modern engineering solutions.", "image": "renovation.jpg"},
    ]
    return render_template("projects.html", projects=projects_list)

@app.route("/services")
def services():
    services_list = [
        {"title": "CAD Drafting", "description": "Accurate 2D and 3D technical drawings for all project types.", "image": "drafting.jpg"},
        {"title": "Documentation", "description": "Complete project documentation, reports, and compliance files.", "image": "docs.jpg"},
        {"title": "Civil Engineering", "description": "Site planning, grading, drainage, and infrastructure design.", "image": "civil.jpg"},
        {"title": "MEP & Structural Design", "description": "Integrated mechanical, electrical, plumbing, and structural solutions.", "image": "mep.jpg"},
        {"title": "I-Beam & Load Calculations", "description": "Structural calculations ensuring safety and efficiency.", "image": "I_beam.jpg"},
        {"title": "Project Consultation", "description": "Expert advice from concept through construction execution.", "image": "structural.jpg"},
    ]
    return render_template("services.html", services=services_list)

# ------------------- RUN APP -------------------
if __name__ == "__main__":
    app.run(debug=True)
