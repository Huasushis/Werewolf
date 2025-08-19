from gevent import monkey
monkey.patch_all()
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, json
from markupsafe import escape
from flask_sockets import Sockets
import json
from collections import OrderedDict
from copy import deepcopy
from game import Game
from queue import Queue, Empty
import asyncio
from threading import Thread
from revqw import QWBotPlayer, gen_username
import revqw
import regex as re
# import os
# import binascii

loop = asyncio.new_event_loop()
#revqw.chatlock = asyncio.Lock(loop = loop)

def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def clean_str(s: str):
    return str(escape(re.sub(r'^\s+|\s+$', '', s)))[:512]

app = Flask(__name__)
# app.secret_key = binascii.hexlify(os.urandom(24)).decode('utf-8')
app.secret_key = '33702ccfed7bdf3acbc3b8bb0cbd74899edd22d202f7d63f'
sockets = Sockets(app)

rooms = {}

@app.route('/')
def index():
    # if 'room_code' in session:
    #     if session['room_code'] not in rooms or session['username'] not in rooms[session['room_code']]['players']:
    #         session.pop('room_code', None)
    return render_template('index.html')

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    if 'room_code' in session:
        if session['room_code'] not in rooms or session['username'] not in rooms[session['room_code']]['players']:
            session.pop('room_code', None)
    return response

'''
1: 狼人
2: 预言家
3: 女巫
4: 猎人
5: 村民
'''
name2id = {
    'wolf': '狼人',
    'seer': '预言家',
    'witch': '女巫',
    'hunter': '猎人',
    'villager': '平民',
    'knight': '骑士'
}

def default_player(room_code):
    return {'role': None, 'died': False, 'chat': not rooms[room_code]['started'], 'wolfchat': False, 'choice': False, 'information': Queue(), 'chatinf': Queue(), 'toxic': False, 'pill': False, 'knight': False, 'ai': False}

@app.route('/create_room', methods=['POST'])
def create_room():
    room_code = clean_str(request.json.get('room_code'))
    password = request.json.get('password')
    username = clean_str(request.json.get('username'))
    
    if room_code in rooms:
        return jsonify({'success': False, 'message': 'Room already exists'})
    if 'room_code' in session and session['room_code']:
        return jsonify({'success': False, 'message': 'You have already been in a room!'})
    
    rooms[room_code] = {
        'password': password,
        'players': OrderedDict(),
        'roles': {"wolf": 0, "seer": 0, "witch": 0, "hunter": 0, "villager": 0},
        'owner': None,
        'started': False,
        'chat': [],
        'wolfchat': [],
        'day': True,
        'sockets': {},
        'thread': None
    }
    session['room_code'] = room_code
    session['username'] = username
    rooms[room_code]['owner'] = session['username']
    rooms[room_code]['players'][username] = default_player(room_code)
    return jsonify({'success': True, 'room_code': room_code})

@app.route('/join_room', methods=['POST'])
def join_room():
    room_code = clean_str(request.json.get('room_code'))
    password = request.json.get('password')
    username = clean_str(request.json.get('username'))
    
    if 'room_code' in session and session['room_code']:
        return jsonify({'success': False, 'message': 'You have already been in a room!'})
    if room_code not in rooms or (rooms[room_code]['password'] and rooms[room_code]['password'] != password):
        return jsonify({'success': False, 'message': 'Invalid room code or password'})
    if username in rooms[room_code]['players']:
        return jsonify({'success': False, 'message': 'Username already exists'})
    
    session['room_code'] = room_code
    session['username'] = username
    rooms[room_code]['players'][username] = default_player(room_code)
    return jsonify({'success': True})

