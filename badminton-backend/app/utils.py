import os
import logging
from flask import current_app

def send_whatsapp_message(to_phone, message):
    """Send a WhatsApp message using Twilio if configured, else log it.

    Environment variables used (optional): TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, WHATSAPP_FROM
    """
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
