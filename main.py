from flask import Flask, render_template, redirect, url_for, flash, abort, request, send_from_directory
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import RegistrationForm, LoginForm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_bootstrap import Bootstrap5
from flask_mail import Mail, Message
import os
from werkzeug.utils import secure_filename
import secrets

GMAIL_ADDRESS='houselistings6@gmail.com'
GMAIL_PASSWORD='eyrtekesvicoaueo'

app = Flask(__name__)
app.config['SECRET_KEY'] ="your-secret-key"

# #This code will help us to connect to database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = GMAIL_ADDRESS
app.config['MAIL_PASSWORD'] = GMAIL_PASSWORD
app.config['MAIL_SENDER'] = GMAIL_ADDRESS
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg','webp'}
db = SQLAlchemy(app)
mail = Mail(app)
Bootstrap5(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from functools import wraps

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_admin != True:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)
    is_admin = db.Column(db.Boolean, unique=False, default=False)

    contacts = db.relationship('Contact', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.id}>'


class House(db.Model):
    __tablename__ = "houses"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    price = db.Column(db.Integer)
    location = db.Column(db.String(100))
    description = db.Column(db.Text)
    image_1 = db.Column(db.String(150), nullable=False, default='image1.jpg')
    image_2 = db.Column(db.String(150), nullable=False, default='image2.jpg')
    image_3 = db.Column(db.String(150), nullable=False, default='image3.jpg')
    contacts = db.relationship('Contact', backref='house', lazy=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<House {self.id}>'
    
class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    house_id = db.Column(db.Integer, db.ForeignKey('houses.id'), nullable=False)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Contact {self.id}>'



@app.route('/')
def home():
    houses = House.query.order_by(House.created_at.desc()).all()
    return render_template('home.html', houses=houses)


@app.route('/search', methods=['GET', 'POST'])
def search():
    location = request.args.get('location')
    sort_order = request.args.get('sort_order')
    

    query = House.query
    
    # This is where we sort our housings 
    if sort_order == 'asc':
        query = query.order_by(House.price.asc())
    elif sort_order == 'desc':
        query = query.order_by(House.price.desc())
    
    if location:
        query = query.filter(House.location.ilike(f"%{location}%"))
        
    if location is None:
        location = ""

    houses = query.all()
    
    return render_template('search-results.html', houses=houses, location=location)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/house/<int:house_id>', methods=['GET'])
def house_details(house_id):
    house = House.query.get(house_id)
    house_contacted = False

    if current_user.is_authenticated:
        contact = Contact.query.filter_by(user_id=current_user.id, house_id=house_id).first()
        if contact:
            house_contacted = True

    return render_template('house_details.html', house=house, house_contacted=house_contacted)

@app.route('/contact', methods=['POST'])
@login_required
def contact():
    if not current_user.is_authenticated:
        flash('Please log in to contact the admin.', 'error')
        return redirect(url_for('login'))

    house_id = request.form.get('house_id')
    message = request.form.get('message')
    
    print(house_id,message)

    house = House.query.get(house_id)
    if not house:
        flash('House not found.', 'error')
        return redirect(url_for('home'))

    contact = Contact.query.filter_by(user_id=current_user.id, house_id=house_id).first()
    if contact:
        flash('You have already contacted the admin for this house.', 'info')
    else:
        new_contact = Contact(user_id=current_user.id, house_id=house_id, message=message)
        db.session.add(new_contact)
        db.session.commit()
        db.session.refresh(new_contact)
        
        subject = 'New Inquiry'
        template = render_template('admin_email.html', house=house, contact=new_contact, user=current_user)
        
        send_email( subject, template)

        flash('Your message has been sent to the admin.', 'success')

    return redirect(url_for('house_details', house_id=house_id))

@app.route('/my_contacts')
@login_required
def my_contacts():
    contacts = Contact.query.filter_by(user_id=current_user.id).order_by(Contact.created_at.desc()).all()
    return render_template('my_contacts.html', contacts=contacts)

def send_email(subject, template):
    msg = Message(subject, recipients=[app.config['MAIL_SENDER']], sender=app.config['MAIL_SENDER'])
    msg.html = template
    try:
        mail.send(msg)
    except Exception as e:
        print('mail send error :',e)


@app.route('/register', methods=['GET', 'POST'])
def register():
    register_form = RegistrationForm()
    if register_form.validate_on_submit():
        if User.query.filter_by(email=register_form.email.data).first():
            flash("You've already sign up with that email, log in instead.", category='danger')
            return redirect(url_for('login'))
        else:
            hash_password = generate_password_hash(register_form.password.data, method='pbkdf2:sha256', salt_length=16)
            new_user = User(name=register_form.name.data, email=register_form.email.data, password=hash_password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash("Registration successful.", category='success')
            return redirect(url_for('home'))
    return render_template("auth-form.html", form=register_form,title="Register")


@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if user is not None:
            if check_password_hash(user.password, login_form.password.data):
                login_user(user)
                if user.is_admin:
                    return redirect(url_for('admin'))
                return redirect(url_for('home'))
            else:
                flash('Password incorrect,try again.', category='danger')
        else:
            flash('That email does not exist,please try again.', category='danger')
    return render_template("auth-form.html", form=login_form,title="Login")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout successful.", category='success')
    return redirect(url_for('home'))


@app.route('/admin')
@admin_only
def admin():
    houses = House.query.all()
    return render_template('admin.html', houses=houses)


@app.route('/add_house', methods=['GET', 'POST'])
@admin_only
def add_house():
    if request.method == 'POST':
        title = request.form.get('title')
        price = request.form.get('price')
        location = request.form.get('location')
        description = request.form.get('description')
        picture_one = request.files['image_1']
        picture_two = request.files['image_2']
        picture_three = request.files['image_3']
        if picture_one and allowed_file(picture_one.filename):
            _, f_ext = os.path.splitext(picture_one.filename)
            filename_one = secrets.token_hex(8) + f_ext
            picture_one.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_one))
        else:
            filename_one = None
            
        if picture_two and allowed_file(picture_two.filename):
            _, f_ext = os.path.splitext(picture_two.filename)
            filename_two = secrets.token_hex(8) + f_ext
            picture_two.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_two))
        else:
            filename_two = None
            
        if picture_three and allowed_file(picture_three.filename):
            _, f_ext = os.path.splitext(picture_three.filename)
            filename_three = secrets.token_hex(8) + f_ext
            picture_three.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_three))
        else:
            filename_three = None
        
        house = House(title=title, price=price, 
                      description=description, 
                      location=location)
        if filename_one:
            house.image_1 = filename_one
        if filename_two:
            house.image_2 = filename_two
        if filename_three:
            house.image_3 = filename_three
        db.session.add(house)
        db.session.commit()
        flash('House added successfully.')
        return redirect(url_for('admin'))
    return render_template('add_house.html')

@app.route('/remove_house/<int:house_id>', methods=['POST'])
@admin_only
def remove_house(house_id):
    house = House.query.get_or_404(house_id)
    Contact.query.filter_by(house_id=house.id).delete()
    if house.image_1:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], house.image_1))
    if house.image_2:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], house.image_2))
    if house.image_3:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], house.image_3))
    db.session.delete(house)
    db.session.commit()
    flash('House removed successfully.')
    return redirect(url_for('admin'))


#We can uncomment this code to reset the database
if __name__ == "__main__":
    # with app.app_context():
    #     db.drop_all()
    #     db.create_all()
    #     if not User.query.filter_by(email='admin@email.com').first():
    #         hassed_password = generate_password_hash('12345', method='pbkdf2:sha256', salt_length=16)
    #         user = User(name='admin',
    #                     email='admin@email.com',
    #                     password=hassed_password,
    #                     is_admin=True)
    #         db.session.add(user)
    #         db.session.commit()
    #         print('admin user created')
    app.run(debug=True)