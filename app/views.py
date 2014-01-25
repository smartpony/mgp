﻿#
# Обработка запросов клиентов
#

from flask import render_template, redirect, url_for, request
from flask.ext.login import login_user, logout_user, current_user, login_required
from flask.ext.sqlalchemy import sqlalchemy
func = sqlalchemy.func
from datetime import datetime
import hashlib
import os

# Импорт других файлов проекта
from app import app, db, lm
from models import User, ForumTopic, ForumMessage
from forms import PostingForm, LoginForm, RegisterForm, ProfileForm


# --- ЗАГРУЗКА ПОЛЬЗОВАТЕЛЯ ---------------------
# Функция загружает объект пользователя по его ID,
# который хранится в памяти
@lm.user_loader
def load_user(id):
    return(User.query.get(int(id)))


# --- СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ ---------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Форма регистрации
    form = RegisterForm()

    # Если отправлена форма
    if request.method == 'POST':
        # Данные из формы
        user_login = form.login.data
        user_email = form.email.data
        user_password = form.password.data
        user_password_confirm = form.password_confirm.data

        if user_password == user_password_confirm:
            user_password = hashlib.sha256(user_password).hexdigest()
        else:
            return(render_template('info.html',
                user=current_user,
                text='"Passwod" and "Confirm password" must be the same'))
            
        # Регистрация
        new_user = User(login=user_login,
            password=user_password,
            email=user_email)
        db.session.add(new_user)
        db.session.commit()

        # Войти под новым пользователем
        login_user(new_user)

        # Сообщение об успешной регистрации
        return(render_template('info.html',
            user=current_user,
            text='Registered succesfully'))

    # Вернуть страницу
    return(render_template('register.html',
        user=current_user,
        register_form=form))


# --- ВХОД ПОЛЬЗОВАТЕЛЯ -------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Форма логина
    form = LoginForm()

    # Если отправлена форма
    if request.method == 'POST':
        # Данные из формы
        user_login = form.login.data
        user_password = form.password.data

        # Найти пользователя в базе по логину и паролю
        user = User.query.filter \
            ((User.login==user_login) & \
            (User.password==hashlib.sha256(user_password).hexdigest())) \
            .first()

        # Если пользователь найден, войти
        if user is not None:
            login_user(user)
            current_user.last_seen = datetime.utcnow()
            db.session.commit()
            # Вернуться в корень форума
            return(redirect(url_for('forum')))
        # Если пользователь не найден, выдать ошибку
        else:
            return(render_template('info.html',
                user=current_user,
                text='Invalid login or password'))

    # Вернуть страницу
    return(render_template('login.html',
        user=current_user,
        login_form=form))


# --- КОРЕНЬ ------------------------------------
@app.route('/')
@app.route('/index')
def index():
    return(render_template('index.html',
        user=current_user))


# --- ФОРУМ -------------------------------------
@app.route('/forum', methods=['GET', 'POST'])
def forum():
    # Форма для постинга сообщений
    form = PostingForm()

    # Если отправлена форма постинга
    if form.validate_on_submit():
        # Данные из формы
        form_topic = form.topic.data
        form_message = form.message.data
        # Создание темы и обновление счётчиков у пользователя
        new_topic = ForumTopic(name=form_topic, author_id=current_user.id)
        current_user.message_count += 1
        current_user.topic_count += 1
        db.session.add(new_topic)
        # Коммит в этом месте нужен, чтобы появился ID
        db.session.commit()
        # Создание сообщения
        new_mes = ForumMessage(topic_id=new_topic.id, author_id=current_user.id, text=form_message)
        db.session.add(new_mes)
        db.session.commit()
        return(redirect(url_for('topic', topic_id=str(new_topic.id))))

    # Выборка всех тем с счётчиком сообщений для каждой
    # Подзапрос
    all_topics_subq = db.session.query(
        ForumMessage.topic_id, func.count(ForumMessage.id).label('mes_count')).\
        group_by(ForumMessage.topic_id).\
        subquery()
    # Основной запрос
    all_topics = db.session.query(
        ForumTopic, all_topics_subq.c.mes_count).\
        join(all_topics_subq, ForumTopic.id == all_topics_subq.c.topic_id).\
        order_by(ForumTopic.time_last.desc()).all()


    # Вернуть страницу
    return(render_template('forum.html',
        user=current_user,
        all_topics=all_topics,
        new_topic=form))


# --- ТЕМА НА ОТДЕЛЬНОЙ СТРАНИЦЕ ----------------
@app.route('/forum/topic/show/<topic_id>', methods=['GET', 'POST'])
def topic(topic_id):
    # Форма добавления нового сообщения
    form = PostingForm()

    # Объект текущего топика
    current_topic = ForumTopic.query.get(topic_id)

    # Если отправлена форма постинга
    if form.validate_on_submit():
        # Данные из формы
        form_message = form.message.data
        # Создание сообщения
        new_mes = ForumMessage(topic_id=topic_id, author_id=current_user.id, text=form_message)
        current_topic.time_last = datetime.utcnow()
        current_user.message_count += 1
        db.session.add(new_mes)
        # Запись последнего автора темы
        ForumTopic.query.get(topic_id).editor_id = current_user.id
        db.session.commit()
        return(redirect(url_for('topic', topic_id=topic_id)))

    # Счётчик просмотров +1
    current_topic.views += 1
    db.session.commit()

    # Выборка сообщений
    topic_name = current_topic.name
    topic_messages = ForumTopic.query.get(topic_id).message

    # Вернуть страницу
    return(render_template('topic.html',
        user=current_user,
        name=current_topic.name,
        topic_messages=topic_messages,
        add_message=form))


