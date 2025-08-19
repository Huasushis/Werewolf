import threading
import time
from collections import defaultdict
from queue import Queue
from copy import deepcopy
import json
import time


class Game(threading.Thread):
    def __init__(self, players, get_choice, seer_result, start_game, end_game, send_message, farewell_speech, allow_vote, wolf_speak, allow_chat, set_chat):
        super().__init__()
        # self.players = players
        self.get_choice = get_choice
        self.seer_result = seer_result
        self.start_game = start_game
        self.end_game = end_game
        self.send_message = send_message
        self.farewell_speech = farewell_speech
        self.allow_vote = allow_vote
        self.wolf_speak = wolf_speak
        self.allow_chat = allow_chat
        self.set_chat = set_chat
        self.game_state = players
        self.is_vote = False
        # self.game_state = defaultdict(lambda: {'role': None, 'died': False, 'chat': True, 'wolfchat': False})
        self.night_results = []
        self.stop = False
        self.day = False
        # self.initialize_game_state()

    # def initialize_game_state(self):
    #     for username, role in self.players.items():
    #         self.game_state[username]['role'] = role

    def run(self):
        try:
            self.start_game()
            self.night_phase()  # 游戏开始时先进行夜晚阶段
            while not self.game_over() and not self.stop:
                self.day_phase()
                if self.game_over():
                    break
                self.night_phase()
        except Exception as e:
            print('error', e)
            raise e
        finally:
            self.end_game(self.villagers_win())

    def day_phase(self):
        self.day = True
        self.send_message("天亮了，请睁眼")
        dead_players = deepcopy(self.check_night_results())
        self.night_results.clear()
        if dead_players:
            self.send_message("、".join(dead_players) + "被杀了")
            for dead_player in dead_players:
                self.farewell_speech(dead_player)
            for dead_player in dead_players:
                self.game_state[dead_player]['died'] = True
            if self.game_over():
                return
        else:
            self.send_message("昨夜是平安夜")
        
        self.send_message("白天讨论与投票开始")
        for player, state in list(self.game_state.items()):
            if state['role'] and not state['died']:
                self.send_message(f"请{player}发表言论")
                self.allow_chat(player)
        self.knight_kill()
        if self.game_over():
            return
        voted_out = self.vote()
        if self.game_over():
            return
        if voted_out:
            self.farewell_speech(voted_out)
            if self.game_state[voted_out]['role'] == 'hunter':
                self.hunter_action(voted_out)
            self.game_state[voted_out]['died'] = True

    def night_phase(self):
        self.day = False
        self.send_message("天黑请闭眼")
        self.kill_player()
        self.seer_check()
        self.witch_action()
        for dead_player in self.night_results:
            if self.game_state[dead_player]['role'] == 'hunter':
                self.hunter_action(dead_player)
        time.sleep(10)

    def check_night_results(self):
        return self.night_results

    def kill_player(self):
        self.send_message("狼人请睁眼")
        choices = []

        self.wolf_speak(True)
        self.allow_vote("狼人需要讨论并投票给杀的人", 'wolf')

        tout = 3 * 60
        for player, state in list(self.game_state.items()):
            if state['role'] == 'wolf' and not state['died']:
                st = time.time()
                choice, _ = self.get_choice(player, 'kill', "请选择你要杀的人", False, tout)
                tout -= time.time() - st - 1
                tout = max(tout, 5)
                if choice and choice in self.game_state and not self.game_state[choice]['died'] and self.game_state[choice]['role']:
                  choices.append(choice)

        self.wolf_speak(False)
        
        if choices:
            final_choice = max(set(choices), key=choices.count)
            # self.game_state[final_choice]['died'] = True
            self.night_results.append(final_choice)
            self.send_message(f"你们杀了{final_choice}", 'wolf')
        else:
            self.send_message("你们放弃杀人", 'wolf')
        self.send_message("狼人请闭眼")

    def seer_check(self):
        self.send_message("预言家请睁眼")
        for player, state in list(self.game_state.items()):
            if state['role'] == 'seer' and not state['died']:
                target, _ = self.get_choice(player, 'check', "请选择你要查验的人")
                if target and target in self.game_state:
                    result = self.game_state[target]['role']
                    self.seer_result(player, result)
        time.sleep(5)
        self.send_message("预言家请闭眼")
    
    def knight_kill(self):
        for player, state in list(self.game_state.items()):
            if state['role'] == 'knight' and not state['died'] and state['knight']:
                target, _ = self.get_choice(player, 'knight', '请选择你要刺杀的人，如果你选的人是狼人他死，否则你死，并且暴露身份')
                if target and target in self.game_state and not self.game_state[target]['died'] and self.game_state[target]['role']:
                    self.send_message(player + "刺杀了" + target)
                    if self.game_state[target]['role'] == 'wolf':
                        self.game_state[target]['died'] = True
                        state['knight'] = False
                        self.send_message(target + "是狼人，他死了！")
                    else:
                        state['died'] = True
                        self.send_message(target + "是好人，骑士死了！")
                    if self.game_over():
                        return
        time.sleep(10)
                    
    def witch_action(self):
        self.send_message("女巫请睁眼")
        for player, state in list(self.game_state.items()):
            if state['role'] == 'witch' and (not state['died'] or player in self.check_night_results()):
                if not state['toxic'] and not state['pill']:
                    continue
                dead_players = self.check_night_results()
                dead_str = "没有人死"
                if dead_players:
                    dead_str = "、".join(dead_players) + "被杀了"
                target, action = self.get_choice(player, 'witch', f"{dead_str}，你想救人还是杀人？(rescue/kill)")
                if state['toxic'] and not state['pill']:
                    action = True
                elif not state['toxic'] and state['pill']:
                    action = False
                if target and target in self.game_state and not self.game_state[target]['died'] and self.game_state[target]['role']:
                    if not action:
                        if target in dead_players:
                            state['pill'] = False
                            # self.game_state[target]['died'] = False
                            self.night_results.remove(target)
                    else:
                        # self.game_state[target]['died'] = True
                        state['toxic'] = False
                        if target not in self.night_results:
                            self.night_results.append(target)
        time.sleep(5)
        self.send_message("女巫请闭眼")

    def hunter_action(self, hunter):
        target, _ = self.get_choice(hunter, 'kill', "你死了，请选择你要带走的人")
        if target and target in self.game_state and not self.game_state[target]['died'] and self.game_state[target]['role']:
            if self.day:
                self.game_state[target]['died'] = True
                self.send_message(f'猎人杀了{target}')
            if not self.day and target not in self.night_results:
                self.night_results.append(target)

    def vote(self, flag = True, scope = []):
        self.is_vote = True
        self.set_chat(True)
        self.allow_vote("请投票给你认为要淘汰的人")
        votes = {}
        tout = 3 * 60
        for player, state in list(self.game_state.items()):
            if state['role'] and not state['died']:
                st = time.time()
                target, _ = self.get_choice(player, 'vote', f"{player} 请选择你要投票的人", False, tout)
                tout -= time.time() - st - 1
                tout = max(tout, 5)
                if target and target in self.game_state and not self.game_state[target]['died'] and self.game_state[target]['role'] and (not scope or target in scope):
                    # self.send_message(f"{player} 投票投给了 {target}")
                    if target in votes:
                        votes[target] += 1
                    else:
                        votes[target] = 1
                else:
                    # self.send_message(f"{player} 弃权")
                    pass
        self.set_chat(False)
        self.is_vote = False
        
        if not votes:
            self.send_message("无人出局")
            return None
        max_votes = max(votes.values())
        voted_out = [player for player, count in votes.items() if count == max_votes and player in self.game_state]
        self.send_message("投票结果：" + str(votes))
        
        if len(voted_out) > 1:
            if not flag:
                self.send_message("无人出局")
                return None
            self.send_message("出现平票，重新投票")
            self.send_message('、'.join(voted_out) + "票数最高，请在这些人中投票")
            return self.vote(False, voted_out)
        else:
            return voted_out[0]

    def villagers_win(self):
        wolves = [player for player, state in list(self.game_state.items()) if state['role'] == 'wolf' and not state['died']]
        return len(wolves) == 0

    def game_over(self):
        wolves = [player for player, state in list(self.game_state.items()) if state['role'] == 'wolf' and not state['died']]
        villagers = [player for player, state in list(self.game_state.items()) if state['role'] == 'villager' and not state['died']]
        common = [player for player, state in list(self.game_state.items()) if state['role'] and state['role'] != 'wolf' and not state['died']]
        return len(wolves) == 0 or len(wolves) >= len(common) or not len(villagers) or len(villagers) == len(common)
    
    def player_left(self, username):
        if username in self.game_state:
            self.game_state[username]['died'] = True
            self.send_message(f"{username} 离开了游戏，视为死亡")

