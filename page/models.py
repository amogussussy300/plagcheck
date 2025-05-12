import datetime
from flask_login import UserMixin
from sqlalchemy.ext.mutable import MutableDict

from extensions import db
from sqlalchemy.dialects.sqlite import JSON


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    archives = db.relationship('Archive', back_populates='user', cascade='all, delete-orphan')


class Archive(db.Model):
    __tablename__ = 'archives'
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at        = db.Column(db.DateTime, default=datetime.datetime.now())
    task_id            = db.Column(db.String(64), nullable=False)
    status             = db.Column(db.String(20), nullable=False)
    comparison_results = db.Column(
        MutableDict.as_mutable(JSON),
        nullable=False
    )
    user = db.relationship('User', back_populates='archives')