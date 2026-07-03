from flask import Blueprint, current_app, jsonify


docs_bp = Blueprint('docs', __name__)


ENDPOINT_DOCS = {
    '/api/health': ('Health', 'Check API health.'),
    '/api/auth/send-otp': ('Auth', 'Send a WhatsApp OTP.'),
    '/api/auth/verify': ('Auth', 'Verify an OTP and return a bearer token.'),
    '/api/auth/register': ('Auth', 'Register a user account.'),
    '/api/auth/login': ('Auth', 'Login with username/email and password.'),
    '/api/auth/me': ('Auth', 'Return the current authenticated user.'),
    '/api/bookings/availability': ('Bookings', 'Check court availability for a date.'),
    '/api/bookings': ('Bookings', 'List or create bookings.'),
    '/api/bookings/{booking_id}': ('Bookings', 'Update or delete a booking.'),
    '/api/bookings/{booking_id}/rsvp': ('Bookings', 'Update current user attendance for a booking.'),
    '/api/bookings/{booking_id}/family-attendance': ('Bookings', 'Update family attendance for a booking.'),
    '/api/bookings/{booking_id}/participants': ('Bookings', 'Add an admin-managed participant.'),
    '/api/bookings/{booking_id}/participants/{participant_id}': ('Bookings', 'Update or remove a booking participant.'),
    '/api/bookings/{booking_id}/invoice': ('Invoices', 'Generate a booking invoice.'),
    '/api/bookings/{booking_id}/settle': ('Invoices', 'Mark a booking invoice as settled.'),
    '/api/invoices/monthly': ('Invoices', 'Get the current user monthly invoice summary.'),
    '/api/misc-costs': ('Split Costs', 'List or create shared costs.'),
    '/api/misc-costs/{cost_id}': ('Split Costs', 'Update or delete a shared cost.'),
    '/api/family-members': ('Members', 'List or add current user family members.'),
    '/api/family-members/{member_id}': ('Members', 'Delete a current user family member.'),
    '/api/play-availability': ('Availability', 'List or update play availability.'),
    '/api/admin/users': ('Admin', 'List or create users.'),
    '/api/admin/users/{user_id}': ('Admin', 'Update or delete a user.'),
    '/api/admin/family-members': ('Admin', 'Create a family member for a user.'),
    '/api/admin/family-members/{member_id}': ('Admin', 'Update or delete a family member.'),
    '/api/admin/courts': ('Admin Courts', 'List or create courts.'),
    '/api/admin/courts/{court_id}': ('Admin Courts', 'Update or soft-delete a court.'),
    '/api/admin/invoices/monthly': ('Admin Invoices', 'List monthly invoice summaries for all users.'),
    '/api/admin/whatsapp-groups': ('WhatsApp', 'List WhatsApp groups visible to the paired bot.'),
    '/api/admin/whatsapp-notifications': ('WhatsApp', 'List WhatsApp notification settings and recent logs.'),
    '/api/admin/whatsapp-notifications/{setting_id}': ('WhatsApp', 'Update a WhatsApp notification setting.'),
    '/api/admin/whatsapp-notifications/{setting_id}/test': ('WhatsApp', 'Send a test WhatsApp notification.'),
}


def _openapi_path(rule):
    path = rule.rule
    for argument in rule.arguments:
        path = path.replace(f'<int:{argument}>', f'{{{argument}}}')
        path = path.replace(f'<{argument}>', f'{{{argument}}}')
    return path


def _parameter_docs(rule):
    params = []
    for argument in sorted(rule.arguments):
        params.append({
            'name': argument,
            'in': 'path',
            'required': True,
            'schema': {'type': 'integer' if f'<int:{argument}>' in rule.rule else 'string'},
        })
    return params


def _request_body(method):
    if method not in {'POST', 'PUT', 'PATCH'}:
        return None
    return {
        'required': False,
        'content': {
            'application/json': {
                'schema': {'type': 'object', 'additionalProperties': True}
            }
        },
    }


