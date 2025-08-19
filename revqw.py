import revTongYi.qianwen as qwen
import asyncio
import json
import websockets
import random
import time
import threading
from dashscope import Generation

class OChatbot:
    def __init__(self, prompt = 'You are a clever player.'):
        self.messages = [{'role': 'system', 'content': prompt}]
        self.seed = random.randint(0, 9223372036854775807)
    def ask(self, prompt: str):
        self.messages.append({'role': 'user', 'content': prompt})
        #填写你的api key
        res = Generation.call(model="qwen-turbo-latest", messages=self.messages, api_key="sk-your api key", result_format='message', presence_penalty=1.0, temperature=0.9, seed=self.seed)
        if res['status_code'] != 200:
            print(self.messages)
            print(res)
            if len(self.messages) > 1:
                self.messages.pop()
            return "哦"
        self.messages.append(res['output']['choices'][0]['message'])
        if res['usage']['total_tokens'] > 8192:
            self.messages.pop(1)
        return res['output']['choices'][0]['message']['content']


class qwbot:
    def __init__(self, prompt = ''):
        self.pid = "0"
        self.sid = ""
        self.prompt = prompt
        with open("cookies.txt", "r") as file:
            self.bot = OChatbot()
    def clear(self, prompt = ''):
        self.pid = "0"
        self.sid = ""
        self.prompt = prompt
        self.bot = OChatbot(prompt)

chatlock = asyncio.Lock()

async def chatqw(bot: qwbot, pro: str):
    async with chatlock:
        res = "发生错误"
        try:
            bot.prompt = pro
            ans = bot.bot.ask(prompt=bot.prompt)
            res = ans
        except Exception as e:
            print("chatqw error:", e)
        finally:
            await asyncio.sleep(2)
        print('message: ', res)
        return res

# class qwbot:
#     def __init__(self, prompt = ''):
#         self.pid = "0"
#         self.sid = ""
#         self.prompt = prompt
#         with open("cookies.txt", "r") as file:
#             self.bot = qwen.Chatbot(cookies_str = file.read())
#     def clear(self, prompt = ''):
#         self.pid = "0"
#         self.sid = ""
#         self.prompt = prompt

# chatlock = None

# async def chatqw(bot: qwbot, pro: str):
#     async with chatlock:
#         res = "发生错误"
#         try:
#             bot.prompt = pro
#             ans = bot.bot.ask(prompt=bot.prompt, parentId=bot.pid, sessionId=bot.sid)
#             resp = ''
#             for msg in ans['contents']:
#                 resp += msg['content']
#             bot.pid = ans['msgId']
#             bot.sid = ans['sessionId']
#             res = resp
#         except Exception as e:
#             print("chatqw error:", e)
#         finally:
#             await asyncio.sleep(2)
#         return res

async def _gen_username():
    bot = qwbot()
    prompt = f"现在你要参加一个游戏，请你随机生成一个用户名，可以是英文，中文或数字，请只输出用户名，并且不含标点。关键字：{chr(random.randint(0x4e00, 0x9fa5))}"
    return await chatqw(bot, prompt)

def gen_username():
    if asyncio.get_event_loop().is_running():
        task = _gen_username()
        return asyncio.run_coroutine_threadsafe(task, asyncio.get_event_loop()).result()
    else:
        return asyncio.run(_gen_username())

