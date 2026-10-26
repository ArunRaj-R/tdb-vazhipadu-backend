from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Standardized JSON error handler ensuring all error responses adhere to:
    {
        "error": {
            "code": "<ERROR_CODE>",
            "message": "<Human readable summary>",
            "details": <Field-specific errors or extra info>
        }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        status_code = response.status_code
        if status_code == status.HTTP_400_BAD_REQUEST:
            error_code = 'VALIDATION_ERROR'
        elif status_code == status.HTTP_404_NOT_FOUND:
            error_code = 'NOT_FOUND'
        elif status_code == status.HTTP_403_FORBIDDEN:
            error_code = 'FORBIDDEN'
        elif status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = 'UNAUTHORIZED'
        else:
            error_code = getattr(exc, 'default_code', 'ERROR').upper()

        details = response.data
        message = "An error occurred."

        if isinstance(details, dict):
            if 'detail' in details:
                message = str(details['detail'])
            else:
                message = "Invalid input provided."
        elif isinstance(details, list):
            message = "; ".join(str(item) for item in details)

        response.data = {
            "error": {
                "code": error_code,
                "message": message,
                "details": details,
            }
        }
    else:
        response = Response(
            {
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred.",
                    "details": str(exc),
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
