import io
import json
import os

import requests
from flask import Flask, render_template, url_for, flash, redirect, jsonify, request
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from requests import RequestException
from werkzeug.utils import secure_filename
import pathlib
import tempfile
from forms import RegistrationForm, LoginForm
from models import User
from extensions import db
from services import send_archive, get_status


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

bcr = Bcrypt(app)
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()


@app.route("/")
def index():
    return render_template('base.html', current_user=current_user)


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_pw = bcr.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash('Аккаунт зарегистрирован, войдите.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and bcr.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect(url_for('dashboard'))
        else:
            flash('Неверная почта или пароль', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/upload', methods=['POST'])
@login_required
def handle_upload():
    """потом заполню"""
    try:
        if 'archive' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['archive']
        suffix = pathlib.Path(file.filename).suffix
        name = file.filename[:10]
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        try:
            file_bytes = file.read()

            with tempfile.TemporaryDirectory() as tdir:
                save_path = os.path.join(tdir, fr"{name}.{suffix}")

                with open(save_path, "wb") as f:
                    f.write(file_bytes)

                    task_id = json.loads(requests.post("http://localhost:8000/api/archives/",
                                             files={"file": open(save_path, "rb")},
                                             params={"process_type": "vector copydetect"}).content)["task_id"]

                    status_response = requests.get(f"http://localhost:8000/api/status/{task_id}")
                    while status_response.json()["status"] != "completed":
                        print(status_response.json())

            return status_response.json()

        except RequestException as e:
            return jsonify({'error': f'ошибка коммуникации с апи: {str(e)}'}), 502
        except KeyError:
            return jsonify({'error': 'неверный ответ от апи'}), 502

    except Exception as e:
        return jsonify({'error': f'внутренняя ошибка сервера: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == "__main__":
    app.run(debug=True)