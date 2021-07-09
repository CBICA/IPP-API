import os
import time
import sqlite3
import json
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
from werkzeug.utils import secure_filename
from .helpers import *

STATUS_MAP = ["submitted", "completed"]
schema = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, email TEXT UNIQUE, password TEXT, token TEXT unique, token_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, uid INTEGER, label TEXT, created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, path TEXT);
-- eid = experiment ID, fid = file ID
CREATE TABLE IF NOT EXISTS experiment_files (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, eid INTEGER, fid INTEGER);
"""
insert_user = "INSERT INTO users (email, password, token) VALUES (?, ?, ?)"
insert_experiment = "INSERT INTO experiments (uid, label) VALUES (?, ?)"
insert_file = "INSERT INTO files (path) VALUES (?)"
insert_map = "INSERT INTO experiment_files (eid, fid) VALUES (?, ?)"


def create_app(test_config=None):
    conn = sqlite3.connect("db.sqlite")
    db = conn.cursor()
    db.executescript(schema)
    conn.commit()
    conn.close()
    app = Flask(__name__, instance_relative_config=True)
    CORS(app)
    app.config["CORS_HEADERS"] = "no-cors"

    # Routes

    @app.route("/users/new", methods=["POST", "OPTIONS"])
    @cross_origin()
    def create_user():
        conn, db = create_conn()
        email = request.form.get("email")
        password = get_hashed_password(request.form.get("password"))
        token = get_token()
        db.execute(insert_user, (email, password, token))
        conn.commit()
        conn.close()
        return jsonify({"token": token})

    @app.route("/users/auth", methods=["POST", "OPTIONS"])
    @cross_origin()
    def auth_user():
        conn, db = create_conn()
        if login(db, request.form):
            token = get_token()
            db.execute(
                "UPDATE users SET token = ? WHERE email = ?",
                (
                    token,
                    request.form.get("email"),
                ),
            )
            conn.commit()
            conn.close()
            return jsonify({"token": token})
        conn.close()
        return jsonify({"token": None, "error": "invalid credentials"})

    @app.route("/experiments", methods=["GET"])
    @cross_origin()
    def experiments():
        conn, db = create_conn()
        if not is_authd(db, request.args):
            conn.close()
            return jsonify({"error": "must be logged in"})
        uid = db.execute(
            "SELECT id FROM users WHERE token = ?", (request.args.get("token"),)
        ).fetchone()[0]
        res = []
        rows = db.execute(
            "SELECT id, label, created FROM experiments WHERE uid = ?", (uid,)
        ).fetchall()
        for r in rows:
            output_files = os.listdir(
                os.path.join(
                    os.environ["UPLOAD_FOLDER"], str(uid), "completed", str(r[0])
                )
            )
            input_files = db.execute(
                "SELECT path FROM files WHERE id IN (SELECT fid FROM experiment_files WHERE eid = ?)",
                (r[0],),
            ).fetchall()
            status_code = 0 if len(output_files) == 0 else 1
            user_folder = os.path.join(os.environ["UPLOAD_FOLDER"], str(uid))
            params = json.load(
                open(
                    os.path.join(
                        user_folder,
                        STATUS_MAP[status_code],
                        str(r[0]),
                        "params.json",
                    )
                )
            )
            status = json.load(
                open(
                    os.path.join(
                        user_folder,
                        STATUS_MAP[status_code],
                        str(r[0]),
                        "status.json",
                    )
                )
            )
            res.append(
                {
                    "id": r[0],
                    "label": r[1],
                    "created": r[2],
                    "status_code": status_code,
                    "status": status,
                    "inputs": list(map(lambda x: os.path.basename(x[0]), input_files)),
                    "outputs": output_files,
                    "params": params,
                }
            )
        conn.close()
        return jsonify({"experiments": res})

    @app.route("/experiments/new", methods=["POST", "OPTIONS"])
    @cross_origin()
    def new_experiment():
        conn, db = create_conn()
        if not is_authd(db, request.form):
            conn.close()
            return jsonify({"error": "must be logged in"})
        uid = db.execute(
            "SELECT id FROM users WHERE token = ?", (request.form.get("token"),)
        ).fetchone()[0]
        db.execute(insert_experiment, (uid, request.form.get("label")))
        eid = db.lastrowid
        user_folder = os.path.join(os.environ["UPLOAD_FOLDER"], str(uid))
        job_folder = os.path.join(user_folder, "submitted", str(eid))
        completed_job_folder = os.path.join(user_folder, "completed", str(eid))
        edited_job_folder = os.path.join(user_folder, "edited", str(eid))
        os.makedirs(job_folder, exist_ok=True)
        os.makedirs(completed_job_folder, exist_ok=True)
        os.makedirs(edited_job_folder, exist_ok=True)
        request_dict = request.form.to_dict(flat=True)
        del request_dict["token"]
        request_dict["createdAt"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        request_dict["ownerId"] = uid
        request_dict["_id"] = eid
        # each user is allowed 50 files, and no one file can exceed 1G
        user_files = db.execute(
            "SELECT COUNT(*) FROM files WHERE id IN (SELECT fid FROM experiment_files WHERE eid IN (SELECT id FROM experiments WHERE uid = ?))",
            (uid,),
        ).fetchone()[0]
        remaining = 50 - user_files
        if remaining < len(request.files):
            conn.close()
            return jsonify(
                {
                    "error": "The %d files you tried to upload exceed the %d remaining files you have left in your quota"
                    % (len(request.files), remaining)
                }
            )
        for file in request.files.values():
            if file.filename != "":
                secure_fn = secure_filename(file.filename)
                dest = os.path.join(job_folder, secure_fn)
                file.save(dest)
                # possible to determine file size before writing to disk?
                if os.path.getsize(dest) > 1073741824:  # 1GB in bytes
                    os.remove(dest)
                    conn.close()
                    return jsonify(
                        {
                            "error": 'The file "%s" exceeds the 1GB file size limit'
                            % (file.filename,)
                        }
                    )
                db.execute(insert_file, (dest,))
                fid = db.lastrowid
                db.execute(insert_map, (eid, fid))
        conn.commit()
        conn.close()
        with open(os.path.join(job_folder, "params.json"), "w") as f:
            f.write(json.dumps(request_dict))
        with open(os.path.join(job_folder, "status.json"), "w") as f:
            f.write(json.dumps({"status": "pending"}))
        return jsonify(True)

    return app


create_app()
