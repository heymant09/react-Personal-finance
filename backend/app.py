from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'

# Initialize SQLAlchemy
db = SQLAlchemy()

# Import models after db initialization
from models import User, Transaction, Category, Tag, transaction_tags

# Initialize extensions
db.init_app(app)  # Bind SQLAlchemy to app
CORS(app)
jwt = JWTManager(app)

# Helper to validate user
def get_current_user():
    user_id = get_jwt_identity()
    return User.query.get_or_404(user_id)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'message': 'Username and password required'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists'}), 400
    hashed_password = generate_password_hash(password)
    user = User(username=username, password=hashed_password)
    db.session.add(user)
    db.session.commit()
    # Add default categories and tags
    default_categories = [
        Category(name="Salary", type="income", user_id=user.id),
        Category(name="Other Income", type="income", user_id=user.id),
        Category(name="Rent", type="expense", user_id=user.id),
        Category(name="Groceries", type="expense", user_id=user.id),
        Category(name="Utilities", type="expense", user_id=user.id)
    ]
    default_tags = [
        Tag(name="Recurring", user_id=user.id),
        Tag(name="Urgent", user_id=user.id)
    ]
    db.session.add_all(default_categories + default_tags)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        access_token = create_access_token(identity=user.id)
        return jsonify({'token': access_token, 'username': user.username}), 200
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/api/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    user = get_current_user()
    category_id = request.args.get('category_id', type=int)
    tag_id = request.args.get('tag_id', type=int)
    query = Transaction.query.filter_by(user_id=user.id)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if tag_id:
        query = query.join(transaction_tags).filter(transaction_tags.c.tag_id == tag_id)
    transactions = query.order_by(Transaction.date.desc()).all()
    return jsonify([{
        'id': t.id,
        'date': t.date.isoformat(),
        'amount': t.amount,
        'category_id': t.category_id,
        'category_name': t.category.name,
        'category_type': t.category.type,
        'description': t.description,
        'tags': [{'id': tag.id, 'name': tag.name} for tag in t.tags]
    } for t in transactions])

@app.route('/api/transactions', methods=['POST'])
@jwt_required()
def add_transaction():
    user = get_current_user()
    data = request.get_json()
    # Handle category
    if data.get('category_id') == 'other':
        if not data.get('new_category') or not data.get('new_category_type'):
            return jsonify({'message': 'New category name and type required'}), 400
        category = Category(name=data['new_category'], type=data['new_category_type'], user_id=user.id)
        try:
            db.session.add(category)
            db.session.commit()
        except:
            db.session.rollback()
            return jsonify({'message': 'Category name already exists'}), 400
        category_id = category.id
    else:
        category_id = data.get('category_id')
        if not Category.query.get(category_id):
            return jsonify({'message': 'Invalid category'}), 400
    # Handle new tags
    new_tags = []
    if data.get('new_tag'):
        tag_names = [name.strip() for name in data['new_tag'].split(',') if name.strip()]
        for name in tag_names:
            tag = Tag.query.filter_by(name=name, user_id=user.id).first()
            if not tag:
                tag = Tag(name=name, user_id=user.id)
                try:
                    db.session.add(tag)
                    db.session.commit()
                except:
                    db.session.rollback()
                    continue
            new_tags.append(tag)
    # Create transaction
    date_obj = datetime.strptime(data['date'], '%Y-%m-%d').date() if data.get('date') else date.today()
    txn = Transaction(
        date=date_obj,
        amount=data['amount'],
        category_id=category_id,
        description=data.get('description'),
        user_id=user.id
    )
    selected_tag_ids = data.get('tag_ids', [])
    selected_tags = Tag.query.filter(Tag.id.in_(selected_tag_ids)).all() + new_tags
    txn.tags = selected_tags
    db.session.add(txn)
    db.session.commit()
    return jsonify({'message': 'Transaction added successfully'}), 201

@app.route('/api/transactions/<int:txn_id>', methods=['PUT'])
@jwt_required()
def edit_transaction(txn_id):
    user = get_current_user()
    txn = Transaction.query.get_or_404(txn_id)
    if txn.user_id != user.id:
        return jsonify({'message': 'Unauthorized'}), 403
    data = request.get_json()
    # Handle category
    if data.get('category_id') == 'other':
        if not data.get('new_category') or not data.get('new_category_type'):
            return jsonify({'message': 'New category name and type required'}), 400
        category = Category(name=data['new_category'], type=data['new_category_type'], user_id=user.id)
        try:
            db.session.add(category)
            db.session.commit()
        except:
            db.session.rollback()
            return jsonify({'message': 'Category name already exists'}), 400
        category_id = category.id
    else:
        category_id = data.get('category_id')
        if not Category.query.get(category_id):
            return jsonify({'message': 'Invalid category'}), 400
    # Handle new tags
    new_tags = []
    if data.get('new_tag'):
        tag_names = [name.strip() for name in data['new_tag'].split(',') if name.strip()]
        for name in tag_names:
            tag = Tag.query.filter_by(name=name, user_id=user.id).first()
            if not tag:
                tag = Tag(name=name, user_id=user.id)
                try:
                    db.session.add(tag)
                    db.session.commit()
                except:
                    db.session.rollback()
                    continue
            new_tags.append(tag)
    # Update transaction
    txn.date = datetime.strptime(data['date'], '%Y-%m-%d').date() if data.get('date') else date.today()
    txn.amount = data['amount']
    txn.category_id = category_id
    txn.description = data.get('description')
    selected_tag_ids = data.get('tag_ids', [])
    txn.tags = Tag.query.filter(Tag.id.in_(selected_tag_ids)).all() + new_tags
    db.session.commit()
    return jsonify({'message': 'Transaction updated successfully'})

