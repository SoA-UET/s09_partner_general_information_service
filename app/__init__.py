"""
WARNING: Change this file if the
service does not need HTTP API
or WebSocket features.
"""

SERVICE_NAME = "Telcenter Consultation Service" # change this



from flask import Flask, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
import os 

app = Flask(__name__)

app.url_map.strict_slashes = False

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

socketio = SocketIO(app, cors_allowed_origins=CORS_ORIGINS, async_mode='threading')

CORS(
    app, 
    origins=CORS_ORIGINS,
    supports_credentials=True,
    allow_headers=["Content-Type", "Accept", "Authorization", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['JSON_SORT_KEYS'] = False

with app.app_context():
    from .controllers import register_api_controllers
    register_api_controllers(app, socketio)

    from .utils.auth import init_auth
    init_auth()

    @app.get('/')
    def home():
        return f"""
        <html><head><title>{SERVICE_NAME}</title></head><body>
        <h1>Welcome to the {SERVICE_NAME}!</h1>
        <a href={url_for("get_api_versions")}>Here is the API documentation.</a>
        </body></html>
        """

print(app.url_map)
