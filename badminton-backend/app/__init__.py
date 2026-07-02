from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from itsdangerous import URLSafeTimedSerializer
import os
import redis as _redis
from passlib.hash import pbkdf2_sha256

db = SQLAlchemy()
limiter = Limiter(key_func=get_remote_address)


def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY") or "dev-secret"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    limiter.init_app(app)

    if not app.config.get('TESTING') and os.environ.get('FLASK_ENV', '').lower() != 'development':
        Talisman(app)
    else:
        app.config['TALISMAN_ENABLED'] = False

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
    from app.bookings import bookings_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(bookings_bp, url_prefix='/api')

    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    with app.app_context():
        db.create_all()
        from sqlalchemy import inspect
        from app.models import User
        inspector = inspect(db.engine)
        user_columns = {col['name'] for col in inspector.get_columns('users')}
        if 'email' not in user_columns:
            db.session.execute(db.text('ALTER TABLE users ADD COLUMN email VARCHAR(255)'))
        if 'password_hash' not in user_columns:
            db.session.execute(db.text('ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)'))
        if 'whatsapp_number' not in user_columns:
            db.session.execute(db.text('ALTER TABLE users ADD COLUMN whatsapp_number VARCHAR(64)'))
        if 'role' not in user_columns:
            db.session.execute(db.text("ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'member'"))
        if 'is_club_member' not in user_columns:
            db.session.execute(db.text('ALTER TABLE users ADD COLUMN is_club_member BOOLEAN DEFAULT FALSE'))
        family_columns = {col['name'] for col in inspector.get_columns('family_members')}
        if 'is_club_member' not in family_columns:
            db.session.execute(db.text('ALTER TABLE family_members ADD COLUMN is_club_member BOOLEAN DEFAULT FALSE'))
        court_columns = {col['name'] for col in inspector.get_columns('courts')}
        if 'location' not in court_columns:
            db.session.execute(db.text('ALTER TABLE courts ADD COLUMN location VARCHAR(255)'))
        if 'description' not in court_columns:
            db.session.execute(db.text('ALTER TABLE courts ADD COLUMN description TEXT'))
        participant_columns = {col['name'] for col in inspector.get_columns('booking_participants')}
        if 'name' not in participant_columns:
            db.session.execute(db.text('ALTER TABLE booking_participants ADD COLUMN name VARCHAR(128)'))
        if 'status' not in participant_columns:
            db.session.execute(db.text("ALTER TABLE booking_participants ADD COLUMN status VARCHAR(32) DEFAULT 'tentative'"))
        if 'is_adhoc' not in participant_columns:
            db.session.execute(db.text('ALTER TABLE booking_participants ADD COLUMN is_adhoc BOOLEAN DEFAULT FALSE'))
        misc_cost_columns = {col['name'] for col in inspector.get_columns('misc_costs')}
        if 'purchase_date' not in misc_cost_columns:
            db.session.execute(db.text('ALTER TABLE misc_costs ADD COLUMN purchase_date VARCHAR(10)'))
        play_vote_columns = {col['name'] for col in inspector.get_columns('play_availability_votes')}
        if 'status' not in play_vote_columns:
            db.session.execute(db.text("ALTER TABLE play_availability_votes ADD COLUMN status VARCHAR(32) DEFAULT 'not_available'"))
            db.session.execute(db.text("UPDATE play_availability_votes SET status = CASE WHEN available THEN 'available' ELSE 'not_available' END"))
        if 'attendee_details' not in play_vote_columns:
            db.session.execute(db.text('ALTER TABLE play_availability_votes ADD COLUMN attendee_details TEXT'))
        play_vote_user_id = next((col for col in inspector.get_columns('play_availability_votes') if col['name'] == 'user_id'), None)
        if play_vote_user_id and not play_vote_user_id.get('nullable') and db.engine.dialect.name != 'sqlite':
            db.session.execute(db.text('ALTER TABLE play_availability_votes ALTER COLUMN user_id DROP NOT NULL'))
        db.session.commit()
        admin_user = User.query.filter_by(phone='+10000000000').first()
        if not admin_user:
            admin_user = User(
                phone='+10000000000',
            )
            db.session.add(admin_user)
        admin_user.email = 'admin@example.com'
        admin_user.password_hash = pbkdf2_sha256.hash('admin123')
        admin_user.name = 'admin'
        admin_user.role = 'admin'
        admin_user.is_club_member = True
        db.session.commit()

    return app
