import asyncio
import json
import uuid
from sanic.log import logger


NAME = "dummy"
TITLE = "Dummy Game"


class Game:
    def __init__(self, game_id):
        self._id = game_id
        self._players = dict()
        self._lock_add_player = asyncio.Lock()
        self._max_players = 4
        self._message_history = []
        self._max_history_messages = 100
    
    @property
    def num_players(self):
        return len(self._players)

    async def add_player(self, name, player):
        async with self._lock_add_player:
            if name in self._players:
                logger.info(f"player '{name}' is already in game {self._id}")
                return False
            if len(self._players) == self._max_players:
                logger.info(f"maximum number of players reached")
                return False
            self._players[name] = player
            return True

    async def remove_player(self, name):
        async with self._lock_add_player:
            player = self._players.get(name)
            if player is None:
                logger.info(f"'{name}' is not a player of game {self._id}")
                return False
            self._players.pop(name)
            logger.info(f"removed '{name}' from game {self._id}, {len(self._players)} left")
            return True

    def get_player(self, name):
        return self._players.get(name)

    def broadcast(self, message):
        self._message_history.append(message)
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
        """
        returns whether the player disconnected from the game.
        """
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

                if (message := data.get("message")) is not None:
                    text = message.get("text")
                    if text is not None and text != "":
                        self._game.broadcast({
                            "id": str(uuid.uuid4()), 
                            "text": message["text"], 
                            "user": self._user
                        })
                    continue

                if (action := data.get("action")) is not None:
                    if (todo := action.get("todo")) == "disconnect":
                        self._websocket = None
                        return True
                    else:
                        logger.error(f"unknown action '{todo}'")
                    continue

        except asyncio.CancelledError as ex:
            self._websocket = None
            logger.info(f"WebsocketPlayer {self._user} client closed websocket connection")
        
        return False
    
    def notify(self, message, historical=False):
        if self._websocket is not None:
            if historical or self._send_new_messages:
                asyncio.create_task(self._websocket.send(json.dumps(message)))
