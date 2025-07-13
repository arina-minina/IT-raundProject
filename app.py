import os
from PIL import Image
import requests
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask import jsonify
from datetime import datetime

app = Flask(__name__)  # создаем приложение

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///siriusplaces.db'  # создаём базу данных

app.config['UPLOAD_FOLDER'] = 'static/uploads'  # назначаем папку для загружаемых файлов

app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # указываем форматы только для загрузки картинок

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # максимальный размер загружаемого файла = 2 МБ

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # для подавления предупреждения
db = SQLAlchemy(app)


# вспомогательная функция для проверки расширения файла
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def resize_image(image_path, max_size=(1200, 1200), quality=95):
    try:
        with Image.open(image_path) as img:
            file_format = img.format  # сохраняем исходный формат изображения

            img.thumbnail(max_size, Image.Resampling.LANCZOS)  # определяем новые размеры с сохранением пропорций

            # параметры сохранения в зависимости от формата
            save_kwargs = {}
            if file_format == 'JPEG':
                save_kwargs = {
                    'quality': quality,
                    'optimize': True,
                    'progressive': True
                }
            elif file_format == 'PNG':
                save_kwargs = {'compress_level': 6}

            img.save(image_path, **save_kwargs)
    except:
        return False
    return True


# вынесение API ключа в конфигурацию
YANDEX_GEOCODE_API_KEY = 'dfcb1467-2945-4e9f-a1f4-2c3f0d47eef8'


def get_coordinates(address, api_key=YANDEX_GEOCODE_API_KEY):
    try:
        url = f"https://geocode-maps.yandex.ru/1.x/?format=json&apikey={api_key}&geocode={address}"
        response = requests.get(url, timeout=10)  # контроль времени ожидания ответа от сервера
        response.raise_for_status()  # проверка на ошибки HTTP
        data = response.json()  # преобразование сырого ответа сервера (текста) в Python-объект (словарь/список).

        pos = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point'][
            'pos']  # извлечение координат из ответа API Яндекс.Геокодера
        lon, lat = map(float, pos.split())
        return lat, lon
    except:
        return None, None


# создание таблиц в базе данных
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    image_name = db.Column(db.String(100))
    description = db.Column(db.Text, nullable=False)
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    post = db.relationship('Post', backref=db.backref('reviews', lazy=True))


@app.route('/geocode')
def geocode():
    address = request.args.get('address')  # получение параметра адреса
    if not address:
        return jsonify({'error': 'Параметр адреса является обязательным для заполнения'}), 400

    try:
        lat, lon = get_coordinates(address)
        if not lat or not lon:
            return jsonify({'error': 'Не удалось геокодировать адрес'}), 400
        return jsonify({'lat': lat, 'lon': lon})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    category_filter = request.args.get('category')
    query = Post.query

    if category_filter:
        query = query.filter_by(category=category_filter)

    posts = query.all()
    categories = db.session.query(Post.category).distinct().all()

    return render_template('index.html',
                           posts=posts,
                           categories=[c[0] for c in categories],
                           current_category=category_filter)


@app.route('/post', methods=['GET', 'POST'])
def post():
    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip()
            address = request.form.get('address', '').strip()
            category = request.form.get('category', '').strip()
            description = request.form.get('description', '').strip()
            file = request.files.get('image')

            if not all([title, address, category, description]):
                return 'Все текстовые поля обязательны для заполнения', 400

            # получаем координаты
            lat, lon = get_coordinates(address)
            if not lat or not lon:
                return 'Не удалось определить координаты для этого адреса', 400

            # обрабатываем изображение
            image_name = None
            if file and file.filename:
                if not allowed_file(file.filename):
                    return 'Разрешены только файлы: .png, .jpg, .jpeg, .gif', 400

                filename = secure_filename(file.filename)  # очищаем имя загружаемого файла

                upload_dir = os.path.join(app.root_path,
                                          app.config['UPLOAD_FOLDER'])  # создаём абсолютный путь к папке для загрузок

                os.makedirs(upload_dir, exist_ok=True)  # создаём папку, если она уже есть, ошибки не будет

                filepath = os.path.join(upload_dir, filename)  # собираем полный путь для сохранения файла

                file.save(filepath)
                if not resize_image(filepath):
                    os.remove(filepath)
                    return 'Ошибка обработки изображения', 500

                image_name = filename

            post = Post(
                title=title,
                address=address,
                category=category,
                image_name=image_name,
                description=description,
                lat=lat,
                lon=lon
            )

            db.session.add(post)
            db.session.commit()
            return redirect(url_for('index'))

        except:
            return 'При добавлении записи произошла ошибка!'

    return render_template('post.html')


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def show_post(post_id):
    post = Post.query.get_or_404(post_id)

    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            rating = request.form.get('rating', type=int)
            text = request.form.get('text', '').strip()

            if not all([name, rating, text]) or rating not in range(1, 6):
                return 'Неверные данные отзыва', 400

            review = Review(
                post_id=post.id,
                name=name,
                rating=rating,
                text=text
            )

            db.session.add(review)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post.id))

        except Exception as e:
            db.session.rollback()
            return f'Ошибка при добавлении отзыва: {str(e)}', 500

    # подсчет средней оценки
    reviews = Review.query.filter_by(post_id=post.id).order_by(Review.created_at.desc()).all()
    avg_rating = db.session.query(db.func.avg(Review.rating)).filter_by(post_id=post.id).scalar()
    avg_rating = round(avg_rating, 1) if avg_rating else 0

    return render_template('post_detail.html',
                           post=post,
                           reviews=reviews,
                           avg_rating=avg_rating)


def reset_database():
    with app.app_context():
        db.drop_all()
        db.create_all()


if __name__ == '__main__':
    # создаем папку для загрузок, если ее нет
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # если нужно сбросить базу данных и создать ее заново, то нужно раскомментировать следующую строку
    # reset_database()
    app.run(debug=True)
