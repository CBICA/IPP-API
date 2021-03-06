import os
import time
import sqlite3
import json
import zipfile
import tempfile
import shutil
import glob
import sys
import subprocess
from datetime import datetime
from flask import (
    Flask,
    jsonify,
    request,
    send_file,
    redirect,
    send_from_directory,
    abort,
)
from flask_cors import CORS, cross_origin
from werkzeug.utils import secure_filename
from flask import render_template  # only for admin pages
import helpers

STATUS_SUBMITTED = 0
STATUS_QUEUED = 1
STATUS_COMPLETED = 2
STATUS_FAILED = 3
schema = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, email TEXT UNIQUE, password TEXT, token TEXT unique, token_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP, approved BOOLEAN DEFAULT 0);
CREATE TABLE IF NOT EXISTS user_settings (uid INTEGER, name TEXT, value TEXT, UNIQUE(uid, name) ON CONFLICT REPLACE, PRIMARY KEY(uid, name));
CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS user_groups (uid INTEGER, gid INTEGER, UNIQUE(uid, gid) ON CONFLICT REPLACE);
CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, uid INTEGER, label TEXT, host TEXT, status INTEGER DEFAULT 0, created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS experiment_settings (eid INTEGER, name TEXT, value TEXT, UNIQUE(eid, name) ON CONFLICT REPLACE, PRIMARY KEY(eid, name));
CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, path TEXT);
-- eid = experiment ID, fid = file ID
CREATE TABLE IF NOT EXISTS experiment_files (eid INTEGER, fid INTEGER, UNIQUE(eid, fid), PRIMARY KEY(eid, fid), FOREIGN KEY(eid) REFERENCES experiments(id), FOREIGN KEY(fid) REFERENCES files(id));
CREATE TABLE IF NOT EXISTS limits (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, gid INTEGER, name TEXT, value TEXT, UNIQUE(gid, name) ON CONFLICT REPLACE, FOREIGN KEY(gid) REFERENCES groups(id));
"""
insert_user = "INSERT INTO users (email, password, token) VALUES (?, ?, ?)"
insert_settings = "INSERT INTO user_settings (uid, name, value) VALUES (?, ?, ?)"
insert_experiment = "INSERT INTO experiments (uid, label, host) VALUES (?, ?, ?)"
insert_file = "INSERT INTO files (path) VALUES (?)"
insert_map = "INSERT INTO experiment_files (eid, fid) VALUES (?, ?)"


def create_app(test_config=None):
    __version__ = "0.0.1"
    conn = sqlite3.connect("db.sqlite")
    db = conn.cursor()
    db.executescript(schema)
    conn.commit()
    conn.close()
    app = Flask(__name__, instance_relative_config=True)
    CORS(app)
    app.config["CORS_HEADERS"] = "no-cors"
    prefix = "/api"

    # Routes

    @app.route(f"{prefix}/notifications/notify", methods=["POST", "OPTIONS"])
    def notify():
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        email = request.form.get("email")
        uid = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
        rows = db.execute(
            "SELECT value FROM user_settings WHERE uid = ? AND name = 'notification_type'",
            (uid,),
        ).fetchall()
        for row in rows:
            notification_type = row[0]
            to = (
                email
                if notification_type == "email"
                else db.execute(
                    "SELECT value FROM user_settings WHERE uid = ? AND name = 'slack_webhook'",
                    (uid,),
                ).fetchone()[0]
            )
            helpers.getattr("send_" + notification_type)(
                to, request.form.get("message")
            )
        conn.close()

    @app.route(f"{prefix}/users/new", methods=["POST", "OPTIONS"])
    @cross_origin()
    def create_user():
        if request.form.get("password") != request.form.get("confirm-password"):
            return jsonify({"error": "passwords don't match"})
        conn, db = helpers.create_conn()
        email = request.form.get("email")
        password = helpers.get_hashed_password(request.form.get("password"))
        token = helpers.get_token()
        db.execute(insert_user, (email, password, token))
        uid = db.lastrowid
        for key in request.form:
            if key.startswith("setting-"):
                db.execute(insert_settings, (uid, key[8:], request.form.get(key)))
        db.execute(insert_settings, (uid, "notification_type", "email"))
        # slack messages need to be configured
        # db.execute(insert_settings, (uid, "notification_type", "slack_message"))
        helpers.notify_admin(request, uid)
        conn.commit()
        conn.close()
        # return jsonify({"token": token})
        return jsonify(True)

    @app.route(f"{prefix}/users/settings/set", methods=["POST", "OPTIONS"])
    @cross_origin()
    def set_settings():
        conn, db = helpers.create_conn()
        if not helpers.is_authd(db, request.form):
            conn.close()
            return jsonify({"error": "must be logged in"})
        uid = db.execute(
            "SELECT id FROM users WHERE token = ?", (request.form.get("token"),)
        ).fetchone()[0]
        db.execute(
            "INSERT OR REPLACE INTO user_settings (uid, name, value) VALUES (?, ?, ?)",
            (uid, request.form.get("name"), request.form.get("value")),
        )
        conn.commit()
        conn.close()
        return jsonify(True)

    @app.route(f"{prefix}/users/list", methods=["GET", "OPTIONS"])
    def list_users():
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        rows = db.execute(
            "SELECT id, email, token, approved FROM users ORDER BY id DESC"
            if not request.args.get('awaiting_approval') == "1" else
            "SELECT id, email, token, approved FROM users WHERE approved = 0 ORDER BY id DESC"
        ).fetchall()
        users = []
        for row in rows:
            settings = db.execute(
                "SELECT name, value FROM user_settings WHERE uid = ?", (row[0],)
            ).fetchall()
            user = {
                "id": row[0],
                "email": row[1],
                "token": row[2],
                "approved": row[3],
                "settings": {},
            }
            for setting in settings:
                user["settings"][setting[0]] = setting[1]
            users.append(user)
        conn.close()
        return jsonify(users)

    @app.route(f"{prefix}/users/approve/<id>", methods=["GET", "OPTIONS"])
    def approve_user(id):
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        db.execute("UPDATE USERS SET approved = 1 WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return jsonify(True)

    @app.route(f"{prefix}/users/deny/<id>", methods=["GET", "OPTIONS"])
    def deny_user(id):
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        db.execute("UPDATE USERS SET approved = 0 WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return jsonify(True)

    @app.route(f"{prefix}/users/auth", methods=["POST", "OPTIONS"])
    @cross_origin()
    def auth_user():
        conn, db = helpers.create_conn()
        if helpers.login(db, request.form):
            token = helpers.get_token()
            db.execute(
                "UPDATE users SET token = ?, token_created = date('now') WHERE email = ?",
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

    @app.route(f"{prefix}/experiments", methods=["GET", "OPTIONS"])
    @cross_origin()
    def experiments():
        conn, db = helpers.create_conn()
        if not helpers.is_authd(db, request.args):
            conn.close()
            return jsonify({"error": "must be logged in"})
        uid = db.execute(
            "SELECT id FROM users WHERE token = ?", (request.args.get("token"),)
        ).fetchone()[0]
        res = []
        rows = db.execute(
            "SELECT id, label, created, status FROM experiments WHERE uid = ?", (uid,)
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
            # status_code = 0 if len(output_files) == 0 else 1
            eid = r[0]
            user_folder = os.path.join(os.environ["UPLOAD_FOLDER"], str(uid))
            params = db.execute(
                "SELECT name, value FROM experiment_settings WHERE eid = ?", (eid,)
            ).fetchall()
            app, experimentDescription, experimentName, params = helpers.extract_params(
                params, False
            )
            res.append(
                {
                    "id": r[0],
                    "label": r[1],
                    "created": r[2],
                    # "status_code": status_code,
                    "status": ["submitted", "queued", "completed"][r[3]],
                    "app": app,
                    "experimentDescription": experimentDescription,
                    "experimentName": experimentName,
                    "inputs": [item for sublist in input_files for item in sublist],
                    # list(map(lambda x: os.path.basename(x[0]), input_files))
                    "outputs": output_files,
                    "params": params,
                }
            )
        conn.close()
        return jsonify({"experiments": res})

    @app.route(f"{prefix}/experiments/queue", methods=["GET", "OPTIONS"])
    def experiment_queue():
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        experiments = []
        rows = db.execute(
            "SELECT id, uid, host FROM experiments WHERE status = ? ORDER BY created DESC",
            (STATUS_SUBMITTED,),
        ).fetchall()
        for r in rows:
            eid = r[0]
            uid = r[1]
            # or does this happen when backend actually starts job?
            # db.execute("UPDATE experiments SET queued = 1 WHERE id = ?", (eid,))
            params = db.execute(
                "SELECT name, value FROM experiment_settings WHERE eid = ?", (eid,)
            ).fetchall()
            app, experimentDescription, experimentName, params = helpers.extract_params(
                params, True
            )
            experiments.append(
                {
                    "id": r[0],
                    "user": uid,
                    "host": r[2],
                    # "inputs": db.execute(
                    #     "SELECT path FROM files WHERE id IN (SELECT fid FROM experiment_files WHERE eid = ?)",
                    #     (eid,),
                    # ).fetchall(),
                    "params": params,
                    "app": app,
                    "experimentDescription": experimentDescription,
                    "experimentName": experimentName,
                }
            )
        db.execute(
            "UPDATE experiments SET status = ? WHERE status = ?",
            (
                STATUS_QUEUED,
                STATUS_SUBMITTED,
            ),
        )
        conn.commit()
        conn.close()
        return jsonify(experiments)

    @app.route(f"{prefix}/experiments/<id>/files", methods=["GET", "OPTIONS"])
    # https://stackoverflow.com/a/24613980
    # https://stackoverflow.com/a/27337047
    def download_files(id):
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        uid = db.execute("SELECT uid FROM experiments WHERE id = ?", (id,)).fetchone()[
            0
        ]
        files = os.path.join(
            os.environ["UPLOAD_FOLDER"], str(uid), "submitted", str(id)
        )
        memory_file = helpers.zipdir(files)
        # @after_this_request
        # def remove_file(response):
        #     try:
        #         shutil.rmtree(files)
        #     except Exception as error:
        #         app.logger.error("Error removing or closing downloaded file handle", error)
        #     return response
        conn.close()
        return send_file(
            memory_file, attachment_filename="files.zip", as_attachment=True
        )

    @app.route(f"{prefix}/experiments/<id>/results", methods=["POST", "OPTIONS"])
    def upload_results(id):
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        uid = db.execute("SELECT uid FROM experiments WHERE id = ?", (id,)).fetchone()[
            0
        ]
        db.execute(
            "UPDATE experiments SET status = ? WHERE id = ?", (STATUS_COMPLETED, id)
        )
        conn.commit()
        conn.close()
        user_folder = os.path.join(os.environ["UPLOAD_FOLDER"], str(uid))
        completed_job_folder = os.path.join(user_folder, "completed", str(id))
        for file in request.files.values():
            secure_fn = secure_filename(file.filename)
            dest = os.path.join(completed_job_folder, secure_fn)
            file.save(dest)
        return jsonify(True)

    @app.route(f"{prefix}/experiments/<id>/file", methods=["GET", "OPTIONS"])
    @cross_origin()
    def static_file(id):
        conn, db = helpers.create_conn()
        if not helpers.is_authd(db, request.args):
            conn.close()
            return jsonify({"error": "must be logged in"})
        uid = db.execute(
            "SELECT id FROM users WHERE token = ?", (request.args.get("token"),)
        ).fetchone()[0]
        conn.close()
        path = request.args.get("path")
        return send_from_directory(
            os.path.join(os.environ["UPLOAD_FOLDER"], str(uid), "completed", id), path
        )

    # Uploaded files and the form, serialized as JSON, are placed in
    # a folder like `UPLOAD_FOLDER/uid/submitted/eid` where UPLOAD_FOLDER
    # is an environment variable, uid is a users ID, and eid is an experiment
    # ID. In addition to the "submitted" namespace (meant for the backend to queue)
    # there's an "editing" (ignored by backend) and "completed" namespace.
    # The location of an experiments files determines the status.
    # When the IPP backend runs job, output should be placed in `UPLOAD_FOLDER/uid/completed/eid`
    @app.route(f"{prefix}/experiments/new", methods=["POST", "OPTIONS"])
    @cross_origin()
    def new_experiment():
        conn, db = helpers.create_conn()
        if not helpers.is_authd(db, request.form):
            conn.close()
            return jsonify({"error": "must be logged in"})
        uid = db.execute(
            "SELECT id FROM users WHERE token = ?", (request.form.get("token"),)
        ).fetchone()[0]
        db.execute(
            insert_experiment,
            (uid, request.form.get("label"), request.form.get("host")),
        )
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
        del request_dict["host"]
        # request_dict["createdAt"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        # request_dict["ownerId"] = uid
        # request_dict["_id"] = eid
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
        # for file in request.files.values():
        for input_name, file in request.files.items():
            if file.filename != "":
                secure_fn = secure_filename(file.filename)
                dest = os.path.join(job_folder, secure_fn)
                file.save(dest)
                # possible to determine file size before writing to disk?
                if os.path.getsize(dest) > 1073741824:  # 1GB in bytes
                    shutil.rmtree(job_folder)
                    shutil.rmtree(completed_job_folder)
                    shutil.rmtree(edited_job_folder)
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
                request_dict[input_name] = dest
        for k, v in request_dict.items():
            db.execute(
                "INSERT INTO experiment_settings (name, value, eid) VALUES (?, ?, ?)",
                (k, v, eid),
            )
        conn.commit()
        conn.close()
        return jsonify(True)

    @app.route(f"{prefix}/experiments/<id>/delete", methods=["DELETE", "OPTIONS"])
    def delete_experiment_inputs(id):
        if request.remote_addr != "127.0.0.1":
            return abort(403)
        if request.method == "OPTIONS":
            return jsonify({"error": "the only request method is DELETE"})
        conn, db = helpers.create_conn()
        uid = db.execute("SELECT uid FROM experiments WHERE id = ?", (id,)).fetchone()[
            0
        ]
        conn.close()
        try:
            shutil.rmtree(
                os.path.join(os.environ["UPLOAD_FOLDER"], str(uid), "submitted", id)
            )
        except FileNotFoundError:
            return jsonify(False)
        return jsonify(True)

    @app.route(f"{prefix}/experiments/<id>/failed", methods=["POST", "OPTIONS"])
    def mark_failed(id):
        if request.remote_addr != "127.0.0.1":
            return abort(403)
        if request.method == "OPTIONS":
            return jsonify({"error": "the only request method is POST"})
        conn, db = helpers.create_conn()
        db.execute(
            "UPDATE experiments SET status = ? WHERE id = ?", (STATUS_FAILED, id)
        )
        conn.commit()
        conn.close()
        return jsonify(True)

    @app.route(f"{prefix}/files/delete", methods=["POST", "OPTIONS"])
    def delete_file():
        if request.remote_addr != "127.0.0.1":
            return abort(403)
        if request.method == "OPTIONS":
            return jsonify({"error": "the only request method is POST"})
        conn, db = helpers.create_conn()
        path = request.form.get("path")
        db.execute(
            "DELETE FROM experiment_files WHERE eid IN (SELECT id FROM files WHERE path = ?)",
            (path,),
        )
        db.execute("DELETE FROM files WHERE path = ?", (path,))
        shutil.rmtree(path)
        conn.commit()
        conn.close()
        return jsonify(True)

    @app.route(f"{prefix}/files/old", methods=["GET", "OPTIONS"])
    def files_older_than():
        if request.remote_addr != "127.0.0.1":
            return abort(403)
        if request.method == "OPTIONS":
            return jsonify({"error": "the only request method is GET"})
        conn, db = helpers.create_conn()
        days = request.args.get("days")
        if days is None:
            return jsonify({"error": "must specify days"})
        old_inputs = db.execute(
            "SELECT path FROM files WHERE id IN (SELECT fid FROM experiment_files WHERE eid IN (SELECT id FROM experiments WHERE created < DATE('now', '-%s days')))"
            % (days,)
        ).fetchall()
        old_outputs = []
        for f in glob.glob(
            os.path.join(os.environ["UPLOAD_FOLDER"], "*", "completed", "*")
        ):
            if os.path.getmtime(f) < time.time() - int(days) * 86400:
                old_outputs.append(f)
        conn.close()
        return jsonify(
            [item for sublist in old_inputs for item in sublist] + old_outputs
        )

    @app.route(f"{prefix}/users/groups", methods=["GET", "OPTIONS"])
    @cross_origin()
    def get_groups():
        conn, db = helpers.create_conn()
        token = request.args.get("token")
        uid = db.execute("SELECT id FROM users WHERE token = ?", (token,)).fetchone()[0]
        groups = db.execute(
            "SELECT name FROM groups WHERE id IN (SELECT gid FROM user_groups WHERE uid = ?)",
            (uid,),
        ).fetchall()
        conn.close()
        return jsonify({"groups": [g[0] for g in groups]})

    @app.route(f"{prefix}/admin/users", methods=["GET", "OPTIONS"])
    def user_admin_panel():
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        rows = db.execute(
            "SELECT id, email, token, approved FROM users ORDER BY id DESC"
        ).fetchall()
        users = []
        for r in rows:
            user_groups = db.execute(
                "SELECT gid FROM user_groups WHERE uid = ?", (r[0],)
            ).fetchall()
            users.append(
                {
                    "id": r[0],
                    "email": r[1],
                    "token": r[2],
                    "approved": r[3],
                    "groups": [g[0] for g in user_groups],
                }
            )

        rows = db.execute("SELECT id, name FROM groups ORDER BY id DESC").fetchall()
        groups = []
        for r in rows:
            groups.append({"id": r[0], "name": r[1]})
        conn.close()
        return render_template("users.html", users=users, groups=groups)

    @app.route(f"{prefix}/admin/groups", methods=["GET", "OPTIONS"])
    def group_admin_panel():
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        rows = db.execute("SELECT id, name FROM groups ORDER BY id DESC").fetchall()
        groups = []
        for r in rows:
            groups.append({"id": r[0], "name": r[1]})
        conn.close()
        return render_template("groups.html", groups=groups)

    @app.route(f"{prefix}/groups/create", methods=["POST", "OPTIONS"])
    def create_group():
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        db.execute("INSERT INTO groups (name) VALUES (?)", (request.form.get("group"),))
        conn.commit()
        conn.close()
        return redirect("/admin/groups")

    @app.route(f"{prefix}/groups/remove/<id>", methods=["POST", "OPTIONS"])
    def remove_group(id):
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        db.execute("DELETE FROM groups WHERE id = ?", (id,))
        db.execute("DELETE FROM user_groups WHERE gid = ?", (id,))
        conn.commit()
        conn.close()
        return redirect("/admin/groups")

    @app.route(f"{prefix}/groups/edit/<id>", methods=["POST", "OPTIONS"])
    def edit_group(id):
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        db.execute(
            "UPDATE groups SET name = ? WHERE id = ?",
            (
                request.form.get("group"),
                id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect("/admin/groups")

    @app.route(f"{prefix}/users/groups/map", methods=["POST", "OPTIONS"])
    def map_user_to_group():
        if request.remote_addr != "127.0.0.1":
            abort(403)
        conn, db = helpers.create_conn()
        uid = request.form.get("uid")
        for gid in request.form.getlist("gid"):
            db.execute("INSERT INTO user_groups (uid, gid) VALUES (?, ?)", (uid, gid))
        conn.commit()
        conn.close()
        return redirect("/admin/users")

    @app.route(f"{prefix}/version", methods=["GET", "OPTIONS"])
    def version():
        return jsonify({"version": __version__})

    @app.route(f"{prefix}/version/update", methods=["POST", "OPTIONS"])
    def update_version():
        if request.remote_addr != "127.0.0.1":
            abort(403)
        if 'GIT_DIR' in os.environ:
            to_checkout = request.form.get("checkout")
            if to_checkout is None:
                to_checkout = "build"
            # https://stackoverflow.com/a/16928558/2624391
            ret = subprocess.Popen(['nohup', os.environ['GIT_DIR'] + '/utils/pull-api.sh', to_checkout] + sys.argv,
                    stdout=open('/dev/null', 'w'),
                    stderr=open('logfile.log', 'a'),
                    preexec_fn=os.setpgrp
                    )
            print(ret)
            sys.exit(0)
        return jsonify({"error": "GIT_DIR not set"})

    @app.route(f"{prefix}/fe-version/update", methods=["POST", "OPTIONS"])
    def update_frontend_version():
        if request.remote_addr != "127.0.0.1":
            abort(403)
        if 'GIT_DIR' not in os.environ:
            return jsonify({"error": "GIT_DIR not set"})
        if 'FE_GIT_DIR' in os.environ:
            to_checkout = request.form.get("checkout")
            if to_checkout is None:
                to_checkout = "build"
            # https://stackoverflow.com/a/16928558/2624391
            ret = subprocess.Popen(['nohup', os.environ['GIT_DIR'] + '/utils/pull-fe.sh', os.environ['FE_GIT_DIR'], to_checkout] + sys.argv,
                    stdout=open('/dev/null', 'w'),
                    stderr=open('logfile.log', 'a'),
                    preexec_fn=os.setpgrp
                    )
            print(ret)
            sys.exit(0)
        return jsonify({"error": "FE_GIT_DIR not set"})

    if __name__ == "__main__":
        port = 8080
        host = "0.0.0.0"
        if "FLASK_RUN_PORT" in os.environ:
            port = int(os.environ["FLASK_RUN_PORT"])
        if "FLASK_RUN_HOST" in os.environ:
            host = os.environ["FLASK_RUN_HOST"]
        if sys.version_info < (3, 0):
            print("Python 3 required")
            sys.exit(1)
        print("Running with", sys.version_info)
        app.run(host=host, port=port)

    return app


create_app()
