import asyncio
import json
from sanic.log import logger


TITLE = "Dummy Game"


class Game:
    def __init__(self):
        self._players = dict()
        self._lock_add_player = asyncio.Lock()
        self._max_players = 4

    async def add_player(self, name, player):
        async with self._lock_add_player:
            if name in self._players:
                logger.info(f"player '{name}' is already in game")
                return False
            if len(self._players) == self._max_players:
                logger.info(f"maximum number of players reached")
                return False
            self._players[name] = player
            return True

    def get_player(self, name):
        return self._players.get(name)

    def broadcast(self, message):
        for name, player in self._players.items():
            player.notify(message)


class WebsocketPlayer:
    def __init__(self, user, game):
        self._user = user
        self._game = game

    async def run(self, websocket):
        self._websocket = websocket
        try:
            while True:
                data = await websocket.recv()
                # TODO: check if data = {"message": "..."}
                data = json.loads(data)
                self._game.broadcast({"message": data["message"], "user": self._user})
        except asyncio.CancelledError as ex:
            self._websocket = None
            logger.info(f"WebsocketPlayer {self._user} client closed websocket connection")
    
    def notify(self, message):
        asyncio.create_task(self._websocket.send(json.dumps(message)))
