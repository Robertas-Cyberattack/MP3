import os
from flask import Flask, render_template
from flask_pymongo import PyMongo

if os.path.exists("env.py"):
    import env


app = Flask(__name__)

# MongoDB configuration
app.config["MONGO_DBNAME"] = os.environ.get("CADDB")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


@app.route("/", methods=["GET", "POST"])
@app.route("/get_tickets", methods=["GET", "POST"])
def get_tickets():
    cad_tickets = list(mongo.db.CADTickets.find())
    return render_template("tickets.html", tickets=cad_tickets)


@app.route("/get_tickets")
def get_tickets():
    cad_tickets = mongo.db.CADTickets.find()
    return render_template("tickets.html", tickets=cad_tickets)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("IP"),
        port=int(os.environ.get("PORT")),
        debug=True
    )

"""
import os
import pymongo

if os.path.exists("env.py"):
    import env

MONGO_URI = os.environ.get("MONGO_URI")
print(MONGO_URI)

DATABASE = "CADDB"
COLLECTION = "CADProjects"

def mongo_connect(url):
    try:
        conn = pymongo.MongoClient(url)
        print("Mongo is connected")
        return conn
    except pymongo.errors.ConnectionFailure as e:
        print("Could not connect to MongoDB: %s" % e)
        return None

conn = mongo_connect(MONGO_URI)

if conn is None:
    print("Connection failed, exiting")
    exit()

coll = conn[DATABASE][COLLECTION]

# UPDATE
result = coll.update_one(
    {"first": "placeholder-first2"},
    {"$set": {"last": "holderlast"}}
)

print("Matched:", result.matched_count)
print("Modified:", result.modified_count)

# FIND (kad pamatytum rezultatą)
documents = coll.find({"first": "placeholder-first2"})

for doc in documents:
    print(doc)
"""