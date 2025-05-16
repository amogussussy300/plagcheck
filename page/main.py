import os
import uuid
import requests
from flask import Flask, render_template, url_for, flash, redirect, jsonify, request, current_app
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from requests import RequestException
import pathlib
import tempfile
from forms import RegistrationForm, LoginForm
from models import User, Archive
from extensions import db
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix


load_dotenv()
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = r'uploads/'
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
    archives = Archive.query.filter_by(user_id=current_user.id).order_by(Archive.created_at.desc()).all()
    archives_data = [{"status": archive.status, "task_id": archive.task_id, "results": archive.comparison_results, "archive_name": archive.archive_name, "created_at": archive.created_at} for archive in archives]
    print(archives_data)
    return render_template('dashboard.html', archives=archives_data, counter=len(archives_data))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/upload', methods=['POST'])
@login_required
def handle_upload():
    if 'archive' not in request.files:
        return jsonify(error='загруженного архива нет'), 400

    file = request.files['archive']
    if file.filename == '':
        return jsonify(error='пустое имя архива'), 400

    current_count = Archive.query.filter_by(user_id=current_user.id).count()
    if current_count >= 10:
        return jsonify({'error': f'Достигнут лимит по числу архивов для пользователя {current_user.id}'}), 400

    suffix = pathlib.Path(file.filename).suffix
    name = f'{str(uuid.uuid4())}'

    file_bytes = file.read()

    with tempfile.TemporaryDirectory() as upload_dir:

        save_path = os.path.join(upload_dir, f"{name}{suffix}")

        with open(save_path, "wb") as f:
            f.write(file_bytes)

        try:
            with open(save_path, "rb") as fp:
                resp = requests.post(
                    "http://localhost:8000/api/archives/",
                    files={"file": fp},
                    params={"process_type": "vector copydetect"},
                )

            resp.raise_for_status()
            task_id = resp.json()["task_id"]
        except RequestException as e:
            return jsonify(error=f'ошибка коммуникации с апи: {e}'), 502
        except KeyError:
            return jsonify(error='неверный response от апи'), 502

        while True:
            status_resp = requests.get(f"http://localhost:8000/api/status/{task_id}")
            status_resp.raise_for_status()
            status_data = status_resp.json()
            if status_data.get("status") == "completed":
                break

    with current_app.app_context():
        new_arch = Archive(
            user_id=current_user.id,
            task_id=status_data['task_id'],
            status=status_data['status'],
            comparison_results=status_data['results'],
            archive_name=status_data['archive_name'],
            created_at=status_data['created_at']
        )

        db.session.add(new_arch)
        db.session.commit()

    return jsonify({"status_data": status_data, "new_count": len(Archive.query.filter_by(user_id=current_user.id).order_by(Archive.created_at.desc()).all())})


@app.route('/delete/<task_id>', methods=['DELETE'])
def delete_archive(task_id):
    archive = Archive.query.filter_by(task_id=task_id).first()

    if not archive:
        return jsonify({'error': 'архив не найден'}), 404

    if archive.user_id != current_user.id:
        return jsonify({'error': 'неверный пользователь'}), 403

    try:
        db.session.delete(archive)
        db.session.commit()
        return jsonify({'success': True, 'new_count': len(Archive.query.filter_by(user_id=current_user.id).order_by(Archive.created_at.desc()).all())})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == "__main__":
    app.run(debug=True)