import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

if os.path.exists("env.py"):
    import env

app = Flask(__name__)

# MongoDB configuration
app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


# -------------------- HOME / TICKETS --------------------
@app.route("/")
@app.route("/tickets")
def get_tickets():
    tickets = mongo.db.CADTickets.find()
    return render_template("tickets.html", tickets=tickets, user=session.get("user"))


# -------------------- ADD TICKET --------------------
@app.route("/add_ticket", methods=["POST"])
def add_ticket():
    if "user" not in session:
        flash("Please login first!")
        return redirect(url_for("login"))

    ticket = {
        "title": request.form.get("title"),
        "description": request.form.get("description"),
        "status": request.form.get("status"),
        "author": session["user"]
    }
    mongo.db.CADTickets.insert_one(ticket)
    flash("Ticket added successfully!")
    return redirect(url_for("get_tickets"))


# -------------------- DELETE TICKET --------------------
@app.route("/delete_ticket/<ticket_id>")
def delete_ticket(ticket_id):
    if "user" not in session:
        flash("Please login first!")
        return redirect(url_for("login"))

    mongo.db.CADTickets.delete_one({"_id": ObjectId(ticket_id)})
    flash("Ticket deleted!")
    return redirect(url_for("get_tickets"))


# -------------------- REGISTER --------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")

        existing_user = mongo.db.users.find_one({"username": username})
        if existing_user:
            flash("Username already exists")
            return redirect(url_for("register"))

        mongo.db.users.insert_one({
            "username": username,
            "password": generate_password_hash(password)
        })
        session["user"] = username
        flash("Registration successful!")
        return redirect(url_for("get_tickets"))

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
            return redirect(url_for("get_tickets"))
        else:
            flash("Incorrect username or password")
            return redirect(url_for("login"))

    return render_template("login.html")


# -------------------- LOGOUT --------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out")
    return redirect(url_for("login"))

@app.route("/about")
def about():
    return render_template("about.html", user=session.get("user"))

@app.route("/services")
def services():
    return render_template("services.html", user=session.get("user"))

@app.route("/contact")
def contact():
    return render_template("contact.html", user=session.get("user"))

# -------------------- RUN APP --------------------
if __name__ == "__main__":
    app.run()