@app.route('/room/<room_code>', methods=['GET'])
def room(room_code):
    password = request.form.get('password', default=None)
    if 'username' not in session:
        return redirect(url_for('index'))

    username = session['username']
    if room_code not in rooms or (rooms[room_code]['password'] and rooms[room_code]['password'] != password):
        return redirect(url_for('index'))
    if 'room_code' in session:
        if session['room_code'] != room_code or username in rooms[room_code]['sockets']:
            return redirect(url_for('index'))
        else:
            if username not in rooms[room_code]['players']:
                session.pop('room_code', None)
                return redirect(url_for('index'))
            return render_template('room.html', room_code=room_code, players=rooms[room_code]['players'])
    
    print("direct in")
    session['room_code'] = room_code
    rooms[room_code]['players'][username] = default_player(room_code)
    return render_template('room.html', room_code=room_code, players=rooms[room_code]['players'])

@sockets.route('/ws/<room_code>')
def ws(ws, room_code):
    if room_code not in rooms or 'username' not in session or session['room_code'] != room_code:
        ws.close()
        return
    
    username = session['username']
    rooms[room_code]['sockets'][username] = ws
    print("connected: ", username)
    broadcast_message(room_code, {'type': 'attend', 'username': username})
    
    try:
        while not ws.closed:
            message = ws.receive()
            if message:
                message_data = json.loads(message)
                if message_data['type'] != 'heartbeat':
                    print(username, room_code, message_data)
                if message_data['type'] == 'message':
                    handle_message(room_code, username, message_data['content'])
                    if rooms[room_code]['started'] and not rooms[room_code]['thread'].is_vote:
                        rooms[room_code]['players'][username]['chat'] = False
                        rooms[room_code]['players'][username]['chatinf'].put(0)
                elif message_data['type'] == 'wolfmessage':
                    handle_wolf_message(room_code, username, message_data['content'])
                elif message_data['type'] == 'heartbeat':
                    # Handle heartbeat if needed
                    ws.send(json.dumps({'type': 'heartbeat'}))
                elif message_data['type'] == 'choice':
                    if rooms[room_code]['players'][username]['choice']:
                        rooms[room_code]['players'][username]['choice'] = False
                        target = message_data['username']
                        rooms[room_code]['players'][username]['information'].put((message_data['username'], message_data['action']))
                        if rooms[room_code]['thread'].is_vote:
                            if target:
                                send_message(room_code)(f"{username} 投票投给了 {target}")
                            else:
                                send_message(room_code)(f"{username} 弃权")
                elif message_data['type'] == 'kick':
                    if rooms[room_code]['owner'] == username and not rooms[room_code]['started']:
                        player = message_data['username']
                        if player in rooms[room_code]['sockets']:
                            rooms[room_code]['sockets'][player].close()
                elif message_data['type'] == 'addai':
                    continue
                    if rooms[room_code]['owner'] == username and not rooms[room_code]['started']:
                        player = gen_username()
                        while player in rooms[room_code]['players']:
                            player += '1'
                        rooms[room_code]['players'][player] = default_player(room_code)
                        rooms[room_code]['players'][player]['ai'] = True
                        rooms[room_code]['players'][player]['role'] = '1'
                        print("add:", player)
                        async def run_bot(player):
                            AiPlayer = QWBotPlayer(room_code, player, rooms[room_code]['players'])
                            await AiPlayer.run()
                        asyncio.run_coroutine_threadsafe(run_bot(player), loop)
                        # Thread(target = run_bot).start()
                        # executor = ThreadPoolExecutor(max_workers=1)
                        # executor.submit(run_bot)

    finally:
        print("leaved: ", username)
        role = rooms[room_code]['players'][username]['role']
        if rooms[room_code]['started'] and role:
            rooms[room_code]['roles'][role] -= 1
            rooms[room_code]['players'][username]['information'].put((None, False))
        handle_leave_room(room_code, username)

