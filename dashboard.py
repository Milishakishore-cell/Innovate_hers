from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import jwt
import datetime
from functools import wraps
import ollama
from datetime import datetime, timedelta

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smartcampus.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Initialize Ollama
ollama_client = ollama.Client(host='http://localhost:11434')

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True)
    student_id = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(70), unique=True)
    password = db.Column(db.String(80))
    role = db.Column(db.String(20), default='student')
    profile = db.Column(db.JSON, default={})

class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(db.String(20))  # breakfast, lunch, dinner, snack
    date = db.Column(db.DateTime, nullable=False)
    nutritional_info = db.Column(db.JSON)
    ingredients = db.Column(db.JSON)  # List as JSON
    ratings = db.Column(db.JSON)      # List of dicts as JSON
    predicted_demand = db.Column(db.Integer)
    actual_consumption = db.Column(db.Integer)

class LostItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20))  # electronics, books, clothing, etc.
    location = db.Column(db.String(100), nullable=False)
    date_lost = db.Column(db.DateTime, nullable=False)
    date_found = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='lost')  # lost, found, claimed
    reported_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    claimed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    image_url = db.Column(db.String(200))

class Scholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    provider = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text, nullable=False)
    eligibility = db.Column(db.JSON, nullable=False)  # Dictionary as JSON
    application_link = db.Column(db.String(200))
    tags = db.Column(db.JSON)  # List as JSON

class UserScholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarship.id'), nullable=False)
    status = db.Column(db.String(20), default='interested')  # interested, applied, awarded, rejected
    application_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)

# Create database tables
with app.app_context():
    db.create_all()

# Auth Decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(public_id=data['public_id']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# Routes

# Auth Routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Check if user already exists
    existing_user = User.query.filter(
        (User.student_id == data['student_id']) | 
        (User.email == data['email'])
    ).first()
    
    if existing_user:
        return jsonify({'message': 'User already exists!'}), 400
    
    hashed_password = generate_password_hash(data['password'], method='sha256')
    
    new_user = User(
        public_id=str(uuid.uuid4()),
        student_id=data['student_id'],
        name=data['name'],
        email=data['email'],
        password=hashed_password,
        role=data.get('role', 'student')
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'Registered successfully!'}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    auth = request.get_json()
    
    if not auth or not auth.get('student_id') or not auth.get('password'):
        return jsonify({'message': 'Could not verify!'}), 401
    
    user = User.query.filter_by(student_id=auth['student_id']).first()
    
    if not user:
        return jsonify({'message': 'User not found!'}), 404
    
    if check_password_hash(user.password, auth['password']):
        token = jwt.encode({
            'public_id': user.public_id,
            'exp': datetime.utcnow() + timedelta(minutes=30)
        }, app.config['SECRET_KEY'])
        
        return jsonify({
            'token': token,
            'user': {
                'public_id': user.public_id,
                'student_id': user.student_id,
                'name': user.name,
                'email': user.email,
                'role': user.role
            }
        })
    
    return jsonify({'message': 'Wrong password!'}), 401

# User Routes
@app.route('/api/users/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    return jsonify({
        'public_id': current_user.public_id,
        'student_id': current_user.student_id,
        'name': current_user.name,
        'email': current_user.email,
        'role': current_user.role,
        'profile': current_user.profile
    })

@app.route('/api/users/me', methods=['PATCH'])
@token_required
def update_user_profile(current_user):
    data = request.get_json()
    
    if 'password' in data:
        data['password'] = generate_password_hash(data['password'], method='sha256')
    
    for key, value in data.items():
        setattr(current_user, key, value)
    
    db.session.commit()
    
    return jsonify({'message': 'Profile updated!'})

# Canteen Routes
@app.route('/api/meals', methods=['GET'])
@token_required
def get_meals(current_user):
    date_str = request.args.get('date')
    meal_type = request.args.get('type')
    
    query = Meal.query
    
    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            start_date = datetime(date.year, date.month, date.day)
            end_date = start_date + timedelta(days=1)
            query = query.filter(Meal.date >= start_date, Meal.date < end_date)
        except ValueError:
            return jsonify({'message': 'Invalid date format! Use YYYY-MM-DD'}), 400
    
    if meal_type:
        query = query.filter_by(type=meal_type)
    
    meals = query.order_by(Meal.date.asc()).all()
    
    output = []
    for meal in meals:
        meal_data = {
            'id': meal.id,
            'name': meal.name,
            'description': meal.description,
            'type': meal.type,
            'date': meal.date.isoformat(),
            'nutritional_info': meal.nutritional_info,
            'ingredients': meal.ingredients,
            'ratings': meal.ratings,
            'predicted_demand': meal.predicted_demand,
            'actual_consumption': meal.actual_consumption
        }
        output.append(meal_data)
    
    return jsonify({'meals': output})

