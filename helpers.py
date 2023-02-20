from functools import wraps
from flask import render_template, session, redirect
from datetime import datetime


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def convert_date_time_from_sql_to_python(single_datetime_from_sql):
    datetime_object = datetime.strptime(single_datetime_from_sql, '%Y-%m-%d %H:%M:%S')
    return datetime_object


def convert_date_from_sql_to_python(single_date_from_sql):
    date_object = datetime.strptime(single_date_from_sql, "%Y-%m-%d").date()
    return date_object
