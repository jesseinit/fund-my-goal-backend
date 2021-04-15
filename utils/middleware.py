import uuid

from sentry_sdk import capture_exception
from django.utils import timezone
from utils.enums import UserActionStatus
from utils.helpers import retrieve_from_redis, save_in_redis


class LoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        payload = request.body
        response = self.get_response(request)

        # Todo: Add some sort of logging service at this point

        return response

    def process_exception(self, request, exception):
        capture_exception(exception)
        from rest_framework.response import Response
        from rest_framework.renderers import JSONRenderer

        resp = Response(data={"error": exception.args[0],
                              "status": 500}, status=500)

        # # Todo - Updgrade to Handling All Errors This Way.
        # # resp = Response(data={"error": exception.args[0]['error'],
        # # "status": exception.args[0]['status']}, status=exception.args[0]['status'])

        resp.accepted_renderer = JSONRenderer()
        resp.accepted_media_type = "application/json"
        resp.renderer_context = {}
        return resp
        # return None
