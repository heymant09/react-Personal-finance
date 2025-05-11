from flask_sqlalchemy import SQLAlchemy
from datetime import date

db = SQLAlchemy()

# Association table for Transaction-Tag many-to-many relationship
transaction_tags = db.Table('transaction_tags',
    db.Column('transaction_id', db.Integer, db.ForeignKey('transaction.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    categories = db.relationship('Category', backref='user', lazy=True)
    tags = db.relationship('Tag', backref='user', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    description = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tags = db.relationship('Tag', secondary=transaction_tags, backref=db.backref('transactions', lazy='dynamic'))

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'income' or 'expense'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='category', lazy=True)
    __table_args__ = (db.UniqueConstraint('name', 'user_id', name='unique_category_user'),)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('name', 'user_id', name='unique_tag_user'),)