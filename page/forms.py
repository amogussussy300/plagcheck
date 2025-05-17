from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, ValidationError
from models import User

class LoginForm(FlaskForm):
    """
    HTML-форма для реализации логина
    """
    email = StringField('Почта', validators=[DataRequired(), Email()])
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

class RegistrationForm(FlaskForm):
    """
    HTML-форма для реализации регистрации
    """
    username = StringField('Логин', validators=[
        DataRequired(),
        Length(min=3, max=20)
    ])
    email = StringField('Почта', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    password = PasswordField('Пароль', validators=[
        DataRequired(),
        Length(min=6)
    ])
    submit = SubmitField('Зарегистрироваться')

    def validate_username(self, username):
        """
        функция для определения, занято ли уже введённое пользователем имя
        :param username: введённое имя пользователя
        """
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Данное имя пользователя уже занято')

    def validate_email(self, email):
        """
        функция для определения, занята ли уже введённая пользователем почта
        :param email: введённое имя пользователя
        """
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Данная почта уже занята')