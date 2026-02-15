from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from itsdangerous import URLSafeTimedSerializer
import os
import redis as _redis

db = SQLAlchemy()
limiter = Limiter(key_func=get_remote_address)


def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY") or "dev-secret"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    limiter.init_app(app)

    Talisman(app)

    # Initialize token serializer
    app.token_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    # Initialize Redis if available, else fall back to in-memory store
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        try:
            app.redis = _redis.from_url(redis_url)
        except Exception:
            app.redis = None
    else:
        app.redis = None
        # simple in-memory OTP store: {phone: (hashed_otp, expires_at)}
        app._otp_store = {}

    # Mock auth mode for development: set AUTH_MOCK=1|true to enable
    app.config['AUTH_MOCK'] = os.environ.get('AUTH_MOCK', 'false').lower() in ('1', 'true', 'yes')

    # JWT configuration
    app.config['JWT_SECRET'] = os.environ.get('JWT_SECRET') or app.config['SECRET_KEY']
    try:
        app.config['JWT_EXP_SECONDS'] = int(os.environ.get('JWT_EXP_SECONDS', '3600'))
    except Exception:
        app.config['JWT_EXP_SECONDS'] = 3600

    from app.auth import auth_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    return app
