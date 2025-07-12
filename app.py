import os
from PIL import Image
from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)  # создаем приложение

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///siriusplaces.db'  # создаём базу данных

app.config['UPLOAD_FOLDER'] = 'static/uploads'  # назначаем папку для загружаемых файлов

app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # указываем форматы только для загрузки картинок

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # максимальный размер загружаемого файла = 2 МБ
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
                save_kwargs = {
                    'compress_level': 6
                }
            img.save(image_path, **save_kwargs)
    except:
        return 'При выполнении действия произошла ошибка!'


# создание таблицы в базе данных
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    image_name = db.Column(db.String(100))
    description = db.Column(db.Text, nullable=False)


@app.route('/')
def index():
    # получаем все данные из базы данных
    index = Post.query.all()
    # передаем данные в шаблон
    return render_template('index.html', index=index)


@app.route('/post', methods=['POST', 'GET'])
def post():
    if request.method == 'POST':
        title = request.form['title']
        address = request.form['address']
        category = request.form['category']
        description = request.form['description']
        file = request.files.get('image')

        # обрабатываем изображение
        image_name = None
        if file and file.filename != '':
            if not allowed_file(file.filename):
                return 'Разрешены только файлы: .png, .jpg, .jpeg, .gif'

            filename = secure_filename(file.filename)  # очищаем имя загружаемого файла
            upload_path = os.path.join(app.root_path,
                                       app.config['UPLOAD_FOLDER'])  # создаём абсолютный путь к папке для загрузок
            os.makedirs(upload_path, exist_ok=True)  # создаём папку, если она уже есть, ошибки не будет

            filepath = os.path.join(upload_path, filename)  # собираем полный путь для сохранения файла
            file.save(filepath)
            resize_image(filepath)
            image_name = filename

        post = Post(title=title, address=address, category=category, image_name=image_name, description=description)

        try:
            db.session.add(post)  # добавляем post в базу данных
            db.session.commit()  # сохраняем изменения
            return redirect('/')  # переносим пользователя на главную страницу
        except:
            return 'При добавлении записи произошла ошибка!'
    else:
        return render_template('post.html')


@app.route('/post/<int:post_id>')
def show_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)


@app.route('/post/<int:post_id>/reviews')
def show_reviews(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('reviews.html', post=post)


def reset_database():
    with app.app_context():
        db.drop_all()
        db.create_all()


if __name__ == '__main__':
    # создаем папку для загрузок, если ее нет
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # если нужно сбросить базу данных и создать ее заново, то нужно раскомментировать следующую строку
    # reset_database()
    app.run(debug=True)  # запускаем приложение
