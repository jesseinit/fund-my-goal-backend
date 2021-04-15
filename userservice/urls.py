from django.conf.urls import url
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from userservice.views import (ApplicationSupportView, BankDetailsViewSet,
                               BankListView, CommentTudoViewset,
                               DebitCardViewSet, FollowTudoViewset,
                               GetPasswordResetLinkView,
                               GetTudoContributionViewset, KYCViewSet,
                               LikeTudoViewset, LoginUserViewSet, LogoutView,
                               NextOfKinViewSet, NotificationViewSet,
                               PasswordResetView, ProfileView,
                               PublicSearchTudoViewset, ReferralViewset,
                               RegisterBusinessViewSet, RegisterUserViewSet,
                               SearchUsers, SharedTudoViewset, SyncedContacts,
                               TopUpTudoViewset, TransactionHistoryViewSet,
                               TransactionWebHook, TrendingTudoViewset,
                               TudoCollectionViewset, TudoContributionViewSet,
                               TudoFeedViewset, TudoMediaViewset,
                               TudoTransactionsViewset, TudoViewset,
                               VerificationViewSet, WithdrawTudoViewSet)

router = DefaultRouter(trailing_slash=False)
router.register(r'register', RegisterUserViewSet, basename='user')
router.register(r'register-business', RegisterBusinessViewSet, basename='user')
router.register(r'login', LoginUserViewSet, basename='user')
router.register(r'user/referrals', ReferralViewset, basename='user-referral')
router.register(r'user', VerificationViewSet, basename='user')
router.register(r'user-kyc', KYCViewSet, basename='user-kyc')
router.register(r'synced-contacts', SyncedContacts, basename='synced-contacts')
router.register(r'search-users', SearchUsers, basename='search-users')
router.register(r'next-of-kin', NextOfKinViewSet, basename='user')
router.register(r'bank-details', BankDetailsViewSet, basename='user-bank')
router.register(r'bank-list', BankListView, basename='user-bank-list')
router.register(r'card-details', DebitCardViewSet, basename='user-cards')
router.register(r'user-notification', NotificationViewSet, basename='user-notification')
router.register(r'transaction-history', TransactionHistoryViewSet,
                basename='tudo-transaction-history')


""" PERSONAL/BUSINESS TUDO ENDPOINTS """
router.register(r'tudo/contribute', TudoContributionViewSet, basename='user-tudo')
router.register(r'tudo/collection', TudoCollectionViewset, basename='user-tudo')
router.register(r'tudo/trending', TrendingTudoViewset, basename='trending-tudo')
router.register(r'tudo/withdraw', WithdrawTudoViewSet, basename='withdraw-tudo')
router.register(r'tudo/search', PublicSearchTudoViewset, basename='search-tudo')
router.register(r'tudo/transactions', TudoTransactionsViewset,
                basename='tudo-transactions')
router.register(r'tudo/get-contribution',
                GetTudoContributionViewset, basename='user-tudo')
router.register(r'tudo/top-up', TopUpTudoViewset, basename='user-tudo')
router.register(r'tudo/like', LikeTudoViewset, basename='user-tudo')
router.register(r'tudo/follow', FollowTudoViewset, basename='user-tudo')
router.register(r'tudo/comment', CommentTudoViewset, basename='user-tudo')
router.register(r'tudo/media', TudoMediaViewset, basename='tudo-media')
router.register(r'tudo/shared-tudo', SharedTudoViewset, basename='shared-tudo')
router.register(r'tudo', TudoViewset, basename='user-tudo')
router.register(r'shared-tudo', SharedTudoViewset, basename='shared-tudo')
router.register(r'my-tudo-feed', TudoFeedViewset, basename='my-tudo-feed')


""" WEBHOOK ENDPOINTS """
router.register(r'paystack/transactions', TransactionWebHook, basename='webhook')
# Todo - Reimplement Integration(separate concerns)
# router.register(r'webhook/integrations/paystack', PaystackWebhookViewset, basename='paystack-webhook') # noqa
# router.register(r'webhook/integrations/flutterwave', FlutterwaveWebhookViewset, basename='flutterwave-webhook') # noqa

""" APPLICATION SUPPORT """
router.register(r'application-support', ApplicationSupportView,
                basename='application-support')


urlpatterns = [
    url(r'', include(router.urls)),
    path('password-reset-link', GetPasswordResetLinkView.as_view()),
    path('password-reset-change/<uidb64>/<token>',
         PasswordResetView.as_view(), name='password_reset'),
    path('user-profile', ProfileView.as_view(), name='user-profile'),
    path('logout', LogoutView.as_view())
]
