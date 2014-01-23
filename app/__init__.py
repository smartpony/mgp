﻿#
# Инициализация приложения
#

# Основной объект приложения Flask
from flask import Flask
# Работа с БД через ORM
from flask.ext.sqlalchemy import SQLAlchemy
# Аутентификация пользователей
from flask.ext.login import LoginManager

# Создать экземпляр класса, который будет WSGI-приложением,
# аргумент помогает определить роль (место вызова) - либо это
# модуль, либо standalone-приложение
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////python/mgp/base.db'
db = SQLAlchemy(app)

# Отключение CSRF для WTF-Forms
app.config['CSRF_ENABLED'] = True
app.config['SECRET_KEY'] = 'just qwerty'

# Инициализация системы логинов
lm = LoginManager()
lm.init_app(app)

# Импорт обработчиков запросов клиентов
from app import views

# Импорт модели БД
from app import models