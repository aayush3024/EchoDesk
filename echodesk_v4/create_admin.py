import os
from getpass import getpass

from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

load_dotenv()
uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/echodesk")
client = MongoClient(uri)
database = client.get_default_database()
users = database["users"]

name = input("Admin name: ").strip()
email = input("Admin email: ").strip().lower()
password = getpass("Admin password (minimum 12 characters): ")

if not name or not email or "@" not in email or len(password) < 12:
    raise SystemExit("Enter a valid name/email and a password of at least 12 characters.")

if users.find_one({"email": email}):
    raise SystemExit("That email is already registered. Use a different email.")

users.insert_one({
    "name": name,
    "email": email,
    "password": generate_password_hash(password),
    "role": "admin"
})
print("Admin account created.")
client.close()