@sockets.route('/botws/<room_code>/<username>')
def ws(ws, room_code, username):
    if room_code not in rooms:
        ws.close()
        return
    
    rooms[room_code]['sockets'][username] = ws
    print("ai connected: ", username)
    broadcast_message(room_code, {'type': 'attend', 'username': username})
    
    try:
        while not ws.closed:
            message = ws.receive()
            if message:
                message_data = json.loads(message)
                if message_data['type'] != 'heartbeat':
                    print(username, room_code, message_data)
                if message_data['type'] == 'message':
                    handle_message(room_code, username, message_data['content'])
                    if rooms[room_code]['started'] and not rooms[room_code]['thread'].is_vote:
                        rooms[room_code]['players'][username]['chat'] = False
                        rooms[room_code]['players'][username]['chatinf'].put((None, False))
                elif message_data['type'] == 'wolfmessage':
                    handle_wolf_message(room_code, username, message_data['content'])
                elif message_data['type'] == 'heartbeat':
                    # Handle heartbeat if needed
                    ws.send(json.dumps({'type': 'heartbeat'}))
                elif message_data['type'] == 'choice':
                    if rooms[room_code]['players'][username]['choice']:
                        rooms[room_code]['players'][username]['choice'] = False
                        target = message_data['username']
                        rooms[room_code]['players'][username]['information'].put((message_data['username'], message_data['action']))
                        if rooms[room_code]['thread'].is_vote:
                            if target:
                                send_message(room_code)(f"{username} 投票投给了 {target}")
                            else:
                                send_message(room_code)(f"{username} 弃权")

    finally:
        print("ai leaved: ", username)
        role = rooms[room_code]['players'][username]['role']
        if rooms[room_code]['started'] and role:
            rooms[room_code]['roles'][role] -= 1
            rooms[room_code]['players'][username]['information'].put((None, False))
        handle_leave_room(room_code, username)


def handle_message(room_code, username, message):
    if not rooms[room_code]['players'][username]['chat']:
        return
    
    message = str(escape(message))
    rooms[room_code]['chat'].append({'username': username, 'message': message})
    broadcast_message(room_code, {'type': 'message', 'username': username, 'message': message})

def handle_wolf_message(room_code, username, message):
    if not rooms[room_code]['players'][username]['wolfchat']:
        return
    
    message = str(escape(message))
    rooms[room_code]['wolfchat'].append({'username': username, 'message': message})
    broadcast_message(room_code, {'type': 'wolfmessage', 'username': username, 'message': message}, 'wolf')

def broadcast_message(room_code, message, role = None):
    for username, socket in rooms[room_code]['sockets'].items():
        try:
            if not socket.closed:
                if not role or rooms[room_code]['players'][username]['died'] or not rooms[room_code]['players'][username]['role'] or rooms[room_code]['players'][username]['role'] == role:
                    if message['type'] != 'choice' or (rooms[room_code]['players'][username]['role'] and not rooms[room_code]['players'][username]['died']):
                        socket.send(json.dumps(message))
        except Exception as e:
            print("bm error", e)
            pass

def handle_leave_room(room_code, username):
    if username in rooms[room_code]['players']:
        del rooms[room_code]['players'][username]
    if username in rooms[room_code]['sockets']:
        del rooms[room_code]['sockets'][username]
    
    broadcast_message(room_code, {'type': 'leave', 'username': username})
    if rooms[room_code]['owner'] == username:
        for new_owner in rooms[room_code]['players']:
            if not rooms[room_code]['players'][new_owner]['ai']:
                rooms[room_code]['owner'] = new_owner
                rooms[room_code]['sockets'][new_owner].send(json.dumps({'type': 'owner_change'}))
                return
        for ws in rooms[room_code]['sockets'].values():
            ws.close()
        if rooms[room_code]['thread']:
            rooms[room_code]['thread'].stop = True
            rooms[room_code]['thread'].join()
        del rooms[room_code]

@app.route('/leave_room', methods=['GET'])
def del_room_code():
    session.pop('room_code', None)
    return jsonify({'success': True})

def ligalize_dict(dic):
    return json.loads(json.dumps(dic, default= lambda _: None))

