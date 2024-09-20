import json
import random
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Секретный ключ для сессий
socketio = SocketIO(app)

# Хранилище пользователей и лайков
users = {}
likes = {}
current_question = None  # Для хранения текущего вопроса

# Загружаем вопросы из JSON
with open('questions.json', 'r') as f:
    questions = json.load(f)['questions']

# Главная страница для входа
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        if username not in users and username != "":
            users[username] = 0  # Изначально лайков нет
            session['username'] = username
            session['used_questions'] = []  # Инициализируем список использованных вопросов
            # Уведомляем всех клиентов о новом пользователе
            socketio.emit('user_list_update', list(users.keys()), broadcast=True)
            return redirect(url_for('game'))
        else:
            return render_template('index.html', error="Имя уже занято или пустое")
    return render_template('index.html')

# Страница игры
@app.route('/game', methods=['GET', 'POST'])
def game():
    if 'username' not in session:
        return redirect(url_for('index'))

    username = session['username']

    # Проверяем, есть ли новый вопрос
    if request.method == 'POST':
        if 'liked_user' in request.form:  # Лайк другому пользователю
            liked_user = request.form['liked_user']
            if liked_user in users and liked_user != username:
                likes[liked_user] = likes.get(liked_user, 0) + 1

    return render_template('game.html', username=username, current_question=current_question)

# AJAX маршрут для получения текущего вопроса
@app.route('/get_question', methods=['GET'])
def get_question():
    return jsonify(question=current_question)

# Страница администратора
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    global current_question
    if request.method == 'POST':
        # Удаление пользователя
        if 'delete_user' in request.form:
            user_to_delete = request.form['delete_user']
            if user_to_delete in users:
                del users[user_to_delete]
                likes.pop(user_to_delete, None)  # Удаляем также лайки этого пользователя
                # Уведомляем всех клиентов об обновлении списка пользователей
                socketio.emit('user_list_update', list(users.keys()), broadcast=True)

        # Показать новый вопрос
        if 'show_question' in request.form:
            available_questions = [q for q in questions if q not in session.get('used_questions', [])]
            
            if available_questions:  # Если есть доступные вопросы
                question_to_show = random.choice(available_questions)
                session['used_questions'].append(question_to_show)  # Сохраняем вопрос в списке использованных
                session.modified = True  # Указываем, что сессия была изменена
                current_question = question_to_show  # Обновляем текущий вопрос
                socketio.emit('new_question', {'question': current_question}, broadcast=True)
            else:
                current_question = 'Все вопросы были показаны!'  # Устанавливаем сообщение о том, что все вопросы показаны
                socketio.emit('new_question', {'question': current_question}, broadcast=True)

    return render_template('admin.html', users=users.keys(), current_question=current_question)

# Маршрут для получения списка пользователей (AJAX)
@app.route('/get_users', methods=['GET'])
def get_users():
    return jsonify(list(users.keys()))  # Возвращаем список пользователей в формате JSON

# Маршрут для получения лайков (AJAX)
@app.route('/get_likes', methods=['GET'])
def get_likes():
    return jsonify(likes)  # Возвращаем лайки в формате JSON

# Страница с результатами лайков
@app.route('/results/hiddenpage')
def results():
    return render_template('results.html', likes=likes)

# Обработка соединения WebSocket
@socketio.on('connect')
def handle_connect():
    username = session.get('username')
    if username:
        print(f'{username} connected.')
        # Отправляем текущий вопрос при подключении
        if current_question:
            emit('new_question', {'question': current_question})

# Обработка отключения WebSocket
@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    if username:
        print(f'{username} disconnected.')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
