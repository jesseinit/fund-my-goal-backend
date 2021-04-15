from django.apps import AppConfig


class UserserviceConfig(AppConfig):
    name = 'userservice'

    def ready(self):
        import userservice.signals