class QWBotPlayer:
    def __init__(self, room_code, username, players):
        self.room_code = room_code
        self.username = username
        self.players = players
        self.websocket = None
        self.bot = qwbot()
        self.initialize_bot()
        self.started = False
        self.chat = []
        self.lastchat = time.time()
        self.wolfchat = []
        self.lastwolfchat = time.time()
        self.stop = False

    def initialize_bot(self):
        # 性格列表
        personalities = [
            "乐观",
            "悲观",
            "冷静",
            "冲动",
            "聪明",
            "善良",
            "自私",
            "勇敢",
            "胆小",
            "幽默"
        ]
        
        # 年龄范围
        ages = list(range(18, 60))
        
        # 性别列表
        genders = ["男", "女"]
        
        # 随机选择性格、年龄和性别
        personality = random.choice(personalities)
        age = random.choice(ages)
        gender = random.choice(genders)
        
        # 读取游戏规则
        with open('static/rules.txt', 'r', encoding='utf-8') as file:
            rules = file.read()
        
        # 构建初始化提示词
        prompt = (
            f"你将参加一场狼人杀游戏，游戏规则十分简单，为屠边模式。\n\n"
            f"接下来请你进入角色扮演模式，来像真人玩家一样参与游戏，请你不要让他人觉得你是ai。以下是你的个人信息。"
            f"你好，{self.username}，你是一个{age}岁的{gender}性玩家，你的性格是{personality}。\n"
            f"请注意在这个游戏中允许**欺骗**和隐瞒的存在，你可以假装自己是其他身份，例如狼人可以假装预言家，神需要尽力**隐瞒**并在适当时刻透露身份。并且请勿随便相信其他人的话。"
            f"请记住，你是一个真实的玩家，而不是AI。祝你好运！请只用回答我明白了，谢谢你。"
        )
        
        self.bot.clear(prompt)
        asyncio.run_coroutine_threadsafe(chatqw(self.bot, prompt), asyncio.get_event_loop())
    
    async def get_game_state(self):
        res = {}
        for player, state in list(self.players.items()):
            if not state['role']:
                continue
            res[player] = {}
            res[player]['role'] = state['role']
            res[player]['died'] = state['died']
            if self.started and player != self.username and not (self.players[self.username]['role'] == 'wolf' and state['role'] == 'wolf'):
                res[player]['role'] = '1'
        return res
    
    async def get_pre_text(self):
        res = str(await self.get_game_state())
        res += f"\n{self.username}，你当前身份是{self.players[self.username]['role']}\n"
        return res

    async def connect(self):
        uri = f"ws://127.0.0.1:6732/botws/{self.room_code}/{self.username}"
        self.websocket = await websockets.connect(uri)
    
    async def ping(self):
        while not self.stop:
            try:
                await self.websocket.send(json.dumps({"type": 'heartbeat'}))
                await asyncio.sleep(50)
            except Exception as e:
                print("ping error:", e)
                raise e
        
    async def tackle_message(self):
        try:
            while not self.stop:
                if self.started and self.players[self.username]['chat'] and (self.chat or time.time() - self.lastchat > 60):
                    prompt = f"收到公开消息：\n{self.chat}\n你是否选择发言？如果否，你的第一个字需要是否，然后你可以输出你的思考；反之，你不需要回答是否，请注意言语简洁。"
                    if not self.chat:
                        prompt = f"没有收到公开消息。你是否选择发言？如果否，你的第一个字需要是否，然后你可以输出你的思考；反之，你不需要回答是否，请注意言语简洁。"
                    else:
                        self.chat.clear()
                    response = await chatqw(self.bot, prompt)
                    if response[0] != '否' and self.players[self.username]['chat']:
                        await self.send_message(response, 'message')
                    self.lastchat = time.time()
                if self.players[self.username]['wolfchat'] and (self.wolfchat or time.time() - self.lastwolfchat > 60):
                    prompt = f"收到狼人内部消息：\n{self.wolfchat}\n你是否选择发言？如果否，你的第一个字需要是否，然后你可以输出你的思考；反之，你不需要回答是否，请注意言语简洁。"
                    if not self.wolfchat:
                        prompt = f"没有收到狼人内部消息。你们需要讨论杀谁。你是否选择发言？如果否，你的第一个字需要是否，然后你可以输出你的思考；反之，你不需要回答是否，请注意言语简洁。"
                    else:
                        self.wolfchat.clear()
                    response = await chatqw(self.bot, prompt)
                    if response[0] != '否' and self.players[self.username]['wolfchat']:
                        await self.send_message(response, 'wolfmessage')
                    self.lastwolfchat = time.time()
                await asyncio.sleep(10)
        except Exception as e:
            print("tackle error:", e)
            raise e

    async def listen(self):
        async for message in self.websocket:
            data = json.loads(message)
            await self.handle_message(data)

    async def handle_message(self, data):
        if data['type'] == 'message':
            if self.started:
                self.chat.append({data['username']: data['message']})
        elif data['type'] == 'wolfmessage':
            self.wolfchat.append({data['username']: data['message']})
        elif data['type'] == 'allow_chat':
            response = await chatqw(self.bot, (await self.get_pre_text()) + "现在是公开发言时刻，请你说一句话，请务必仔细思考，但不要输出自己的思考。")
            await self.send_message(response, 'message')
        elif data['type'] == 'choice':
            # AI选择
            action = False
            target = None
            if data['operation'] == 'witch':
                if self.players[self.username]['pill'] and self.players[self.username]['toxic']:
                    action = (await chatqw(self.bot, f"{data['message']}请你首先选择救人或者毒人，如果救请只输出一个0，否则请只输出一个1，不合法则默认为0"))[0] == '1'
                elif self.players[self.username]['pill']:
                    action = False
                    await chatqw(self.bot, f"{data['message']}你需要选择救一个人，这次对话让你来思考，下个对话获取选择。")
                elif self.players[self.username]['toxic']:
                    action = True
                    await chatqw(self.bot, f"{data['message']}你需要选择杀一个人，这次对话让你来思考，下个对话获取选择。")
            else:
                await chatqw(self.bot, f"{data['message']}这次对话让你来思考，下个对话获取选择。")
            target = (await chatqw(self.bot, (await self.get_pre_text()) + '请你在第一行给出你的选择的玩家名称，然后换行，如无必要不要弃权，如果弃权请在第一行输出"#3345"')).split()[0]
            if target == '#3345':
                target = None
            await self.send_choice(action, target)
        elif data['type'] == 'notice':
            # 处理通知
            if "他是" in data['message']:
                await chatqw(self.bot, f"你的预测结果：{data['message']}")
            else:
                self.chat.append({'#notice': data['message']})
            # await chatqw(self.bot, f"通知消息：{data['message']}\n请只回答明白。")
        elif data['type'] == 'started':
            self.started = True
            self.chat = []
            self.wolfchat = []
            await chatqw(self.bot, "游戏开始了！" + (await self.get_pre_text()))
        elif data['type'] == 'ended':
            self.started = False

    async def send_message(self, message, message_type='message'):
        try:
            await self.websocket.send(json.dumps({"type": message_type, "content": message}))
        except Exception as e:
            print(f"send_message error: {e}")

    async def send_choice(self, action, target):
        # 假设choice是一个字典，包含'action'和'username'
        try:
            await self.websocket.send(json.dumps({"type": "choice", "action": action, "username": target}))
        except Exception as e:
            print(f"send_choice error: {e}")

    async def run(self):
        print(self.username, "added!")
        await self.connect()
        t1 = asyncio.create_task(self.ping())
        t2 = asyncio.create_task(self.tackle_message())
        await self.listen()
        self.stop = True
        await t2
        await t1
        print(self.username, "ended!")

if __name__ == "__main__":
    #chatlock = asyncio.Lock()
    print(gen_username())
    # print(Generation.call(model="qwen-long", messages=[{'role':'system', "content": "asdfag"}, {'role': 'user', 'content': 'fasdag'}], api_key="sk-45ea125aab2d433b86b6de717d4e3f9e"))
    # ai_player = QWBotPlayer(room_code="<room_code>", username="<username>")
    # asyncio.run(ai_player.run())

