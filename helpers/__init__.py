import os
import sqlite3
import bcrypt
import secrets
import smtplib
import requests
import json
import zipfile
import io
from email.mime.text import MIMEText


def zipdir(path):
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        for root, dirs, files in os.walk(path):
            for file in files:
                zf.write(os.path.join(root, file))
    memory_file.seek(0)
    return memory_file


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
            "SELECT COUNT(*) FROM users WHERE token = ? AND approved = 1 AND token_created >= date('now', '-1 days')",
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


def send_email(to, message, subject=""):
    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = "ipp@cbica.upenn.edu"
    msg["To"] = to
    s = smtplib.SMTP("localhost")
    s.send_message(msg)
    s.quit()


def send_slack_message(to, message, channel=None):
    payload = {"text": message, "username": "Image Processing Portal"}
    if channel:
        payload["channel"] = channel
    response = requests.post(
        to,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    return response.status_code == 200


def notify_admin(request, uid):
    user_form = request.form.to_dict(flat=True)
    del user_form["password"]
    del user_form["confirm-password"]
    del user_form["remember"]
    message = (
        "Approve new account?"
        + json.dumps(user_form)
        + "\nClick %susers/approve/%d to approve" % (request.url_root, uid)
    )
    if "ADMIN_EMAIL" in os.environ:
        send_email(os.environ["ADMIN_EMAIL"], message)
    if "ADMIN_SLACK" in os.environ:
        send_slack_message(os.environ["ADMIN_SLACK"], message)


def extract_params(params, backend=False):
    new_params = {}
    app = experimentDescription = experimentName = ""
    for param in params:
        if param[0] == "app":
            app = param[1]
        elif param[0] == "experimentDescription":
            experimentDescription = param[1]
        elif param[0] == "experimentName":
            experimentName = param[1]
        else:
            # the backend server places downloaded files in "inputs"
            new_params[param[0]] = (
                param[1]
                if not backend or not param[1].startswith(os.environ["UPLOAD_FOLDER"])
                else "inputs" + param[1]
            )
    return app, experimentDescription, experimentName, new_params
