import os
import time
import sqlite3
import json
import secrets
import bcrypt
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
from werkzeug.utils import secure_filename

schema = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, email TEXT UNIQUE, password TEXT, token TEXT unique, token_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, uid INTEGER, label TEXT, status INTEGER, created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
-- type =  1 (input) 2 (output)
CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, path TEXT, type INTEGER);
-- eid = experiment ID, fid = file ID
CREATE TABLE IF NOT EXISTS experiment_files (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, eid INTEGER, fid INTEGER);
"""
insert_user = "INSERT INTO users (email, password, token) VALUES (?, ?, ?)"
insert_experiment = "INSERT INTO experiments (uid, label, status) VALUES (?, ?, ?)"
insert_file = "INSERT INTO files (path, type) VALUES (?, ?)"
insert_map = "INSERT INTO experiment_files (eid, fid) VALUES (?, ?)"


def create_app(test_config=None):
    conn = sqlite3.connect('db.sqlite')
    db = conn.cursor()
    db.executescript(schema)
    conn.commit()
    conn.close()
    app = Flask(__name__, instance_relative_config=True)
    CORS(app)
    app.config['CORS_HEADERS'] = 'no-cors'

    # Helpers

    def create_conn():
        conn = sqlite3.connect('db.sqlite')
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
        if args.get('token'):
            res = db.execute(
                "SELECT COUNT(*) FROM users WHERE token = ? AND token_created >= date('now', '-1 days')", (args.get('token'),)).fetchone()
            return res[0] == 1
        return False

    def login(db, args):
        if args.get('email') and args.get('password'):
            hashed = db.execute(
                'SELECT password FROM users WHERE email = ?', (args.get('email'),)).fetchone()
            if hashed:
                return check_password(args.get('password'), hashed[0])
        return False

    # Routes

    @app.route('/users/new', methods=['POST', 'OPTIONS'])
    @cross_origin()
    def create_user():
        conn, db = create_conn()
        email = request.form.get('email')
        password = get_hashed_password(request.form.get('password'))
        token = get_token()
        db.execute(insert_user, (email, password, token))
        conn.commit()
        conn.close()
        return jsonify({'token': token})

    @app.route('/users/auth', methods=['POST', 'OPTIONS'])
    @cross_origin()
    def auth_user():
        conn, db = create_conn()
        if login(db, request.form):
            token = get_token()
            db.execute("UPDATE users SET token = ? WHERE email = ?",
                       (token, request.form.get('email'),))
            conn.commit()
            conn.close()
            return jsonify({'token': token})
        conn.close()
        return jsonify({'token': None, 'error': 'invalid credentials'})

    @app.route('/experiments', methods=['GET'])
    @cross_origin()
    def experiments():
        conn, db = create_conn()
        if not is_authd(db, request.form):
            conn.close()
            return jsonify({'error': 'must be logged in'})
        conn.close()
        return jsonify(True)

    @app.route('/experiments/new', methods=['POST', 'OPTIONS'])
    @cross_origin()
    def new_experiment():
        conn, db = create_conn()
        if not is_authd(db, request.form):
            conn.close()
            return jsonify({'error': 'must be logged in'})
        uid = db.execute("SELECT id FROM users WHERE token = ?",
                         (request.form.get('token'),)).fetchone()[0]
        db.execute(insert_experiment,
                   (uid, request.form.get("label"), 0))
        eid = db.lastrowid
        job_folder = os.path.join(os.environ['UPLOAD_FOLDER'], str(uid), "submitted", str(eid))
        os.makedirs(job_folder, exist_ok=True)
        request_dict = request.form.to_dict(flat=True)
        del request_dict['token']
        request_dict['createdAt'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        request_dict['ownerId'] = uid
        request_dict['_id'] = eid
        # each user is allowed 50 files, and no one file can exceed 1G
        user_files = db.execute(
                "SELECT COUNT(*) FROM files WHERE id IN (SELECT fid FROM experiment_files WHERE eid IN (SELECT id FROM experiments WHERE uid = ?))", (uid,)).fetchone()[0]
        remaining = 50 - user_files
        if remaining < len(request.files):
            conn.close()
            return jsonify({'error': 'The %d files you tried to upload exceed the %d remaining files you have left in your quota' % (len(request.files), remaining)})
        for file in request.files.values():
            if file.filename != '':
                secure_fn = secure_filename(file.filename)
                dest = os.path.join(job_folder, secure_fn)
                file.save(dest)
                # possible to determine file size before writing to disk?
                if os.path.getsize(dest) > 1073741824: # 1GB in bytes
                    os.remove(dest)
                    conn.close()
                    return jsonify({'error': 'The file "%s" exceeds the 1GB file size limit' % (file.filename,)})
                db.execute(insert_file, (dest, 0))
                fid = db.lastrowid
                db.execute(insert_map, (eid, fid))
        conn.commit()
        conn.close()
        os.makedirs(os.path.join(os.environ['UPLOAD_FOLDER'], job_folder), exist_ok=True)
        with open(os.path.join(os.environ['UPLOAD_FOLDER'], job_folder, "params.json"), 'w') as f:
            f.write(json.dumps(request_dict))
        return jsonify(True)

    return app


create_app()
