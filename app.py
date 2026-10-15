from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Request, Review
from datetime import datetime
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'conf2027_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(login='Conf2027').first():
        admin = User(
            login='Conf2027',
            password_hash=generate_password_hash('Demo77'),
            fio='Администратор',
            phone='+70000000000',
            email='admin@conf.ru',
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        login = request.form.get('login', '').strip()
        password = request.form.get('password', '').strip()
        fio = request.form.get('fio', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()

        # Валидация логина: латиница и цифры, мин 6
        if not re.match(r'^[a-zA-Z0-9]{6,}$', login):
            flash('Логин: только латиница и цифры, мин. 6 символов', 'danger')
            return redirect(url_for('register'))

        # Валидация пароля: мин 8
        if len(password) < 8:
            flash('Пароль должен быть не менее 8 символов', 'danger')
            return redirect(url_for('register'))

        # Валидация ФИО: только кириллица и пробелы
        if not re.match(r'^[а-яА-ЯёЁ\s]+$', fio):
            flash('ФИО должно содержать только кириллицу и пробелы', 'danger')
            return redirect(url_for('register'))

        # Валидация телефона: 8(XXX)XXX-XX-XX
        if not re.match(r'^8\(\d{3}\)\d{3}-\d{2}-\d{2}$', phone):
            flash('Телефон в формате 8(XXX)XXX-XX-XX', 'danger')
            return redirect(url_for('register'))

        # Валидация email
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash('Неверный формат email', 'danger')
            return redirect(url_for('register'))

        # Проверка уникальности логина
        if User.query.filter_by(login=login).first():
            flash('Пользователь с таким логином уже существует', 'danger')
            return redirect(url_for('register'))

        new_user = User(
            login=login,
            password_hash=generate_password_hash(password),
            fio=fio,
            phone=phone,
            email=email,
            role='user'
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация успешна! Войдите в систему.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    if request.method == 'POST':
        login_val = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(login=login_val).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('admin_panel'))
            return redirect(url_for('profile'))
        else:
            flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    user_requests = Request.query.filter_by(user_id=current_user.id).order_by(Request.created_at.desc()).all()
    return render_template('profile.html', requests=user_requests)

@app.route('/add_review/<int:req_id>', methods=['POST'])
@login_required
def add_review(req_id):
    req = Request.query.get_or_404(req_id)
    if req.user_id != current_user.id:
        flash('Нельзя оставить отзыв на чужую заявку!', 'danger')
        return redirect(url_for('profile'))
    if req.status != 'Завершено':
        flash('Отзыв можно оставить только после завершения мероприятия.', 'warning')
        return redirect(url_for('profile'))
    existing = Review.query.filter_by(request_id=req_id, user_id=current_user.id).first()
    if existing:
        flash('Вы уже оставили отзыв.', 'info')
        return redirect(url_for('profile'))
    text = request.form.get('text', '').strip()
    if not text:
        flash('Напишите текст отзыва', 'danger')
        return redirect(url_for('profile'))
    new_review = Review(request_id=req_id, user_id=current_user.id, text=text)
    db.session.add(new_review)
    db.session.commit()
    flash('Спасибо за отзыв!', 'success')
    return redirect(url_for('profile'))

@app.route('/request', methods=['GET', 'POST'])
@login_required
def create_request():
    if request.method == 'POST':
        room = request.form.get('room', '').strip()
        date_str = request.form.get('start_date', '').strip()
        payment = request.form.get('payment', '').strip()

        if not room or not date_str or not payment:
            flash('Заполните все поля', 'danger')
            return redirect(url_for('create_request'))

        try:
            start_date = datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            flash('Неверный формат даты! Используйте ДД.ММ.ГГГГ', 'danger')
            return redirect(url_for('create_request'))

        new_req = Request(
            user_id=current_user.id,
            room=room,
            start_date=start_date,
            payment=payment,
            status='Новая'
        )
        db.session.add(new_req)
        db.session.commit()
        flash('Заявка отправлена на рассмотрение!', 'success')
        return redirect(url_for('profile'))
    return render_template('request.html')

@app.route('/admin')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('index'))
    all_requests = Request.query.order_by(Request.created_at.desc()).all()
    return render_template('admin.html', requests=all_requests)

@app.route('/admin/update_status/<int:req_id>', methods=['POST'])
@login_required
def update_status(req_id):
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    req = Request.query.get_or_404(req_id)
    new_status = request.form.get('status')
    valid_statuses = ['Новая', 'Мероприятие назначено', 'Завершено']
    if new_status in valid_statuses:
        req.status = new_status
        db.session.commit()
        flash(f'Статус #{req_id} изменён на "{new_status}"', 'success')
    else:
        flash('Неверный статус', 'danger')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')