import asyncio
import importlib
import os
import uuid
from json import dumps as json_dumps
from json import loads as json_loads
from sanic import Sanic
from sanic.log import logger
from sanic.response import html, json
from sanic.websocket import WebSocketProtocol


app = Sanic("happy-games")


ENGINE_DIR = "engines"
ENGINE_PACKAGES = {
    name: importlib.import_module(f"{ENGINE_DIR}.{name}") 
    for name in os.listdir(ENGINE_DIR)
}

app.static("/", "static/index.html")
app.static("/static", "static")
for name in ENGINE_PACKAGES:
    app.static(f"/{name}/static", f"engines/{name}/static")


game_and_engine_by_gameid = dict()
games_by_user = dict()


@app.route("/engine", methods=["GET"])
async def list_available_engines(request):
    return json({
        "status": "ok",
        "result": {
            "engines": [
                {
                    "name": name,
                    "title": game.TITLE
                }
                for name, game in ENGINE_PACKAGES.items()
            ]
        }
    })


@app.route("/game", methods=["POST"])
async def create_game(request):

    args = request.json
    if args is None:
        return json({
            "status": "error",
            "result": "no arguments supplied"
        })

    user = args.get("user")
    if user is None:
        return json({
            "status": "error",
            "result": "no user supplied"
        })
    
    if user in games_by_user:
        return json({
            "status": "error",
            "result": f"user already joined a game"
        })

    engine_name = args.get("engine-name")
    if engine_name is None:
        return json({
            "status": "error",
            "result": "no engine name supplied"
        })

    engine = ENGINE_PACKAGES.get(engine_name)
    if engine is None:
        return json({
            "status": "error",
            "result": f"unknown game '{engine_name}'"
        })

    game_id = uuid.uuid4()
    game = engine.Game(game_id)
    player = engine.WebsocketPlayer(user, game)
    if not await game.add_player(user, player):
        return json({
            "status": "error",
            "result": f"internal error"
        })

    game_and_engine_by_gameid[game_id] = (game, engine)
    games_by_user[user] = game

    return json({
        "status": "ok",
        "result": {
            "gameId": str(game_id)
        }
    })


@app.route("/game", methods=["GET"])
async def list_games(request):
    return json({
        "status": "ok",
        "result": {
            "games": [
                {
                    "gameId": str(game_id),
                    "engine": {
                        "name": engine.NAME,
                        "title": engine.TITLE
                    }
                }
                for game_id, (game, engine) in game_and_engine_by_gameid.items()
            ]
        }
    })


@app.websocket("/game-socket")
async def game_socket(request, websocket):
    try:
        game_request = json_loads(await websocket.recv())
        
        user = game_request.get("user")
        if user is None:
            await websocket.send(json_dumps({
                "connectResponse": {
                    "status": "error"
                }
            }))
            return

        game_id = game_request.get("gameId")
        if game_id is None:
            await websocket.send(json_dumps({
                "connectResponse": {
                    "status": "error"
                }
            }))
            return
        
        game_id = uuid.UUID(game_id)
        game_and_engine = game_and_engine_by_gameid.get(game_id)
        if game_and_engine is None:
            await websocket.send(json_dumps({
                "connectResponse": {
                    "status": "error",
                    "message": "invalid game id"
                }
            }))
            return
        game, engine = game_and_engine

        game2 = games_by_user.get(user)
        if game2 is not None and game2 != game:
            await websocket.send(json_dumps({
                "connectResponse": {
                    "status": "error",
                    "message": "user already joined another game"
                }
            }))
            return

        player = game.get_player(user)
        if player is None:
            player = engine.WebsocketPlayer(user, game)
            if not await game.add_player(user, player):
                await websocket.send(json_dumps({
                    "connectResponse": {
                        "status": "error",
                        "message": "could not join game"
                    }
                }))
                return
            logger.info(f"user {user} joined game {game_id}")
        logger.info(f"user {user} connected to game")
        
        asyncio.create_task(websocket.send(json_dumps({
            "connectResponse": {
                "status": "ok"
            }
        })))

        if await player.run(websocket):
            await game.remove_player(user)
            games_by_user.pop(user)
            if game.num_players == 0:
                game_and_engine_by_gameid.pop(game_id)
                

    except asyncio.CancelledError as ex:
        print("websocket connection closed by client")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0", 
        port=8080, 
        auto_reload=True, 
        protocol=WebSocketProtocol
    )

