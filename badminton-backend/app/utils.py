import os
import logging
import requests
from flask import current_app


def _whatsapp_bot_recipient(to_phone):
    recipient = (to_phone or '').strip()
    if '@' in recipient:
        return recipient
    digits = ''.join(character for character in recipient if character.isdigit())
    return f'{digits}@c.us' if digits else recipient


def send_whatsapp_message(to_phone, message):
    """Send through the linked WhatsApp bot, then Twilio if configured, else log it.

    Environment variables used (optional): WHATSAPP_BOT_URL, WHATSAPP_BOT_TOKEN,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, WHATSAPP_FROM.
    """
    bot_url = (os.environ.get('WHATSAPP_BOT_URL') or '').strip()
    if bot_url:
        headers = {}
        bot_token = os.environ.get('WHATSAPP_BOT_TOKEN')
        if bot_token:
            headers['X-Bot-Token'] = bot_token
        try:
            response = requests.post(
                f"{bot_url.rstrip('/')}/send",
                json={'message': message, 'recipient': _whatsapp_bot_recipient(to_phone)},
                headers=headers,
                timeout=5,
            )
            if response.ok:
                return {'status': 'sent', 'provider': 'whatsapp_bot'}
            current_app.logger.warning('Linked WhatsApp bot failed to send: %s', response.text[:1000])
        except Exception:
            current_app.logger.exception('Failed to send through linked WhatsApp bot')

    sid = os.environ.get('TWILIO_ACCOUNT_SID')
    token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('WHATSAPP_FROM')

    if sid and token and from_number:
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            msg = client.messages.create(body=message, from_=f'whatsapp:{from_number}', to=f'whatsapp:{to_phone}')
            return {'status': 'sent', 'sid': msg.sid}
        except Exception as e:
            current_app.logger.exception('Failed to send WhatsApp via Twilio')
            return {'status': 'failed', 'error': str(e)}
    else:
        # fallback: log message so developer can see it
        logging.getLogger('whatsapp_fallback').info('WhatsApp to %s: %s', to_phone, message)
        return {'status': 'logged'}
