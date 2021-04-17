from django.conf.urls import url
from django.urls import include
from rest_framework.routers import DefaultRouter

payment_router = DefaultRouter(trailing_slash=False)
""" WEBHOOK ENDPOINTS """
router.register(r'paystack/transactions', TransactionWebHook, basename='webhook')
# Todo - Reimplement Integration(separate concerns)
# router.register(r'webhook/integrations/paystack', PaystackWebhookViewset, basename='paystack-webhook') # noqa
# router.register(r'webhook/integrations/flutterwave', FlutterwaveWebhookViewset, basename='flutterwave-webhook') # noqa

urlpatters = [url(r'', include(payment_router.urls)), ]
