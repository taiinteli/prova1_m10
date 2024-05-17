from flask import Flask, jsonify, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
import psycopg2
from flask_swagger_ui import get_swaggerui_blueprint
from psycopg2.extras import RealDictCursor
import os
from datetime import timedelta
from dotenv import load_dotenv
from uuid import uuid4

load_dotenv()

app = Flask(__name__)
print(os.getenv("JWT_SECRET_KEY"))
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
jwt = JWTManager(app)


def get_db_connection():
    conn = psycopg2.connect(
        host="db",
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PW"),
    )
    return conn


@app.route("/user", methods=["GET"])
def get_users():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users;")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(users)

@app.route("/task/<task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM tasks WHERE id = %s;", (task_id,))
    task = cur.fetchone()
    cur.close()
    conn.close()
    if task:
        return jsonify(task), 200
    else:
        return jsonify({"error": "Task not found"}), 404

@app.route("/user", methods=["POST"])
def create_user():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
        if cur.fetchone():
            return jsonify({"error": "User already exists"}), 409

        user_id = str(uuid4())
        cur.execute(
            "INSERT INTO users (id, username, user_pw) VALUES (%s, %s, %s)",
            (user_id, username, password),
        )
        conn.commit()
        return jsonify({"userid": user_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route("/user/login", methods=["POST"])
def login():
    username = request.json.get("username", None)
    password = request.json.get("password", None)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, user_pw FROM users WHERE username = %s;", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and user["user_pw"] == password:
        expires = timedelta(days=1)
        access_token = create_access_token(identity=user["id"], expires_delta=expires)
        return jsonify(access_token=access_token), 200

    return jsonify({"msg": "Bad username or password"}), 401



@app.route("/task", methods=["GET"])
@jwt_required()
def get_tasks():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM tasks;")
    tasks = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(tasks)




@app.route("/task", methods=["POST"])
@jwt_required()
def create_task():
    data = request.json
    title = data.get("title")
    description = data.get("description")

    if not title:
        return jsonify({"error": "Title is required"}), 400

    id = get_jwt_identity()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id FROM users WHERE id = %s;", (id,))
    user = cur.fetchone()
    if not user:
        cur.close()
        conn.close()
        return jsonify({"error": "User not found"}), 404

    user_id = user["id"]

    try:
        task_id = str(uuid4())
        cur.execute(
            "INSERT INTO tasks (id, title, description, userid) VALUES (%s, %s, %s, %s)",
            (task_id, title, description, user_id),
        )
        conn.commit()
        return jsonify({"message": "Task created successfully", "taskId": task_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route("/user/<user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user:
        return jsonify(user), 200
    else:
        return jsonify({"error": "User not found"}), 404


@app.route("/user/<user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):
    data = request.json
    username = data.get("username")
    password = data.get("password")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET username = %s, user_pw = %s WHERE id = %s;",
        (username, password, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "User updated successfully"}), 200


@app.route("/user/<user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "User deleted successfully"}), 200


@app.route("/task/<task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    data = request.json
    title = data.get("title")
    description = data.get("description")

    if not title:
        return jsonify({"error": "Title is required"}), 400

    id = get_jwt_identity()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT userid FROM tasks WHERE id = %s;", (task_id,))
    task = cur.fetchone()
    if not task:
        cur.close()
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    cur.execute("SELECT id FROM users WHERE id = %s;", (id,))
    user = cur.fetchone()
    if not user or str(user["id"]) != str(task["userid"]):
        cur.close()
        conn.close()
        return jsonify({"error": "Unauthorized"}), 403

    cur.execute(
        "UPDATE tasks SET title = %s, description = %s WHERE id = %s;",
        (title, description, task_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Task updated successfully"}), 200


@app.route("/task/<task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    id = get_jwt_identity()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT userid FROM tasks WHERE id = %s;", (task_id,))
    task = cur.fetchone()
    if not task:
        cur.close()
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    cur.execute("SELECT id FROM users WHERE id = %s;", (id,))
    user = cur.fetchone()
    if not user or str(user["id"]) != str(task["userid"]):
        cur.close()
        conn.close()
        return jsonify({"error": "Unauthorized"}), 403

    cur.execute("DELETE FROM tasks WHERE id = %s;", (task_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Task deleted successfully"}), 200

SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.yaml'  
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Task Management API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


if __name__ == "__main__":
    app.run(debug=True)