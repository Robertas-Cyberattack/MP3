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
app.config["MAIL_DEFAULT_SENDER"] = ("Precision Drafting & Engineering", "robertas.sladkevicius@gmail.com")
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

# Google Maps API Key
app.config["GOOGLE_MAPS_KEY"] = os.environ.get("GOOGLE_MAPS_KEY")


# ------------------- HELPERS -------------------
def norm_username(value: str) -> str:
    return (value or "").strip().lower()


def find_user_by_username_anycase(username_input: str):
    """
    Finds user by:
      - username_lower (preferred for new data)
      - fallback exact username (for older records)
      - fallback case-insensitive regex on username (for older records)
    """
    u_lower = norm_username(username_input)
    if not u_lower:
        return None

    user = mongo.db.users.find_one({"username_lower": u_lower})
    if user:
        return user

    # Fallbacks for old data without username_lower
    user = mongo.db.users.find_one({"username": username_input})
    if user:
        return user

    # Case-insensitive fallback (still safe because we only match exact full string)
    user = mongo.db.users.find_one({"username": {"$regex": f"^{username_input}$", "$options": "i"}})
    return user


def ensure_user_lower_fields(user_doc: dict):
    """
    For older user records, make sure username_lower exists.
    Does not change displayed username.
    """
    if not user_doc:
        return
    if not user_doc.get("username_lower") and user_doc.get("username"):
        mongo.db.users.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"username_lower": norm_username(user_doc["username"])}}
        )


# ------------------- ENSURE ADMIN USER EXISTS -------------------
def ensure_admin_user():
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    admin_email = os.environ.get("ADMIN_EMAIL", "robertas.sladkevicius@gmail.com")

    if not admin_username or not admin_password:
        return

    admin_lower = norm_username(admin_username)

    existing = mongo.db.users.find_one({"username_lower": admin_lower})
    if not existing:
        # fallback for old DBs
        existing = mongo.db.users.find_one({"username": {"$regex": f"^{admin_username}$", "$options": "i"}})

    if existing:
        ensure_user_lower_fields(existing)
        if existing.get("role") != "admin":
            mongo.db.users.update_one({"_id": existing["_id"]}, {"$set": {"role": "admin"}})
        return

    mongo.db.users.insert_one({
        "username": admin_username,
        "username_lower": admin_lower,
        "email": admin_email,
        "phone": "",
        "password": generate_password_hash(admin_password),
        "role": "admin"
    })


with app.app_context():
    try:
        ensure_admin_user()
    except Exception as e:
        print("ADMIN SEED ERROR:", e)


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
        flash("Failed to send email. Check SENDGRID_API_KEY and verified sender in SendGrid.")

    return redirect(url_for("contact"))


