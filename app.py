import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash

if os.path.exists("env.py"):
    import env

app = Flask(__name__)

# MongoDB configuration
app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)

# -------------------- HOME --------------------
@app.route("/")
def home():
    landing_content = {
        "company_name": "Precision Drafting & Engineering",
        "hero_text": "Expert CAD drafting and construction drawings for UK & Europe. All work follows British & Eurocode standards.",
        "sections": [
            {
                "title": "About Our Team",
                "text": (
                    "Our drafters hold at least a Bachelor's degree in Civil Engineering from accredited UK universities and have extensive experience "
                    "in residential, commercial, and infrastructure projects. We provide precise, professional construction documentation, "
                    "CAD drawings, and compliance checks for projects across the UK and Europe."
                ),
                "image": "placeholder.jpg",
                "image_alt": "Our Team or Office"
            },
            {
                "title": "Our Expertise",
                "text": (
                    "We specialize in CAD drafting, structural designs, MEP coordination, interior layouts, and construction documentation. "
                    "Every project is executed with attention to detail, ensuring compliance with British Building Codes and Eurocodes."
                ),
                "image": "placeholder.jpg",
                "image_alt": "Project Illustration"
            },
            {
                "title": "Our Mission",
                "text": (
                    "Our mission is to deliver high-quality, professional drafting and engineering services to clients across the UK and Europe, "
                    "helping them realize their projects efficiently and accurately."
                ),
                "image": "placeholder.jpg",
                "image_alt": "Mission Illustration"
            }
        ]
    }

    return render_template("home.html", landing=landing_content, user=session.get("user"))

# -------------------- PROJECTS --------------------
@app.route("/projects")
def projects():
    projects_list = [
        {"title":"Residential Apartment Design","description":"Complete CAD drafting for a modern apartment complex in London, following British Building Codes.","image":"project1.jpg"},
        {"title":"Commercial Office Renovation","description":"Detailed construction drawings for office space in Manchester, ensuring compliance with UK and Eurocodes.","image":"project2.jpg"},
        {"title":"Industrial Warehouse Layout","description":"Efficient CAD plans for a warehouse in Birmingham, including structural and MEP integration.","image":"project3.jpg"},
        {"title":"Bridge Engineering Project","description":"Structural and civil engineering drawings for a bridge design, following Eurocode standards.","image":"project4.jpg"},
        {"title":"Retail Store Interior Design","description":"Professional CAD drafting for a chain of retail stores across Europe.","image":"project5.jpg"},
        {"title":"Luxury Villa Development","description":"Residential luxury villa construction drawings, tailored to British standards.","image":"project6.jpg"},
    ]
    return render_template("projects.html", projects=projects_list, user=session.get("user"))

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
            "phone": phone
        })
        session["user"] = username
        flash("Registration successful!")
        return redirect(url_for("home"))
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
            flash(f"Welcome back, {username}!")
            return redirect(url_for("home"))
        flash("Incorrect username or password")
        return redirect(url_for("login"))

    return render_template("login.html")

# -------------------- LOGOUT --------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out")
    return redirect(url_for("login"))

# -------------------- ABOUT --------------------
@app.route("/about")
def about():
    return render_template("about.html", user=session.get("user"))

# -------------------- SERVICES --------------------
@app.route("/services")
def services():
    services_list = [
        "CAD drafting for residential and commercial buildings",
        "Structural drawings and compliance with Eurocodes",
        "Civil engineering designs for infrastructure projects",
        "Interior layout plans for offices and retail spaces",
        "MEP integration and coordination drawings",
        "Construction documentation for UK and EU projects"
    ]
    return render_template("services.html", services=services_list, user=session.get("user"))

# -------------------- CONTACT --------------------
@app.route("/contact")
def contact():
    return render_template("contact.html", user=session.get("user"))

# -------------------- RUN APP --------------------
if __name__ == "__main__":
    app.run(debug=True)

