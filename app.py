from flask import Flask, flash, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_migrate import Migrate

app = Flask(__name__)
app.jinja_env.auto_reload = True  # Setting up jinja2 as the template engine
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a secure secret key
app.static_folder = 'static'
app.template_folder = 'templates'

db = SQLAlchemy(app)

migrate = Migrate(app, db)

# Predefined list of categories
CATEGORIES = ['Admin', 'Fundi@work', 'Fundi@Home', 'Fundi@School', 'FundiGirl', 'Guest', 'Helper']

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    fingerprint_id = db.Column(db.Integer, unique=True, nullable=False)
    category = db.Column(db.String(20), nullable=False)
    attendance_records = db.relationship('Attendance', backref='user', lazy=True)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timeIn = db.Column(db.DateTime)
    timeOut = db.Column(db.DateTime)
    status = db.Column(db.String(10), nullable=False)

    def __init__(self, user_id, status):
        self.user_id = user_id
        self.status = status
        self.timeIn = None
        self.timeOut = None

        if self.status == 'registered':
            self.timeIn = datetime.now()

    def checkout(self):
        if self.status == 'registered' and self.timeIn is not None:
            self.timeOut = datetime.now()


@app.route('/')
def index():
    # if 'admin' not in session:
    #     return redirect(url_for('login'))
    # attendance_records = Attendance.query.all()
    return render_template('index.html')  # , attendance=attendance_records)

@app.route('/users')
def users():
    if 'admin' not in session:
        return redirect(url_for('login'))
    users = User.query.all()
    return render_template('users.html', users=users, categories=CATEGORIES)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'admin' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        fingerprint_id = request.form['fingerprint_id']
        category = request.form['category']
        new_user = User(name=name, fingerprint_id=fingerprint_id, category=category)
        db.session.add(new_user)
        db.session.commit()
        flash('User added successfully')
        return redirect(url_for('users'))
    return render_template('add_user.html', categories=CATEGORIES)

@app.route('/update_user/<int:user_id>', methods=['GET', 'POST'])
def update_user(user_id):
    if 'admin' not in session:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if request.method == 'POST':
        user.name = request.form['name']
        user.fingerprint_id = request.form['fingerprint_id']
        user.category = request.form['category']
        db.session.commit()
        flash('User updated successfully')
        return redirect(url_for('users'))
    return render_template('update_user.html', user=user, categories=CATEGORIES)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'admin' not in session:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully')
    return redirect(url_for('users'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Implement proper authentication
        if username == 'admin' and password == 'password':  # Replace with a real authentication method
            session['admin'] = True
            return redirect(url_for('users'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'admin' not in session:
        return redirect(url_for('login'))
    query = request.args.get('query')
    if query:
        users = User.query.filter(User.name.ilike(f'%{query}%')).all()
    else:
        users = User.query.all()
    return render_template('search.html', users=users, categories=CATEGORIES)

@app.route('/manage_users')
def manage_users():
    if 'admin' not in session:
        return redirect(url_for('login'))
    users = User.query.all()  # Query all users from the database
    return render_template('manage_users.html', users=users)

#function to add the record 
def add_attendance_record(fingerprint_id, status):
    user = User.query.filter_by(fingerprint_id=fingerprint_id).first()
    if user:
        new_record = Attendance(user_id=user.id, status=status)
        db.session.add(new_record)
        db.session.commit()

#route to display record
@app.route('/attendance_log')
def attendance_log():
    flash("Attendance log route hit")  # line
    if 'admin' not in session:
        return redirect(url_for('login'))
    attendance_records = Attendance.query.all()
    return render_template('attendance_log.html', attendance=attendance_records)


#testing receiving a finger print 
#@app.route('/test_attendance')
#def test_attendance():
    # Simulating adding an attendance record
 #   fingerprint_id = 89  # Replace with an actual fingerprint_id that exists
  #  status = 'registered'
   ##return "Attendance record added!"


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