@app.route('/get_game_state', methods=['GET'])
def get_game_state():
    if 'room_code' not in session:
        return jsonify({'success': False, 'message': 'You are not in a game'})
    # if 'room_code' in session:
    #     if session['room_code'] not in rooms or session['username'] not in rooms[session['room_code']]['players']:
    #         session.pop('room_code', None)
    #         return jsonify({'success': False, 'message': 'You are not in a game'})

    room_code = session['room_code']
    username = session['username']
    room = rooms[room_code]
    tot = 0
    for role in room['players'].values():
        tot += 1 if role['role'] else 0

    players = ligalize_dict(room['players'])
    wolfchat = deepcopy(room['wolfchat'])
    if room['started'] and not room['players'][username]['died'] and room['players'][username]['role'] not in {None, 'wolf'}:
        wolfchat = []
    if room['started']:
        if room['players'][username]['role']:
            for name, role in players.items():
                role['wolfchat'] = False
                role['toxic'] = False
                role['pill'] = False
                role['knight'] = False
                if not room['players'][username]['died'] and role['role'] and name != username and not (role['role'] == 'wolf' and players[username]['role'] == 'wolf'):
                    role['role'] = '1'
    return jsonify(ligalize_dict({
        'success': True,
        'players': players,
        'chat': room['chat'],
        'wolfchat': wolfchat,
        'day': room['day'],
        'started': room['started'],
        'attendedPlayers': tot,
        'self': room['players'][username],
        'roles': room['roles']
    }))

@app.route('/is_owner', methods=['GET'])
def is_owner():
    if 'room_code' not in session:
        return jsonify({'success': False, 'message': 'You are not in a game'})
    room_code = session['room_code']
    username = session['username']
    return jsonify({'success': True, 'is_owner': rooms[room_code]['owner'] == username})

@app.route('/set_role', methods=['POST'])
def set_role():
    if 'room_code' not in session:
        return jsonify({'success': False, 'message': 'You are not in a game'})
    room_code = session['room_code']
    username = session['username']
    role = request.json.get('role')
    
    if rooms[room_code]['started']:
        return jsonify({'success': False, 'message': 'Game has already started'})
    if role == '0':
        rooms[room_code]['players'][username]['role'] = None
    else:
        rooms[room_code]['players'][username]['role'] = role
    return jsonify({'success': True})

@app.route('/start_game', methods=['POST'])
def start_game():
    if 'room_code' not in session:
        return jsonify({'success': False, 'message': 'You are not in a game'})
    room_code = session['room_code']
    username = session['username']
    if rooms[room_code]['owner'] != username:
        return jsonify({'success': False, 'message': 'Only the owner can start the game'})
    if rooms[room_code]['started']:
        return jsonify({'success': False, 'message': 'Already started'})

    roles = request.json.get('roles')

    for num in roles.values():
        if num < 0:
            return jsonify({'success': False, 'message': '分配不合法'})
    if roles.keys() != name2id.keys():
        return jsonify({'success': False, 'message': '傻der不要改包'})

    participated_players = []
    for username, role in rooms[room_code]['players'].items():
        if role['role']:
            participated_players.append(username)
    total_players = len(participated_players)

    total_roles = sum(roles.values())
    if total_roles != total_players:
        return jsonify({'success': False, 'message': '角色数量不等于总人数'})

    # Assign roles to players
    rooms[room_code]['roles'] = roles
    roles_list = []
    for role, count in roles.items():
        for _ in range(count):
            roles_list.append(role)

    import random
    random.shuffle(roles_list)

    for player, role in zip(participated_players, roles_list):
        rooms[room_code]['players'][player]['role'] = role
        if role == 'witch':
            rooms[room_code]['players'][player]['toxic'] = True
            rooms[room_code]['players'][player]['pill'] = True
        elif role == 'knight':
            rooms[room_code]['players'][player]['knight'] = True

    rooms[room_code]['started'] = True
    broadcast_message(room_code, {'type': 'notice', 'message': '游戏开始了！'})
    if rooms[room_code]['thread']:
        rooms[room_code]['thread'].join()
    rooms[room_code]['thread'] = Game(rooms[room_code]['players'],
                                      get_choice(room_code),
                                      seer_result(room_code),
                                      start_game(room_code),
                                      end_game(room_code),
                                      send_message(room_code),
                                      farewell_speech(room_code),
                                      allow_vote(room_code),
                                      wolf_speak(room_code),
                                      allow_chat(room_code),
                                      set_chat(room_code))
    rooms[room_code]['thread'].start()

    return jsonify({'success': True})