def build_openapi_spec():
    paths = {}
    for rule in sorted(current_app.url_map.iter_rules(), key=lambda item: item.rule):
        if not rule.rule.startswith('/api') or rule.endpoint == 'static':
            continue
        path = _openapi_path(rule)
        tag, summary = ENDPOINT_DOCS.get(path, ('API', rule.endpoint.replace('.', ' ')))
        paths.setdefault(path, {})
        for method in sorted(rule.methods - {'HEAD', 'OPTIONS'}):
            operation = {
                'tags': [tag],
                'summary': summary,
                'operationId': f"{method.lower()}_{rule.endpoint.replace('.', '_')}",
                'parameters': _parameter_docs(rule),
                'responses': {
                    '200': {
                        'description': 'OK',
                        'content': {
                            'application/json': {
                                'schema': {'type': 'object', 'additionalProperties': True}
                            }
                        },
                    },
                    '400': {'description': 'Bad request'},
                    '401': {'description': 'Missing or invalid authorization'},
                    '403': {'description': 'Admin access required'},
                    '404': {'description': 'Not found'},
                },
            }
            body = _request_body(method)
            if body:
                operation['requestBody'] = body
            if path.startswith('/api/') and not path.startswith('/api/auth/login') and path != '/api/health':
                operation['security'] = [{'bearerAuth': []}]
            paths[path][method.lower()] = operation

    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'Nieuwegein Badminton API',
            'version': '1.0.0',
            'description': 'API documentation for auth, bookings, availability, invoices, admin management, and WhatsApp notifications.',
        },
        'servers': [{'url': '/'}],
        'components': {
            'securitySchemes': {
                'bearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'JWT',
                }
            }
        },
        'paths': paths,
    }


@docs_bp.route('/openapi.json')
@docs_bp.route('/swagger.json')
def openapi_json():
    return jsonify(build_openapi_spec())


@docs_bp.route('/docs')
@docs_bp.route('/swagger')
@docs_bp.route('/swagger/')
def swagger_ui():
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Nieuwegein Badminton API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
      body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #0f172a; }
      .fallback { max-width: 1120px; margin: 0 auto; padding: 24px; }
      .top { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid #e2e8f0; padding-bottom: 16px; }
      .top h1 { margin: 0; font-size: 24px; }
      .top a { color: #047857; font-weight: 700; text-decoration: none; }
      .hint { color: #64748b; margin: 8px 0 0; }
      .endpoint { border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 12px; overflow: hidden; background: #fff; }
      .endpoint summary { cursor: pointer; display: flex; gap: 10px; align-items: center; padding: 12px 14px; font-weight: 700; }
      .method { min-width: 64px; border-radius: 6px; padding: 3px 8px; text-align: center; color: #fff; font-size: 12px; }
      .get { background: #2563eb; } .post { background: #059669; } .put { background: #d97706; } .delete { background: #dc2626; }
      .details { padding: 0 14px 14px 88px; color: #475569; }
      #swagger-ui:empty { display: none; }
    </style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <div id="fallback" class="fallback">
      <div class="top">
        <div>
          <h1>Nieuwegein Badminton API</h1>
          <p class="hint">OpenAPI documentation. Interactive Swagger UI loads when CDN assets are available.</p>
        </div>
        <a href="/api/openapi.json">Open JSON spec</a>
      </div>
      <div id="endpoint-list"></div>
    </div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      fetch('/api/openapi.json')
        .then((response) => response.json())
        .then((spec) => {
          const target = document.getElementById('endpoint-list')
          const rows = []
          Object.entries(spec.paths || {}).forEach(([path, methods]) => {
            Object.entries(methods || {}).forEach(([method, operation]) => {
              rows.push({ path, method, operation })
            })
          })
          target.innerHTML = rows.map(({ path, method, operation }) => `
            <details class="endpoint">
              <summary><span class="method ${method}">${method.toUpperCase()}</span><span>${path}</span></summary>
              <div class="details">
                <div>${operation.summary || ''}</div>
                <div>Tags: ${(operation.tags || []).join(', ') || 'API'}</div>
              </div>
            </details>
          `).join('')
        })

      if (window.SwaggerUIBundle) {
        window.ui = SwaggerUIBundle({
          url: '/api/openapi.json',
          dom_id: '#swagger-ui',
          deepLinking: true,
          presets: [SwaggerUIBundle.presets.apis],
          layout: 'BaseLayout',
          onComplete: function () {
            const fallback = document.getElementById('fallback')
            if (fallback) fallback.style.display = 'none'
          }
        })
      }
    </script>
  </body>
</html>"""