# ------------------- REGISTER / LOGIN -------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        username_lower = norm_username(username)

        email = request.form.get("email")
        phone = request.form.get("phone")
        password = generate_password_hash(request.form.get("password"))

        if not username_lower:
            flash("Username cannot be empty")
            return redirect(url_for("register"))

        # Case-insensitive uniqueness check
        if mongo.db.users.find_one({"username_lower": username_lower}) or mongo.db.users.find_one(
            {"username": {"$regex": f"^{username}$", "$options": "i"}}
        ):
            flash("Username already exists")
            return redirect(url_for("register"))

        mongo.db.users.insert_one({
            "username": username,
            "username_lower": username_lower,
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
        username_input = request.form.get("username")
        user = find_user_by_username_anycase(username_input)

        if user:
            ensure_user_lower_fields(user)

        if user and check_password_hash(user["password"], request.form.get("password")):
            session["user"] = user["username"]  # display
            session["user_lower"] = user.get("username_lower") or norm_username(user.get("username"))
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
    user_lower = session.get("user_lower") or norm_username(session.get("user"))

    # Support both old orders (clientno only) and new orders (clientno_lower)
    orders = list(mongo.db.orders.find({
        "$or": [
            {"clientno": session["user"]},
            {"clientno_lower": user_lower}
        ]
    }))

    for order in orders:
        order_id_str = str(order["_id"])

        # messages: support new fields (from_lower/to_lower) and old fields (from/to)
        order["messages"] = list(
            mongo.db.contact_messages.find({
                "type": "order_message",
                "order_id": order_id_str,
                "$or": [
                    {"to_lower": user_lower},
                    {"from_lower": user_lower},
                    {"to": session["user"]},
                    {"from": session["user"]}
                ]
            }).sort("created", 1)
        )

        # last message sent by THIS client for this order (for edit)
        last_sent = mongo.db.contact_messages.find_one(
            {
                "type": "order_message",
                "order_id": order_id_str,
                "$or": [
                    {"from_lower": user_lower},
                    {"from": session["user"]}
                ]
            },
            sort=[("created", -1)]
        )
        order["last_sent_message_id"] = str(last_sent["_id"]) if last_sent else None

        if "comments" not in order:
            order["comments"] = []

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

    user_lower = session.get("user_lower") or norm_username(session.get("user"))

    order_doc = {
        "clientno": session["user"],
        "clientno_lower": user_lower,
        "status": "Pending",
        "progress": 0,
        "file": filenames,
        "comments": [],
        "date": datetime.utcnow()
    }

    result = mongo.db.orders.insert_one(order_doc)
    new_order_id = str(result.inserted_id)

    initial_message = request.form.get("initial_message", "").strip()
    if initial_message:
        mongo.db.contact_messages.insert_one({
            "type": "order_message",
            "from": session["user"],
            "from_lower": user_lower,
            "to": "admin",
            "to_lower": "admin",
            "text": initial_message,
            "order_id": new_order_id,
            "created": datetime.utcnow()
        })

    flash("Order uploaded!")
    return redirect(url_for("dashboard"))


@app.route("/delete_order/<order_id>", methods=["POST"])
@login_required
def delete_order(order_id):
    # allow delete old + new storage
    user_lower = session.get("user_lower") or norm_username(session.get("user"))

    mongo.db.orders.delete_one({
        "_id": ObjectId(order_id),
        "$or": [
            {"clientno": session["user"]},
            {"clientno_lower": user_lower}
        ]
    })
    flash("Order deleted")
    return redirect(url_for("dashboard"))


# ------------------- ADMIN DASHBOARD -------------------
@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    orders = list(mongo.db.orders.find())
    users = list(mongo.db.users.find({"role": "client"}))

    # Make sure users have username_lower (migration-like behavior)
    for u in users:
        ensure_user_lower_fields(u)

    admin_lower = session.get("user_lower") or norm_username(session.get("user"))

    for order in orders:
        order_id_str = str(order["_id"])

        order["messages"] = list(
            mongo.db.contact_messages.find({
                "type": "order_message",
                "order_id": order_id_str
            }).sort("created", 1)
        )

        # last message sent by ADMIN for this order (for edit)
        last_admin = mongo.db.contact_messages.find_one(
            {
                "type": "order_message",
                "order_id": order_id_str,
                "$or": [
                    {"from_lower": admin_lower},
                    {"from": session["user"]}
                ]
            },
            sort=[("created", -1)]
        )
        order["last_admin_message_id"] = str(last_admin["_id"]) if last_admin else None

        if "comments" not in order:
            order["comments"] = []

    return render_template("admin.html", orders=orders, users=users)


@app.route("/update_order/<order_id>", methods=["POST"])
@login_required
@admin_required
def update_order(order_id):
    status = request.form.get("status")
    progress_raw = request.form.get("progress")

    if status is None or status.strip() == "":
        flash("Status cannot be empty")
        return redirect(request.referrer)

    update_doc = {"status": status}

    if progress_raw is not None and progress_raw != "":
        try:
            progress_val = int(progress_raw)
            if progress_val < 0:
                progress_val = 0
            if progress_val > 100:
                progress_val = 100
            update_doc["progress"] = progress_val
        except ValueError:
            flash("Progress must be a number between 0 and 100")
            return redirect(request.referrer)

    mongo.db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": update_doc}
    )

    flash("Order updated!")
    return redirect(request.referrer)


@app.route("/admin/delete_order/<order_id>", methods=["POST"])
@login_required
@admin_required
def admin_delete_order(order_id):
    mongo.db.orders.delete_one({"_id": ObjectId(order_id)})
    mongo.db.contact_messages.delete_many({"type": "order_message", "order_id": str(order_id)})
    flash("Order deleted")
    return redirect(request.referrer)


@app.route("/admin/edit_user/<user_id>", methods=["POST"])
@login_required
@admin_required
def admin_edit_user(user_id):
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    if not email or not phone:
        flash("Email and phone cannot be empty")
        return redirect(request.referrer)

    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"email": email, "phone": phone}}
    )

    flash("User updated")
    return redirect(request.referrer)


