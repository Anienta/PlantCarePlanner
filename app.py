import re
import secrets

from cs50 import SQL
from os.path import splitext
from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session
from flask_mail import Mail, Message
from datetime import datetime, timedelta, date
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
from helpers import apology, login_required, convert_date_time_from_sql_to_python, convert_date_from_sql_to_python
from PIL import Image

# Configure application
app = Flask(__name__)
# Configure mail
app.config['MAIL_DEFAULT_SENDER'] = 'your@mail.com'
app.config['MAIL_SERVER'] = 'mail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'your@mail.com'
app.config['MAIL_PASSWORD'] = 'yourPassword'
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)

max_width = 120
max_height = 120

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///plants.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def entry():
    if "user_id" in session:
        return homepage()
    return render_template("index.html")


@app.route("/home")
def homepage():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/inspirations")
def inspirations():
    return render_template("inspirations.html")


@app.route("/planner")
@login_required
def planner():
    """Display user plants"""
    plants = db.execute("SELECT * FROM plants where user_id = ?", session["user_id"])
    plant_list = []
    for plant in plants:
        plant_id = plant["id"]
        plant_name = plant["name"]
        image_url = plant["picture_url"]
        plant_description = plant["description"]
        watering_frequency = plant["watering_frequency"]
        fertilizing_frequency = plant["fertilizing_frequency"]
        last_watering_date = plant["last_watering"]
        last_fertilizing_date = plant["last_fertilizing"]
        last_watering_date = convert_date_from_sql_to_python(last_watering_date)
        last_fertilizing_date = convert_date_from_sql_to_python(last_fertilizing_date)
        watering_deadline = last_watering_date + timedelta(days=watering_frequency)
        fertilizing_deadline = last_fertilizing_date + timedelta(days=fertilizing_frequency)

        warnings = []

        watering_delta = date.today() - watering_deadline
        fertilizing_delta = date.today() - fertilizing_deadline
        if watering_delta.days > 0:
            warnings.append(f'You missed watering time by {watering_delta.days} days')
        if fertilizing_delta.days > 0:
            warnings.append(f'You missed fertilizing time by {fertilizing_delta.days} days')

        days_from_last_watering = date.today() - last_watering_date
        days_from_last_fertilizing = date.today() - last_fertilizing_date

        single_plant = {"image_url": image_url,
                        "name": plant_name,
                        "description": plant_description,
                        "warnings": warnings,
                        "plant_id": plant_id,
                        "last_fertilizing_date": days_from_last_fertilizing.days,
                        "last_watering_date": days_from_last_watering.days}

        plant_list.append(single_plant)

    return render_template("planner.html", plant_list=plant_list)


@app.route("/add_plant", methods=["GET", "POST"])
@login_required
def add_plant():
    if request.method == "POST":
        plantname = request.form.get("plantname")
        if not plantname:
            return apology("must provide plantname", 400)
        plantdescription = request.form.get("plantdescription")
        approx_watering = request.form.get("approx_watering")
        if not approx_watering:
            return apology("must provide approx_watering", 400)
        approx_fertilize = request.form.get("approx_fertilize")
        if not approx_fertilize:
            return apology("must provide approx_fertilize", 400)
        image_url = upload_image_if_valid_and_return_image_url()
        db.execute("INSERT INTO plants (name, picture_url, user_id, description, watering_frequency, "
                   "fertilizing_frequency) "
                   "VALUES (?, ?, ?, ?, ?, ?)",
                   plantname, image_url, session["user_id"], plantdescription, approx_watering, approx_fertilize)
        return redirect("/planner")
    return redirect("/planner")


def upload_image_if_valid_and_return_image_url():
    image = request.files.get('image')
    image_filename = secure_filename(image.filename)
    image_url = None
    if image_filename:
        _, file_extension = splitext(image.filename)
        img_name = secrets.token_hex(16)
        if file_extension in ('.png', '.jpg', '.jpeg'):
            # Calculate the new width and height of the image
            image = Image.open(image)
            image = resize_and_crop_plant_image(image)
            image.save(f'static/uploaded_images/{img_name}{file_extension}')
            image_url = url_for('static', filename=f'uploaded_images/{img_name}{file_extension}')
    return image_url


