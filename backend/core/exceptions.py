"""Custom DRF exception handler producing consistent error payloads."""

from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        detail = response.data
        if isinstance(detail, dict) and 'detail' in detail:
            message = detail['detail']
        elif isinstance(detail, dict):
            message = '; '.join(f'{key}: {value}' for key, value in detail.items())
        elif isinstance(detail, list):
            message = '; '.join(str(item) for item in detail)
        else:
            message = str(detail)
        response.data = {'error': str(message), 'status_code': response.status_code}
    return response
