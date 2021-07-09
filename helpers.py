import sqlite3
import bcrypt
import secrets


def create_conn():
    conn = sqlite3.connect("db.sqlite")
    return conn, conn.cursor()


def get_hashed_password(plain_text_password):
    # Hash a password for the first time
    #   (Using bcrypt, the salt is saved into the hash itself)
    return bcrypt.hashpw(plain_text_password, bcrypt.gensalt())


def check_password(plain_text_password, hashed_password):
    # Check hashed password. Using bcrypt, the salt is saved into the hash itself
    return bcrypt.checkpw(plain_text_password, hashed_password)


def get_token():
    return secrets.token_urlsafe()


def is_authd(db, args):
    if args.get("token"):
        res = db.execute(
            "SELECT COUNT(*) FROM users WHERE token = ? AND token_created >= date('now', '-1 days')",
            (args.get("token"),),
        ).fetchone()
        return res[0] == 1
    return False


def login(db, args):
    if args.get("email") and args.get("password"):
        hashed = db.execute(
            "SELECT password FROM users WHERE email = ?", (args.get("email"),)
        ).fetchone()
        if hashed:
            return check_password(args.get("password"), hashed[0])
    return False
