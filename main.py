from flask import Flask, jsonify
from fastapi import FastAPI
from starlette.middleware.wsgi import WSGIMiddleware
import gradio as gr
import uvicorn

from app.config import Config
from app.db import (
    init_db,
    get_latest_profile,
    get_latest_emotion,
    list_recent_messages,
    list_recent_diary_sessions,
)
from app.services.state_snapshot import list_state_snapshots
from app.ui.gradio_app import CSS, build_gradio_app


def create_app() -> Flask:
    """Flask API 服务，仅提供 /api 下的接口。"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = Config.SECRET_KEY

    @app.get('/health')
    def health():
        return jsonify({'status': 'ok'})

    @app.get('/profile/<int:user_id>')
    def profile(user_id: int):
        return jsonify(get_latest_profile(user_id) or {})

    @app.get('/emotion/<int:user_id>')
    def emotion(user_id: int):
        return jsonify(get_latest_emotion(user_id) or {})

    @app.get('/messages/<int:user_id>')
    def messages(user_id: int):
        return jsonify(list_recent_messages(user_id, limit=20))

    @app.get('/diary/<int:user_id>')
    def diary(user_id: int):
        return jsonify(list_recent_diary_sessions(user_id, limit=10))

    @app.get('/state/<int:user_id>')
    def state(user_id: int):
        return jsonify(list_state_snapshots(user_id))

    @app.get('/state')
    def state_all():
        return jsonify(list_state_snapshots())

    return app


def main() -> None:
    init_db()
    flask_app = create_app()
    gradio_app = build_gradio_app()

    # FastAPI 作为宿主，挂载 Gradio 与 Flask（WSGI）
    api_host = FastAPI()
    api_host.mount('/api', WSGIMiddleware(flask_app))
    app = gr.mount_gradio_app(api_host, gradio_app, path='/', css=CSS)

    # 直接运行实例，避免 reload 导致启动失败
    uvicorn.run(app, host='0.0.0.0', port=Config.PORT, log_level='info', reload=False)


if __name__ == '__main__':
    main()