# --- УДАЛЕНИЕ ТЕМ ------------------------------
# Примечание: сообщения топика каскадно удаляются
# следом за топиком (см. model.py)
@app.route('/forum/topic/delete/<topic_id>')
@login_required
def delete_topic(topic_id):
    del_topic = ForumTopic.query.get(topic_id)
    # Является ли пользователь автором топика
    if del_topic.author == current_user:
        db.session.delete(del_topic)
        db.session.commit()
    # Если пользователь не является автором, выдать ошибку
    else:
        return(render_template('info.html',
            user=current_user,
            text="You can't delete topic if you are not it's author"))
    # Вернуться в корень форума
    return(redirect(url_for('forum')))


# --- УДАЛЕНИЕ СООБЩЕНИЙ ------------------------
@app.route('/forum/message/delete/<message_id>')
@login_required
def delete_message(message_id):
    del_mes = ForumMessage.query.get(message_id)
    topic_id = del_mes.topic_id
    # Является ли пользователь автором сообщения
    if del_mes.author == current_user:
        db.session.delete(del_mes)
        db.session.commit()
        # Если сообщение было последним, то удалить топик и вернуться в корень форума
        if ForumTopic.query.get(topic_id).message == []:
            db.session.delete(ForumTopic.query.get(topic_id))
            db.session.commit()
            return(redirect(url_for('forum')))
        # Вернуться на страницу, откуда было вызвано удаление
        # (если это было последнее сообщение темы, то возврат в корень форума)
        return(redirect(request.referrer))
    # Если пользователь не является автором, выдать ошибку
    else:
        return(render_template('info.html',
            user=current_user,
            text="You can't delete message if you are not it's author"))

    # Вернуться на страницу, откуда было вызвано удаление
    return(redirect(request.referrer))


# --- СПИСОК ПОЛЬЗОВАТЕЛЕЙ ----------------------
@app.route('/userlist')
def userlist():
    # Аргументы сортировки из GET-запроса
    sort_field = request.args.get('sort')
    sort_order = request.args.get('desc')

    # Сортировка по дате регистрации
    if sort_field == 'reg_date' and sort_order == 'True':
        users_list = User.query.order_by(User.reg_date.desc()).all()
    elif sort_field == 'reg_date':
        users_list = User.query.order_by(User.reg_date).all()
    # Сортировка по количеству тем
    elif sort_field == 'topics' and sort_order == 'True':
        users_list = User.query.order_by(User.topic_count.desc()).all()
    elif sort_field == 'topics':
        users_list = User.query.order_by(User.topic_count).all()
    # Сортировка по количеству сообщений
    elif sort_field == 'messages' and sort_order == 'True':
        users_list = User.query.order_by(User.message_count.desc()).all()
    elif sort_field == 'messages':
        users_list = User.query.order_by(User.message_count).all()
    # Регистронезависимая сортировка по логину
    elif sort_field == 'login' and sort_order == 'True':
        users_list = User.query.order_by(User.login.collate('NOCASE').desc()).all()
    else:
        users_list = User.query.order_by(User.login.collate('NOCASE')).all()

    # Вернуть страницу
    return(render_template('/userlist.html',
        user=current_user,
        users_list=users_list))


# --- ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ----------------------
@app.route('/profile/<user_id>')
def user_profile(user_id):
    user = User.query.get(user_id)
    # Вернуть страницу
    return(render_template('profile.html',
        user=current_user,
        profile=user,
        avatar='anonymous.jpg'))


# --- СВОЙ ПРОФИЛЬ ------------------------------
@app.route('/profile/me')
@login_required
def my_profile():
    # Вернуть страницу
    return(render_template('profile.html',
        user=current_user,
        profile=current_user,
        avatar=current_user.avatar))


# --- РЕДАКТИРОВАНИЕ ПРОФИЛЯ --------------------
@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    # Форма редактирования профиля
    form = ProfileForm()

    # Если отправлена форма постинга
    if request.method == 'POST':
        # Данные из формы
        current_user.city = form.city.data
        current_user.country = form.country.data
        current_user.email = form.email.data
        # Сохранение данных
        db.session.commit()
        # Редирект на страницу профиля
        return(redirect(url_for('my_profile')))

    # Вернуть страницу
    return(render_template('profile_edit.html',
        user=current_user,
        avatar='anonymous.jpg',
        profile_form=form))


# --- ЗАГРУЗКА АВАТАРА --------------------------
@app.route('/profile/edit/avatar', methods=['GET', 'POST'])
@login_required
def avatar_upload():
    if request.method == 'POST':
        # Загруженный файл из HTTP POST
        file = request.files['file']
        # Проверить расширение файла
        allowed_file_ext = ('jpg', 'jpeg', 'gif', 'png')
        file_ext = file.filename.split('.')[-1]
        if '.' in file.filename and file_ext in allowed_file_ext:
            file.save(os.path.join('avatar/', \
                'user_'+current_user.login+file_ext)
            return(render_template('info.html',
                user=current_user,
                text='Avatar uploaded'))
        else:
            return(render_template('info.html',
                user=current_user,
                text='Allowed file types: JPG, GIF, PNG'))
    return(render_template('avatar_upload.html',
        user=current_user))



# --- ВЫХОД -------------------------------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return(render_template('info.html',
        user=current_user,
        text='Logged out'))


# --- ОШИБКА 401 --------------------------------
@app.errorhandler(401)
def error_401(error_code):
    return(render_template('401.html',
        user=current_user))


# --- ОШИБКА 404 --------------------------------
@app.errorhandler(404)
def error_404(error_code):
    return(render_template('404.html',
        user=current_user))