def game_op(func):
    def wrapper(room_code):
        def foo(*args, **kwargs):
            ret = (None, False)
            try:
                ret = func(room_code, *args, **kwargs)
            except Exception as e:
                print("wp:", e)
                raise e
            return ret
        return foo
    return wrapper

@game_op
def get_choice(room_code, username, operation, message, ws_send = True, tout = 3 * 60):
    if ws_send:
        rooms[room_code]['players'][username]['choice'] = True
        rooms[room_code]['sockets'][username].send(json.dumps({'type': 'choice', 'operation': operation, 'message': message}))
    target = None
    action = False
    try:
        target, action = rooms[room_code]['players'][username]['information'].get(timeout=tout)
    except Empty:
        rooms[room_code]['players'][username]['choice'] = False
    return target, action

@game_op
def seer_result(room_code, username, result):
    # 预言家查到了某个玩家的身份
    rooms[room_code]['sockets'][username].send(json.dumps({'type':'notice', 'message': f"他是{'好人' if result != 'wolf' else '坏人'}"}))
    return

@game_op
def start_game(room_code):
    # 游戏开始
    rooms[room_code]['started'] = True
    for player in rooms[room_code]['players'].values():
        player['chat'] = False
        player['died'] = False
    broadcast_message(room_code, {"type": "started"})
    return

@game_op
def end_game(room_code, victory):
    # 游戏结束
    if victory:
        send_message(room_code)("村民阵营胜利")
    else:
        send_message(room_code)("狼人阵营胜利")
    rooms[room_code]['day'] = True
    rooms[room_code]['started'] = False
    rooms[room_code]['chat'] = []
    rooms[room_code]['wolfchat'] = []
    for player in rooms[room_code]['players'].values():
        player['chat'] = True
        player['wolfchat'] = False
        # player['died'] = False
    for i in rooms[room_code]['roles'].values():
        i = 0
    broadcast_message(room_code, {"type": "ended"})

@game_op
def send_message(room_code, message, role = None):
    # 发送消息
    broadcast_message(room_code, {"type": "notice", "message": message}, role)
    if not role:
        broadcast_message(room_code, {"type": "message", "username": "system", "message": message})
    if role == 'wolf':
        broadcast_message(room_code, {"type": "wolfmessage", "username": "system", "message": message}, role)

@game_op
def farewell_speech(room_code, player):
    # 发表遗言
    send_message(room_code)(f"房间 {room_code}: {player} 发表遗言，限时90s")
    rooms[room_code]['players'][player]['chat'] = True
    try:
        rooms[room_code]['players'][player]['chatinf'].get(timeout=90)
    except Empty:
        rooms[room_code]['players'][player]['chat'] = False

@game_op
def allow_vote(room_code, message, role = None):
    for player in rooms[room_code]['players'].values():
        if (not role or player['role'] == role) and player['role'] and not player['died']:
            player['choice'] = True
    broadcast_message(room_code, {"type": "choice", "operation": "None", "message": message}, role)

@game_op
def wolf_speak(room_code, flag):
    for player, state in rooms[room_code]['players'].items():
        if state['role'] == 'wolf' and not state['died']:
            state['wolfchat'] = flag
    return

@game_op
def allow_chat(room_code, player):
    rooms[room_code]['players'][player]['chat'] = True
    rooms[room_code]['sockets'][player].send(json.dumps({'type': 'allow_chat'}))
    try:
        rooms[room_code]['players'][player]['chatinf'].get(timeout=90)
    except Empty:
        rooms[room_code]['players'][player]['chat'] = False
    return

@game_op
def set_chat(room_code, flag):
    for player in rooms[room_code]['players'].values():
        if player['role'] and not player['died']:
            player['chat'] = flag


if __name__ == '__main__':
    Thread(target=start_loop, args=(loop,), daemon=True).start()
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('0.0.0.0', 6732), app, handler_class=WebSocketHandler)
    print('server started')
    server.serve_forever()

# if __name__ == '__main__':
#     app.run(debug=True, host="0.0.0.0", port=6732)