@app.route('/api/transactions/<int:txn_id>', methods=['DELETE'])
@jwt_required()
def delete_transaction(txn_id):
    user = get_current_user()
    txn = Transaction.query.get_or_404(txn_id)
    if txn.user_id != user.id:
        return jsonify({'message': 'Unauthorized'}), 403
    db.session.delete(txn)
    db.session.commit()
    return jsonify({'message': 'Transaction deleted successfully'})

@app.route('/api/categories', methods=['GET'])
@jwt_required()
def get_categories():
    user = get_current_user()
    categories = Category.query.filter_by(user_id=user.id).order_by(Category.name).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'type': c.type
    } for c in categories])

@app.route('/api/categories', methods=['POST'])
@jwt_required()
def add_category():
    user = get_current_user()
    data = request.get_json()
    category = Category(name=data['name'], type=data['type'], user_id=user.id)
    try:
        db.session.add(category)
        db.session.commit()
        return jsonify({'message': 'Category added successfully', 'id': category.id}), 201
    except:
        db.session.rollback()
        return jsonify({'message': 'Category name already exists'}), 400

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_category(category_id):
    user = get_current_user()
    category = Category.query.get_or_404(category_id)
    if category.user_id != user.id:
        return jsonify({'message': 'Unauthorized'}), 403
    if category.transactions:
        return jsonify({'message': 'Cannot delete category with transactions'}), 400
    db.session.delete(category)
    db.session.commit()
    return jsonify({'message': 'Category deleted successfully'})

@app.route('/api/tags', methods=['GET'])
@jwt_required()
def get_tags():
    user = get_current_user()
    tags = Tag.query.filter_by(user_id=user.id).order_by(Tag.name).all()
    return jsonify([{
        'id': t.id,
        'name': t.name
    } for t in tags])

@app.route('/api/tags', methods=['POST'])
@jwt_required()
def add_tag():
    user = get_current_user()
    data = request.get_json()
    tag = Tag(name=data['name'], user_id=user.id)
    try:
        db.session.add(tag)
        db.session.commit()
        return jsonify({'message': 'Tag added successfully', 'id': tag.id}), 201
    except:
        db.session.rollback()
        return jsonify({'message': 'Tag name already exists'}), 400

@app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
@jwt_required()
def delete_tag(tag_id):
    user = get_current_user()
    tag = Tag.query.get_or_404(tag_id)
    if tag.user_id != user.id:
        return jsonify({'message': 'Unauthorized'}), 403
    if tag.transactions:
        return jsonify({'message': 'Cannot delete tag with transactions'}), 400
    db.session.delete(tag)
    db.session.commit()
    return jsonify({'message': 'Tag deleted successfully'})

@app.route('/api/dashboard', methods=['GET'])
@jwt_required()
def dashboard_data():
    user = get_current_user()
    category_id = request.args.get('category_id', type=int)
    tag_id = request.args.get('tag_id', type=int)
    query = Transaction.query.filter_by(user_id=user.id)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if tag_id:
        query = query.join(transaction_tags).filter(transaction_tags.c.tag_id == tag_id)
    transactions = query.order_by(Transaction.date.desc()).all()
    # Calculate metrics
    income = sum(t.amount for t in transactions if t.category.type == 'income')
    expense = sum(t.amount for t in transactions if t.category.type == 'expense')
    savings = income - expense
    # Chart data
    chart_data = {'dates': [], 'income': [], 'expense': []}
    if transactions:
        transaction_data = [
            {'date': t.date.strftime('%Y-%m-%d'), 'amount': t.amount, 'category': t.category.type}
            for t in transactions
        ]
        df = pd.DataFrame(transaction_data)
        if not df.empty:
            try:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                income_df = df[df['category'] == 'income'].resample('D').sum().reindex(df.index, fill_value=0)
                expense_df = df[df['category'] == 'expense'].resample('D').sum().reindex(df.index, fill_value=0)
                dates = [d.strftime('%Y-%m-%d') for d in df.index]
                chart_data = {
                    'dates': dates,
                    'income': income_df['amount'].tolist(),
                    'expense': expense_df['amount'].tolist()
                }
            except Exception as e:
                logger.error(f"Error processing chart data: {e}")
    # Top transactions
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    end_of_month = date(today.year, today.month + 1, 1) if today.month < 12 else date(today.year + 1, 1, 1)
    top_incomes = Transaction.query.join(Category).filter(
        Transaction.user_id == user.id,
        Category.type == 'income',
        Transaction.date.between(start_of_month, end_of_month)
    ).order_by(Transaction.amount.desc()).limit(5).all()
    top_expenses = Transaction.query.join(Category).filter(
        Transaction.user_id == user.id,
        Category.type == 'expense',
        Transaction.date.between(start_of_month, end_of_month)
    ).order_by(Transaction.amount.desc()).limit(5).all()
    return jsonify({
        'income': income,
        'expense': expense,
        'savings': savings,
        'chart_data': chart_data,
        'top_incomes': [{
            'date': t.date.isoformat(),
            'amount': t.amount,
            'description': t.description
        } for t in top_incomes],
        'top_expenses': [{
            'date': t.date.isoformat(),
            'amount': t.amount,
            'description': t.description
        } for t in top_expenses],
        'current_month': today.strftime('%B %Y')
    })

if __name__ == "__main__":
    with app.app_context():
        logger.debug("Creating database tables...")
        try:
            db.create_all()
            logger.debug("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database: {e}")
    app.run(debug=True, port=5000)
