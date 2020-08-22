import asyncio
import json
import uuid
from sanic.log import logger


NAME = "dummy"
TITLE = "Dummy Game"


class Game:
    def __init__(self):
        self._players = dict()
        self._lock_add_player = asyncio.Lock()
        self._max_players = 4
        self._message_history = []
        self._max_history_messages = 100

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
        self._message_history.append(message)
        print(f"broadcast, {len(self._message_history)}")
        for name, player in self._players.items():
            player.notify(message)
    
    def resend_history(self, player):
        for message in self._message_history[-self._max_history_messages:]:
            player.notify(message, historical=True)


class WebsocketPlayer:
    def __init__(self, user, game):
        self._user = user
        self._game = game
        self._websocket = None
        self._send_new_messages = None

    async def run(self, websocket):
        self._send_new_messages = False
        self._websocket = websocket
        self._game.resend_history(self)
        self._send_new_messages = True
        try:
            while True:
                data = await websocket.recv()

                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    logger.error(f"unable to JSON-decode '{data}'")
                    continue

                message = data.get("message")
                if message is not None:
                    text = message.get("text")
                    if text is not None and text != "":
                        self._game.broadcast({
                            "id": str(uuid.uuid4()), 
                            "text": message["text"], 
                            "user": self._user
                        })

        except asyncio.CancelledError as ex:
            self._websocket = None
            logger.info(f"WebsocketPlayer {self._user} client closed websocket connection")
    
    def notify(self, message, historical=False):
        if self._websocket is not None:
            if historical or self._send_new_messages:
                asyncio.create_task(self._websocket.send(json.dumps(message)))
