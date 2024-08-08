import atexit
import http
import os
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz
from flask_migrate import Migrate
import requests
from flask import request, jsonify, render_template, session, redirect, url_for
from sqlalchemy import extract
from sqlalchemy.sql import func
import logging


app = Flask(__name__)
app.jinja_env.auto_reload = True  # Setting up jinja2 as the template engine
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL','postgresql://fundidatabase_user:pU39YDMuKAQonkBrWN7BRKei8bnin5ay@dpg-cqn373tds78s73977me0-a.frankfurt-postgres.render.com/fundidatabase')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY','your_secret_key')  
app.static_folder = 'static'
app.template_folder = 'templates'
db = SQLAlchemy(app)
migrate = Migrate(app, db)
#set up of logging
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

#list of categories
CATEGORIES = ['Admin', 'Fundi@work', 'Fundi@Home', 'Fundi@School', 'FundiGirl', 'Guest', 'Helper']
#East African Timezone
EAT = pytz.timezone('Africa/Kampala')
ESP_URL='http://192.168.43.196:80' # the esp ip is not yet set just holding the place
#ESP_URL_add='http://192.168.0.10:80/'
#ESP_URL=' https://4e4c-41-75-182-54.ngrok-free.app -> http:'




def now_in_eat():
    return datetime.now(EAT)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    fingerprint_id = db.Column(db.Integer, unique=True, nullable=False)
    category = db.Column(db.String(20), nullable=False)
    attendance_records = db.relationship('Attendance', backref='user', lazy=True)

    #for the automatic search
    def to_dict(self):
        return{
            'id':self.id,
            'name':self.name,
            'fingerprint_id':self.fingerprint_id,
            'category':self.category,
        }

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    timeIn = db.Column(db.DateTime)
    timeOut = db.Column(db.DateTime)
    status = db.Column(db.String(10), nullable=False)

    def __init__(self, user_id, status):
        self.user_id = user_id
        self.status = status
        self.timeIn = None
        self.timeOut = None

        if self.status == 'registered':
            self.timeIn = datetime.now(EAT)

    def checkout(self):
        if self.status == 'registered' and self.timeIn is not None:
            self.timeOut = datetime.now(EAT)


# @app.route('/set_esp_url', methods=['POST'])
# def set_esp_url():
#     global ESP_URL
#     esp_ip = request.form.get('esp_url')  # Retrieve the IP address
#     logger.info(f"Received ESP IP: {'esp_ip'}")

#     if esp_ip:
#         # Construct the full URL with port 80
#         ESP_URL = f'http://{esp_ip}:80'
#         flash('ESP URL set successfully.')
#     else:
#         flash('Failed to set ESP URL.')
    
#     return "success"


@app.route('/notify_esp', methods=['POST'])
def notify_esp():
    if not ESP_URL:
        logger.error("ESP URL not set")
        flash("ESP URL not set")
        return "ESP URL not set", 400

    # Retrieve action and user_id from the request
    action = request.form.get('action')
    user_id = request.form.get('user_id')

    if not action or not user_id:
        flash("Missing action or user_id")
        return "Missing action or user_id", 400

    logger.info(f"ESP_URL is: {ESP_URL}")
    logger.info(f"Sending request to ESP with action: {action}, user_id: {user_id}")
    try:
        response = requests.post(ESP_URL + '/notify_esp', data={'action': action, 'user_id': user_id})
        response.raise_for_status()  # Raises an HTTPError if the response code was 4xx, 5xx
        logger.info(f"Successfully notified ESP with action: {action}, user_id: {user_id}")
        return "Notification sent successfully", 200
    except requests.RequestException as e:
        logger.error(f"Error notifying ESP: {e}")
        return "Error notifying ESP", 500

