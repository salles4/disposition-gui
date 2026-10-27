import logging
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

# Suppress Werkzeug HTTP polling logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__, static_folder='dist/assets', template_folder='dist')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