# 示例用法
if __name__ == "__main__":
    players = {
        "Alice": {'role': 'wolf', 'died': False, 'chat': True, 'wolfchat': False, 'choice': False, 'information': None, 'toxic': False, 'pill': False},
        "Bob": {'role': 'hunter', 'died': False, 'chat': True, 'wolfchat': False, 'choice': False, 'information': None, 'toxic': False, 'pill': False},
        "Charlie": {'role': 'villager', 'died': False, 'chat': True, 'wolfchat': False, 'choice': False, 'information': None, 'toxic': False, 'pill': False},
        "David": {'role': 'witch', 'died': False, 'chat': True, 'wolfchat': False, 'choice': False, 'information': None, 'toxic': True, 'pill': True},
        "Eve": {'role': 'seer', 'died': False, 'chat': True, 'wolfchat': False, 'choice': False, 'information': None, 'toxic': False, 'pill': False},


        # "Alice": "wolf",
        # "Bob": "seer",
        # "Charlie": "witch",
        # "David": "hunter",
        # "Eve": "villager",
        # "Frank": "villager"
    }

    def get_choice(username, operation, prompt, flag=True):
        # 模拟用户输入
        print(prompt)
        choice = input("请输入你的选择: ")
        action = input("如果是女巫，请选择救人(rescue)或杀人(kill): ") if operation == 'witch' else None
        return choice, action

    def seer_result(target, result):
        print(f"预言家查到了 {target} 是 {result}")

    def start_game():
        print("游戏开始")

    def end_game(victory):
        if victory:
            print("村民阵营胜利")
        else:
            print("狼人阵营胜利")

    def send_message(message, role=None):
        print(message)

    def farewell_speech(player):
        print(f"{player} 发表遗言")
    
    def wolf_speak(flag):
        return
    
    def allow_vote(s, t=''):
        return
    
    def allow_chat(s):
        return

    game = Game(players, get_choice, seer_result, start_game, end_game, send_message, farewell_speech, allow_vote, wolf_speak, allow_chat)
    game.start()
    game.join()