@app.route("/admin/delete_user/<user_id>", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash("User not found")
        return redirect(request.referrer)

    username = user.get("username")
    username_lower = user.get("username_lower") or norm_username(username)

    user_orders = list(mongo.db.orders.find({
        "$or": [
            {"clientno": username},
            {"clientno_lower": username_lower}
        ]
    }))
    for o in user_orders:
        mongo.db.contact_messages.delete_many({"type": "order_message", "order_id": str(o["_id"])})

    mongo.db.orders.delete_many({
        "$or": [
            {"clientno": username},
            {"clientno_lower": username_lower}
        ]
    })
    mongo.db.users.delete_one({"_id": ObjectId(user_id)})

    flash("User and their orders deleted")
    return redirect(request.referrer)


# ------------------- ORDER COMMENTS (ADMIN) -------------------
@app.route("/admin/add_comment/<order_id>", methods=["POST"])
@login_required
@admin_required
def admin_add_comment(order_id):
    text = request.form.get("text", "").strip()
    if not text:
        flash("Comment cannot be empty")
        return redirect(request.referrer)

    mongo.db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$push": {"comments": {"text": text, "created": datetime.utcnow().strftime("%Y-%m-%d %H:%M")}}}
    )

    flash("Comment added")
    return redirect(request.referrer)


@app.route("/admin/edit_comment/<order_id>/<int:idx>", methods=["POST"])
@login_required
@admin_required
def admin_edit_comment(order_id, idx):
    text = request.form.get("text", "").strip()
    if not text:
        flash("Comment cannot be empty")
        return redirect(request.referrer)

    order = mongo.db.orders.find_one({"_id": ObjectId(order_id)})
    if not order or "comments" not in order or idx < 0 or idx >= len(order["comments"]):
        flash("Comment not found")
        return redirect(request.referrer)

    mongo.db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {f"comments.{idx}.text": text}}
    )

    flash("Comment updated")
    return redirect(request.referrer)


@app.route("/admin/delete_comment/<order_id>/<int:idx>", methods=["POST"])
@login_required
@admin_required
def admin_delete_comment(order_id, idx):
    order = mongo.db.orders.find_one({"_id": ObjectId(order_id)})
    if not order or "comments" not in order or idx < 0 or idx >= len(order["comments"]):
        flash("Comment not found")
        return redirect(request.referrer)

    comments = order.get("comments", [])
    comments.pop(idx)

    mongo.db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"comments": comments}}
    )

    flash("Comment deleted")
    return redirect(request.referrer)


# ------------------- MESSAGES -------------------
@app.route("/send_message", methods=["POST"])
@login_required
def send_message():
    to_user_input = request.form.get("to")
    text = request.form.get("text")
    order_id = request.form.get("order_id") or "general"

    if not to_user_input or not text:
        flash("Message cannot be empty")
        return redirect(request.referrer)

    from_lower = session.get("user_lower") or norm_username(session.get("user"))
    to_lower = norm_username(to_user_input)

    # Client security: client can only message admin
    if session.get("role") != "admin" and to_lower != "admin":
        flash("You can only message admin.")
        return redirect(request.referrer)

    # Resolve recipient canonical username (case-insensitive)
    if to_lower == "admin":
        to_user = "admin"
        to_lower = "admin"
    else:
        target = find_user_by_username_anycase(to_user_input)
        if not target:
            flash("Target user does not exist.")
            return redirect(request.referrer)
        ensure_user_lower_fields(target)
        to_user = target["username"]
        to_lower = target.get("username_lower") or norm_username(target.get("username"))

    mongo.db.contact_messages.insert_one({
        "type": "order_message",
        "from": session["user"],
        "from_lower": from_lower,
        "to": to_user,
        "to_lower": to_lower,
        "text": text,
        "order_id": str(order_id),
        "created": datetime.utcnow()
    })

    flash("Message sent!")
    return redirect(request.referrer)


@app.route("/edit_message/<message_id>", methods=["POST"])
@login_required
def edit_message(message_id):
    new_text = request.form.get("text", "").strip()
    if not new_text:
        flash("Message cannot be empty")
        return redirect(request.referrer)

    msg = mongo.db.contact_messages.find_one({"_id": ObjectId(message_id)})
    if not msg:
        flash("Message not found")
        return redirect(request.referrer)

    current_lower = session.get("user_lower") or norm_username(session.get("user"))
    msg_from_lower = msg.get("from_lower") or norm_username(msg.get("from"))

    # Only author can edit (case-insensitive safe)
    if msg_from_lower != current_lower:
        flash("You can only edit your own messages.")
        return redirect(request.referrer)

    order_id = str(msg.get("order_id"))
Dudley Zoo and Castl
    # Must be the LAST message by this user in this order thread
    last_msg = mongo.db.contact_messages.find_one(
        {
            "type": "order_message",
            "order_id": order_id,
            "$or": [
                {"from_lower": current_lower},
                {"from": session.get("user")}
            ]
        },
        sort=[("created", -1)]
    )
    if not last_msg or str(last_msg["_id"]) != str(msg["_id"]):
        flash("You can only edit your last message.")
        return redirect(request.referrer)

    mongo.db.contact_messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"text": new_text, "edited": True, "edited_at": datetime.utcnow()}}
    )

    flash("Message updated")
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
