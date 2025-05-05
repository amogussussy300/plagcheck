from flask import Flask, request, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
import hashlib
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Отключение отслеживания изменений, которое потребляет ресурсы


db = SQLAlchemy(app)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
class Admin(db.Model): #Админы с персональными ключами доступа
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    Personal_Key = db.Column(db.String(128), unique=True, nullable=False)
KEYS = ['cbb4af4d09d0236b638a0470f7ae6e1bd228cd5f',
        '8c1737e2bf580940d157092e999fcc4f0fce775f',
        '23b6be427e43d4a72bae880f13b7cd677a29b437']
def create_empty_user_once():
    with app.app_context():
        existing_user = User.query.first()
        if existing_user is None:
            new_user = User(email='', password='')
            db.session.add(new_user)
            db.session.commit()
        existing_user = Admin.query.first()
    existing_ad = Admin.query.first()
    if existing_ad is None:
        new_ad = Admin(email='', password='')
        db.session.add(new_ad)
        db.session.commit()
@app.route('/submit', methods=['POST'])
def submit(): # регистрация пользователя
    if request.method == 'POST':
        email = request.form.get('Email')
        pas = request.form.get('password')
        try:
            if pas[-7:] in KEYS:
                if Admin.query.filter_by(password=hashlib.sha1(pas.encode('utf-8')).hexdigest()).first():
                    return "Пользователь с таким паролем уже существует!"
                if Admin.query.filter_by(email=email):
                    return "Пользователь с такой почтой уже существует!"
                # хэширование паролей без персонального ключа админов
                new_admin = Admin( email=email, password=hashlib.sha1(pas[0:len(pas) - 7].encode('utf-8')).hexdigest(), Personal_Key=pas[-7:])
                db.session.add(new_admin)
                db.session.commit()
            elif pas[-6:] in KEYS:
                if Admin.query.filter_by(password=hashlib.sha1(pas.encode('utf-8')).hexdigest()).first():
                    return "Пользователь с таким паролем уже существует!"
                if Admin.query.filter_by(email=email):
                    return "Пользователь с такой почтой уже существует!"
                new_admin = Admin(email=email, password=hashlib.sha1(pas[0:len(pas) - 6].encode('utf-8')).hexdigest(), Personal_Key=pas[-6:])
                db.session.add(new_admin)
                db.session.commit()
            else: # регистрация обычного пользователя с полным хэшированием пароля
                if User.query.filter_by(password=hashlib.sha1(pas.encode('utf-8')).hexdigest()).first():
                    return "Пользователь с таким паролем уже существует!"
                if User.query.filter_by(email=email):
                    return "Пользователь с такой почтой уже существует!"
                new_user = User( email=email, password=hashlib.sha1(pas.encode('utf-8')).hexdigest())
                db.session.add(new_user)
                db.session.commit()
                return "Аккаунт Зарегестрирован, теперь войдите"
        except Exception as e:
            db.session.rollback()
            return f"Ошибка при регистрации: {e}"
@app.route('/check', methods=['POST'])
def check(): #проверка пароля и почты и вход в аккаунт
    if request.method == 'POST':
        email1 = request.form.get('Email')
        pas1 = request.form.get('password')
        if Admin.query.filter_by(email=email1, password=hashlib.sha1(pas1.encode('utf-8')).hexdigest()).first():
            return f"Вход Выполнен"
        #Твоя переадресация на сайт
        else:
            return f'Аккаунт не найден. Проверьте подлинность введеных данных'
@app.route('/', methods=['POST', 'GET'])
def home_page(): # главная страница
    return render_template('home_page.html')
@app.route('/Reg', methods=['POST', 'GET'])
def registration(): # страница регистрации
    return render_template('registration.html')
@app.route('/Log', methods=['POST', 'GET'])
def log_in(): # страница входа
    return render_template('log_in.html')

if __name__ == '__main__':
    # Запускаем приложение на порту 8000
    app.run(debug=True, port=8000)