@app.route('/api/meals/today', methods=['GET'])
@token_required
def get_todays_meals(current_user):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    meals = Meal.query.filter(
        Meal.date >= today,
        Meal.date < tomorrow
    ).order_by(Meal.type.asc()).all()
    
    output = []
    for meal in meals:
        meal_data = {
            'id': meal.id,
            'name': meal.name,
            'description': meal.description,
            'type': meal.type,
            'date': meal.date.isoformat(),
            'nutritional_info': meal.nutritional_info,
            'ingredients': meal.ingredients
        }
        output.append(meal_data)
    
    return jsonify({'meals': output})

@app.route('/api/meals/<int:meal_id>/rate', methods=['POST'])
@token_required
def rate_meal(current_user, meal_id):
    data = request.get_json()
    meal = Meal.query.get(meal_id)
    
    if not meal:
        return jsonify({'message': 'Meal not found!'}), 404
    
    ratings = meal.ratings or []
    
    # Remove existing rating from this user if exists
    ratings = [r for r in ratings if r.get('user_id') != current_user.id]
    
    # Add new rating
    ratings.append({
        'user_id': current_user.id,
        'rating': data['rating'],
        'feedback': data.get('feedback')
    })
    
    meal.ratings = ratings
    db.session.commit()
    
    return jsonify({'message': 'Rating submitted!'})

@app.route('/api/ai/chat', methods=['POST'])
@token_required
def chat_with_ai(current_user):
    data = request.get_json()
    message = data.get('message')
    
    if not message:
        return jsonify({'message': 'Message is required!'}), 400
    
    try:
        response = ollama_client.generate(
            model='llama2',
            prompt=f"You are a helpful campus nutrition assistant. A student asks: {message}",
            stream=False
        )
        return jsonify({'response': response['response']})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# Lost & Found Routes
@app.route('/api/lost-items', methods=['GET'])
@token_required
def get_lost_items(current_user):
    status = request.args.get('status')
    category = request.args.get('category')
    location = request.args.get('location')
    
    query = LostItem.query
    
    if status:
        query = query.filter_by(status=status)
    if category:
        query = query.filter_by(category=category)
    if location:
        query = query.filter_by(location=location)
    
    items = query.order_by(LostItem.date_lost.desc()).all()
    
    output = []
    for item in items:
        reported_by = User.query.get(item.reported_by)
        claimed_by = User.query.get(item.claimed_by) if item.claimed_by else None
        
        item_data = {
            'id': item.id,
            'item_id': item.item_id,
            'name': item.name,
            'description': item.description,
            'category': item.category,
            'location': item.location,
            'date_lost': item.date_lost.isoformat(),
            'date_found': item.date_found.isoformat() if item.date_found else None,
            'status': item.status,
            'reported_by': {
                'id': reported_by.id,
                'name': reported_by.name,
                'student_id': reported_by.student_id
            } if reported_by else None,
            'claimed_by': {
                'id': claimed_by.id,
                'name': claimed_by.name,
                'student_id': claimed_by.student_id
            } if claimed_by else None,
            'image_url': item.image_url
        }
        output.append(item_data)
    
    return jsonify({'items': output})

@app.route('/api/lost-items', methods=['POST'])
@token_required
def report_lost_item(current_user):
    data = request.get_json()
    
    new_item = LostItem(
        item_id=str(uuid.uuid4()),
        name=data['name'],
        description=data['description'],
        category=data['category'],
        location=data['location'],
        date_lost=datetime.strptime(data['date_lost'], '%Y-%m-%d'),
        status=data.get('status', 'lost'),
        reported_by=current_user.id,
        image_url=data.get('image_url')
    )
    
    db.session.add(new_item)
    db.session.commit()
    
    return jsonify({'message': 'Item reported!'}), 201

@app.route('/api/lost-items/<int:item_id>', methods=['PATCH'])
@token_required
def update_lost_item(current_user, item_id):
    item = LostItem.query.get(item_id)
    
    if not item:
        return jsonify({'message': 'Item not found!'}), 404
    
    # For non-admins, only allow status updates
    if current_user.role in ['student', 'staff']:
        if len(request.json) != 1 or 'status' not in request.json:
            return jsonify({'message': 'You can only update the status!'}), 403
    
    data = request.get_json()
    
    # If marking as claimed, set claimed_by and date_found
    if data.get('status') == 'claimed':
        data['claimed_by'] = current_user.id
        data['date_found'] = datetime.utcnow()
    
    for key, value in data.items():
        setattr(item, key, value)
    
    db.session.commit()
    
    return jsonify({'message': 'Item updated!'})

