from flask import Blueprint, request, current_app, jsonify
import os
from .models import User
from . import db
from .utils import send_whatsapp_message
from passlib.hash import pbkdf2_sha256
import jwt
from datetime import datetime, timedelta
import random
import time

auth_bp = Blueprint('auth', __name__)


def _store_otp(phone, hashed_otp, ttl=300):
    app = current_app
    if getattr(app, 'redis', None):
        app.redis.setex(f'otp:{phone}', ttl, hashed_otp)
    else:
        expires = int(time.time()) + ttl
        app._otp_store[phone] = (hashed_otp, expires)


def _get_and_pop_otp(phone):
    app = current_app
    if getattr(app, 'redis', None):
        val = app.redis.get(f'otp:{phone}')
        if val:
            app.redis.delete(f'otp:{phone}')
            return val.decode()
        return None
    else:
        rec = app._otp_store.pop(phone, None)
        if not rec:
            return None
        hashed, expires = rec
        if int(time.time()) > expires:
            return None
        return hashed


@auth_bp.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json() or {}
    phone = data.get('phone')
    if not phone:
        return jsonify({'error': 'phone required'}), 400

    otp = f"{random.randint(0, 999999):06d}"
    hashed = pbkdf2_sha256.hash(otp)
    _store_otp(phone, hashed, ttl=300)
    msg = f"Your verification code is {otp}. It expires in 5 minutes."

    # If mock mode enabled, allow only when running in development environment
    auth_mock = current_app.config.get('AUTH_MOCK', False)
    env_dev = (current_app.config.get('ENV', '').lower() == 'development') or (os.environ.get('FLASK_ENV', '').lower() == 'development')
    if auth_mock and env_dev:
        current_app.logger.info('AUTH_MOCK enabled (dev) - OTP for %s: %s', phone, otp)
        return jsonify({'status': 'otp_sent', 'mock_otp': otp})

    # If AUTH_MOCK requested but not allowed, reject
    if auth_mock and not env_dev:
        current_app.logger.warning('AUTH_MOCK requested but not allowed outside development')
        return jsonify({'error': 'mock_not_allowed'}), 403

    # production: try sending via WhatsApp (Twilio) or fallback to logging
    send_whatsapp_message(phone, msg)

    return jsonify({'status': 'otp_sent'})


@auth_bp.route('/verify', methods=['POST'])
def verify():
    data = request.get_json() or {}
    phone = data.get('phone')
    otp = data.get('otp')
    name = data.get('name')
    if not phone or not otp:
        return jsonify({'error': 'phone and otp required'}), 400

    hashed = _get_and_pop_otp(phone)
    if not hashed:
        return jsonify({'error': 'otp_invalid_or_expired'}), 400

    if not pbkdf2_sha256.verify(otp, hashed):
        return jsonify({'error': 'invalid_otp'}), 400

    # create or get user
    user = User.query.filter_by(phone=phone).first()
    if not user:
        user = User(phone=phone, name=name)
        db.session.add(user)
        db.session.commit()

    # issue JWT token
    jwt_secret = current_app.config.get('JWT_SECRET')
    exp_seconds = int(current_app.config.get('JWT_EXP_SECONDS', 3600))
    payload = {
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(seconds=exp_seconds)
    }
    token = jwt.encode(payload, jwt_secret, algorithm='HS256')

    return jsonify({'status': 'ok', 'token': token, 'user': user.to_dict()})


@auth_bp.route('/me', methods=['GET'])
def me():
    auth_header = request.headers.get('Authorization', '')
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return jsonify({'error': 'missing_authorization'}), 401
    token = parts[1]
    jwt_secret = current_app.config.get('JWT_SECRET')
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'token_expired'}), 401
    except Exception:
        return jsonify({'error': 'invalid_token'}), 401

    user_id = payload.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'user_not_found'}), 404
    return jsonify({'user': user.to_dict()})
