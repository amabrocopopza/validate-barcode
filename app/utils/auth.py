# app/utils/auth.py

from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app as app

auth = HTTPBasicAuth()

# In a real-world scenario, use a database to store users
users = {
    "a": generate_password_hash("a"),
    # Add more users as needed
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None
