import logging
import os
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

# Suppress Werkzeug HTTP polling logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Output of "npm run build". It sits at the project root, one level above this file.
DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dist')

app = Flask(__name__, static_folder=os.path.join(DIST_DIR, 'assets'), static_url_path='/assets', template_folder=DIST_DIR)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