# Scholarship Routes
@app.route('/api/scholarships', methods=['GET'])
@token_required
def get_scholarships(current_user):
    search = request.args.get('search')
    deadline_after = request.args.get('deadline_after')
    amount_min = request.args.get('amount_min')
    
    query = Scholarship.query
    
    if search:
        query = query.filter(
            (Scholarship.name.ilike(f'%{search}%')) |
            (Scholarship.provider.ilike(f'%{search}%')) |
            (Scholarship.description.ilike(f'%{search}%'))
        )
    
    if deadline_after:
        try:
            deadline_date = datetime.strptime(deadline_after, '%Y-%m-%d')
            query = query.filter(Scholarship.deadline >= deadline_date)
        except ValueError:
            return jsonify({'message': 'Invalid date format! Use YYYY-MM-DD'}), 400
    
    if amount_min:
        try:
            query = query.filter(Scholarship.amount >= float(amount_min))
        except ValueError:
            return jsonify({'message': 'Invalid amount!'}), 400
    
    scholarships = query.order_by(Scholarship.deadline.asc()).all()
    
    output = []
    for scholarship in scholarships:
        scholarship_data = {
            'id': scholarship.id,
            'name': scholarship.name,
            'provider': scholarship.provider,
            'amount': scholarship.amount,
            'deadline': scholarship.deadline.isoformat(),
            'description': scholarship.description,
            'eligibility': scholarship.eligibility,
            'application_link': scholarship.application_link,
            'tags': scholarship.tags
        }
        output.append(scholarship_data)
    
    return jsonify({'scholarships': output})

@app.route('/api/scholarships/recommended', methods=['GET'])
@token_required
def get_recommended_scholarships(current_user):
    # Get current date
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Start with all active scholarships
    query = Scholarship.query.filter(Scholarship.deadline >= today)
    
    # Filter based on user profile
    if current_user.profile:
        # Academic level
        if current_user.profile.get('academic_level'):
            query = query.filter(
                (Scholarship.eligibility['academic_level'].astext == 'all') |
                (Scholarship.eligibility['academic_level'].astext == current_user.profile['academic_level'])
            )
        
        # Field of study
        if current_user.profile.get('field_of_study'):
            query = query.filter(
                (Scholarship.eligibility['field_of_study'].astext == 'all') |
                (Scholarship.eligibility['field_of_study'].astext == current_user.profile['field_of_study'])
            )
        
        # GPA
        if current_user.profile.get('gpa'):
            query = query.filter(
                (Scholarship.eligibility['min_gpa'].is_(None)) |
                (Scholarship.eligibility['min_gpa'].astext.cast(db.Float) <= current_user.profile['gpa'])
            )
        
        # Financial need
        if current_user.profile.get('financial_need') == 'high':
            query = query.filter(
                Scholarship.eligibility['financial_need'].astext == 'true'
            )
        
        # Demographics
        if current_user.profile.get('demographics'):
            query = query.filter(
                Scholarship.eligibility['demographics'].astext.in_(current_user.profile['demographics'])
            )
    
    scholarships = query.order_by(Scholarship.deadline.asc()).all()
    
    # Get user's scholarship statuses
    user_scholarships = UserScholarship.query.filter_by(user_id=current_user.id).all()
    
    output = []
    for scholarship in scholarships:
        # Find user's status for this scholarship
        user_scholarship = next(
            (us for us in user_scholarships if us.scholarship_id == scholarship.id),
            None
        )
        
        scholarship_data = {
            'id': scholarship.id,
            'name': scholarship.name,
            'provider': scholarship.provider,
            'amount': scholarship.amount,
            'deadline': scholarship.deadline.isoformat(),
            'description': scholarship.description,
            'eligibility': scholarship.eligibility,
            'application_link': scholarship.application_link,
            'tags': scholarship.tags,
            'user_status': user_scholarship.status if user_scholarship else None
        }
        output.append(scholarship_data)
    
    return jsonify({'scholarships': output})

@app.route('/api/scholarships/<int:scholarship_id>/status', methods=['POST'])
@token_required
def update_scholarship_status(current_user, scholarship_id):
    data = request.get_json()
    status = data.get('status')
    
    if not status:
        return jsonify({'message': 'Status is required!'}), 400
    
    # Check if scholarship exists
    scholarship = Scholarship.query.get(scholarship_id)
    if not scholarship:
        return jsonify({'message': 'Scholarship not found!'}), 404
    
    # Find or create user scholarship record
    user_scholarship = UserScholarship.query.filter_by(
        user_id=current_user.id,
        scholarship_id=scholarship_id
    ).first()
    
    if user_scholarship:
        user_scholarship.status = status
        if status == 'applied':
            user_scholarship.application_date = datetime.utcnow()
    else:
        user_scholarship = UserScholarship(
            user_id=current_user.id,
            scholarship_id=scholarship_id,
            status=status,
            application_date=datetime.utcnow() if status == 'applied' else None
        )
        db.session.add(user_scholarship)
    
    db.session.commit()
    
    return jsonify({'message': 'Status updated!'})

# Run the app
if __name__ == '__main__':
    app.run(debug=True)