@app.route('/')
def index():
    return render_template('index.html')  #attendance=attendance_records

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
        try:
            name = request.form['name']
            fingerprint_id = request.form['fingerprint_id']
            category = request.form['category']
            new_user = User(name=name, fingerprint_id=fingerprint_id, category=category)
            db.session.add(new_user)
            db.session.commit()
        #sending the finger print id to the esp
            notify_esp('add',fingerprint_id)
            return redirect(url_for('users'))
        except Exception as e:
            app.logger.error(f"Error: {e}")
            return "500 error: Internal Server Error",500
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
        return redirect(url_for('users'))
    return render_template('update_user.html', user=user, categories=CATEGORIES)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'admin' not in session:
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found.')
        return redirect(url_for('users'))

    try:
        # Set user_id to None for all attendance records associated with this user
        Attendance.query.filter_by(user_id=user_id).update({'user_id': None}, synchronize_session='fetch')

        db.session.delete(user)
        db.session.commit()

        # Notify the ESP32 about the deletion
        notify_esp('delete', user.fingerprint_id)

        flash('User deleted successfully.')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}')

    return redirect(url_for('users'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        #authentication
        if username == 'admin' and password == 'password':  # to be replaced with a real authentication method
            session['admin'] = True
            return redirect(url_for('users'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))


@app.route('/search', methods=['GET'])
def search():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    query = request.args.get('query')
    if query:
        users = User.query.filter(User.name.ilike(f'%{query}%')).all()
    else:
        users = User.query.all()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify([user.to_dict() for user in users])
    else:
        return render_template('search.html', users=users)


@app.route('/manage_users')
def manage_users():
    if 'admin' not in session:
        return redirect(url_for('login'))
    users = User.query.all()  # Query all users from the database
    return render_template('manage_users.html', users=users)


#route to display record
@app.route('/attendance_log', methods=['GET', 'POST'])
def attendance_log():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    # attendance_records = Attendance.query.all()
    # attendance_records = Attendance.query.join(User).all()
    query=Attendance.query.join(User)

    if request.method == 'POST':
        search_name = request.form.get('search_name')
        search_month = request.form.get('search_month')
        search_day = request.form.get('search_day')

        #joining the tables
        #query = Attendance.query.join(User)

        if search_name:
            #attendance_records = Attendance.query.join(User).filter(User.name.ilike(f'%{search_name}%')).all()
            query = query.filter(User.name.ilike(f'%{search_name}%'))

        if search_month:
            try:
                month = int(search_month)
                if 1 <= month <= 12:
                    #query= query.filter(Attendance.timeIn.has(month=month))
                    query=query.filter(func.extract('month',Attendance.timeIn) == search_month)
                    # attendance_records = [record for record in attendance_records if record.timeIn and record.timeIn.month == month]
                else:
                    flash('Invalid month. Please enter a value between 1 and 12.')
            except ValueError:
                flash('Invalid month. Please enter a numeric value.')

        if search_day:
            try:
                day = int(search_day)
                if 1 <= day <= 31:
                    # attendance_records = [record for record in attendance_records if record.timeIn and record.timeIn.day == day]
                    #query = query.filter(Attendance.timeIn.has(day=day))
                    query=query.filter(func.extract('day',Attendance.timeIn)== search_day)
                else:
                    flash('Invalid day. Please enter a value between 1 and 31.')
            except ValueError:
                flash('Invalid day. Please enter a numeric value.')

      
    attendance_records=query.all()

    if not attendance_records:
        flash('No results found')

    return render_template('attendance_log.html', attendance=attendance_records)

#point to handle the reception of print
@app.route('/register_fingerprint', methods=['POST'])
def register_fingerprint():
    fingerprint_id = request.form.get('fingerprint_id')
    
    if not fingerprint_id:
        return "No Fingerprint_ID"
    
    user = find_user_by_fingerprint(fingerprint_id)
    if user:
        open_record = Attendance.query.filter_by(user_id=user.id, status='registered', timeOut=None).first()
        if open_record:
            open_record.checkout()
            db.session.commit()
        else:
            add_attendance_record(fingerprint_id, 'registered')
        
        return "Attendance recorded"
    else:
        return "User not found", 404

#helper function to search the user table 
def find_user_by_fingerprint(fingerprint_id):
    return User.query.filter_by(fingerprint_id=fingerprint_id).first()

#function to add the record 
def add_attendance_record(fingerprint_id, status):
    user = User.query.filter_by(fingerprint_id=fingerprint_id).first()
    if user:
        new_record = Attendance(user_id=user.id, status=status)
        db.session.add(new_record)
        db.session.commit()


#handling unclosed records
def close_open_records():
    open_records=Attendance.query.filter(Attendance.timeOut==None).all()
    for record in open_records:
        if record.timeIn.date() < now_in_eat().date():
            record.timeOut = datetime.combine(record.timeIn.date(), datetime.max.time(), tzinfo=EAT)
            db.session.commit()

scheduler = BackgroundScheduler(timezone='Africa/Kampala')#for running the close records functions at midnight evryday
# scheduler.add_job(func=close_open_records, trigger='cron',hour=0, minute=0)
scheduler.add_job(func=close_open_records, trigger="interval", seconds=86400) 
scheduler.start()
atexit.register(lambda: scheduler.shutdown())# for ensuring the application shuts down neatly 



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
