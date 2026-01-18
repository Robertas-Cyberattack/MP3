import os
from flask import Flask, render_template, redirect, request, session, url_for
from flask_pymongo import PyMongo
from bson.objectid import ObjectId

if os.path.exists("env.py"):
    import env

app = Flask(__name__)

# MongoDB konfiguracija
app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")  #: "CADDB"
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


@app.route("/")
@app.route("/tickets")
def get_tickets():
    # Prisij. prie CADTickets kolekcijos
    tickets = mongo.db.CADTickets.find()
    return render_template("tickets.html", tickets=tickets)


@app.route("/add_ticket", methods=["POST"])
def add_ticket():
    # Pavyzdys kaip pridėti naują tiketą iš formos
    ticket = {
        "title": request.form.get("title"),
        "description": request.form.get("description"),
        "status": request.form.get("status")
    }
    mongo.db.CADTickets.insert_one(ticket)
    return redirect(url_for("get_tickets"))


@app.route("/delete_ticket/<ticket_id>")
def delete_ticket(ticket_id):
    mongo.db.CADTickets.delete_one({"_id": ObjectId(ticket_id)})
    return redirect(url_for("get_tickets"))


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)