def resize_and_crop_plant_image(image):
    aspect_ratio = image.width / image.height
    if aspect_ratio > 1:
        # Portrait orientation (width < height)
        new_height = max_height
        new_width = int(new_height * aspect_ratio)
    elif aspect_ratio < 1:
        # Landscape orientation (width > height)
        new_width = max_width
        new_height = int(new_width / aspect_ratio)
    else:
        # Square image
        new_width = max_width
        new_height = max_height
    image = image.resize((new_width, new_height))
    # Crop the image to the desired dimensions
    if new_width > max_width or new_height > max_height:
        left = (image.width - max_width) // 2
        top = (image.height - max_height) // 2
        right = (image.width + max_width) // 2
        bottom = (image.height + max_height) // 2
        image = image.crop((left, top, right, bottom))
    return image


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure username was submitted
        if not username:
            return apology("must provide username or e-mail", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ? OR email = ?", username, username)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return render_template("home.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        session.clear()
        email = request.form.get("email")
        password = request.form.get("password")
        username = request.form.get("username")
        confirmation = request.form.get("confirmation")

        # Ensure email was submitted
        if not email:
            return apology("must provide email", 400)

        # Ensure is similar to email
        if not re.fullmatch(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+', email):
            return apology("is not email", 400)

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        if not password:
            return apology("must provide password", 400)

        if not confirmation:
            return apology("must confirm password", 400)

        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        if not re.fullmatch(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
            return render_template("register.html", w="w")

        # Query database for userData
        users_data = db.execute("SELECT username, email, isactive, registration_date "
                                "FROM users WHERE username = ? OR email = ?", username, email)

        if users_data:
            for userData in users_data:
                datetime_object = convert_date_time_from_sql_to_python(userData["registration_date"])
                datetime_object_plus_24_hours = datetime_object + timedelta(hours=24)
                if userData["isactive"] == 0:
                    if datetime_object_plus_24_hours < datetime.now():
                        return apology("Click confirmation link or register again after 24 hours from last attempt.",
                                       400)
                    else:
                        db.execute("DELETE FROM users WHERE (username = ? OR email = ?) AND isactive = 0", username,
                                   email)
                elif userData["isactive"] == 1:
                    return apology("Username/e-mail already exists.", 400)

        hashed_password = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash, email) VALUES (?, ?, ?)", username, hashed_password, email)

        token = secrets.token_hex(16)
        session[token] = {'email': email, 'expires_at': datetime.utcnow() + timedelta(hours=24)}

        # Send an email with the confirmation link
        msg = Message()
        msg.recipients = [email]
        msg.subject = username + ' welcome to Plant Care Planner!'
        msg.body = 'Click url address to confirm your e-mail: ' + 'https://plant-care-planner.herokuapp.com' \
                                                                  '/confirm_email/' + token
        msg.sender = ('Plant Care Planner', 'iwilad@prokonto.pl')
        mail.send(msg)

        return render_template('register_success.html')
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    """Log user out"""
    # Forget any user_id
    session.clear()
    # Redirect user to login form
    return redirect("/home")


@app.route('/confirm_email/<token>')
def confirm_email(token):
    # Check if the confirmation token is valid and has not expired
    if token in session:
        # Mark the user's account as confirmed and redirect them to the confirmation page
        email = session[token]['email']
        expires_at = session[token]['expires_at']
        session.clear()
        if expires_at > datetime.now():
            db.execute("UPDATE users SET isactive = 1 WHERE email = ?", email)
            user = db.execute("SELECT id, registration_date FROM users WHERE email = ?", email)
            session["user_id"] = user[0]["id"]
            return render_template('confirmation.html', s="s")
        else:
            return render_template('confirmation.html')
    return render_template('confirmation.html')


@app.route('/water_plant/<plant_id>')
@login_required
def water_plant(plant_id):
    db.execute("UPDATE plants SET last_watering = CURRENT_DATE WHERE id = ? AND user_id = ?", plant_id, session["user_id"])
    return redirect("/planner")


@app.route('/fertilize_plant/<plant_id>')
@login_required
def fertilize_plant(plant_id):
    db.execute("UPDATE plants SET last_fertilizing = CURRENT_DATE WHERE id = ? AND user_id = ?", plant_id, session["user_id"])
    return redirect("/planner")


@app.route('/remove_plant/<plant_id>')
@login_required
def remove_plant(plant_id):
    db.execute("DELETE FROM plants WHERE user_id = ? AND id = ?", session["user_id"], plant_id)
    return redirect("/planner")


@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return rendered apology instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    return apology(e.name, e.code)
