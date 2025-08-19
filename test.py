import asyncio
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
manager = multiprocessing.Manager()
from threading import Thread

class QWBotPlayer:
    def __init__(self, room_code, player, players):
        self.room_code = room_code
        self.player = player
        self.players = players

    async def run(self):
        print(f"Running bot player for room {self.room_code} and player {self.player}")
        # 模拟异步操作
        await asyncio.sleep(1)
        print("finished!")
        print(self.players[0])
        self.players[0] = 'player'
        print(self.players[0])


# 假设这是你的房间和玩家数据
rooms = {
    'room1': {'players': ['player1', 'player2']}
}
room_code = 'room1'
player = 'player1'
def run():
    for i in range(3):
        def run_bot(room_code, player, players):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # try:
            AiPlayer = QWBotPlayer(room_code, player, players)
            loop.create_task(AiPlayer.run())
            loop.run_forever()
                # loop.run_until_complete(AiPlayer.run())
            # finally:
            #     loop.close()
        Thread(target=run_bot, args=(room_code, player, rooms[room_code]['players'])).start()
    import time
    time.sleep(2)
    print(rooms[room_code]['players'])

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
run()