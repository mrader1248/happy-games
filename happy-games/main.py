import importlib
import os
import uuid
from sanic import Sanic
from sanic.log import logger
from sanic.response import json


app = Sanic("happy-games")


ENGINE_DIR = "engines"
ENGINE_PACKAGES = {
    name: importlib.import_module(f"{ENGINE_DIR}.{name}") 
    for name in os.listdir(ENGINE_DIR)
}

games_by_gameid = dict()
games_by_user = dict()


@app.route("/engine", methods=["GET"])
async def list_available_games(request):
    return json({
        "status": "ok",
        "result": [
            {
                "name": name,
                "title": game.TITLE
            }
            for name, game in ENGINE_PACKAGES.items()
        ]
    })


@app.route("/game", methods=["POST"])
async def create_game(request):
    args = request.form

    user = args.get("user")
    if user is None:
        return json({
            "status": "error",
            "result": "no user supplied"
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
    game = engine.Game()
    games_by_gameid[game_id] = game
    games_by_user[user] = game

    return json({
        "status": "ok",
        "result": {
            "game-id": str(game_id)
        }
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, auto_reload=True)

