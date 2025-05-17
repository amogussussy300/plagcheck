import datetime
from flask_login import UserMixin
from sqlalchemy.ext.mutable import MutableDict

from extensions import db
from sqlalchemy.dialects.sqlite import JSON


class User(db.Model, UserMixin):
    """
    модель для каждого пользователя
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    archives = db.relationship('Archive', back_populates='user', cascade='all, delete-orphan')


class Archive(db.Model):
    """
    модель для каждого архива, привязана к пользователю
    """
    __tablename__ = 'archives'
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at         = db.Column(db.String(100), nullable=False)
    task_id            = db.Column(db.String(64), nullable=False)
    status             = db.Column(db.String(20), nullable=False)
    archive_name = db.Column(db.String, nullable=False)
    comparison_results = db.Column(
        MutableDict.as_mutable(JSON),
        nullable=False
    )
    user = db.relationship('User', back_populates='archives')