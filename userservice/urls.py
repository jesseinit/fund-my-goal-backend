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
                               RegisterUserViewSet,
                               SearchUsers, SharedTudoViewset, SyncedContacts,
                               TopUpTudoViewset, TransactionHistoryViewSet,
                               TransactionWebHook, TrendingTudoViewset,
                               TudoCollectionViewset, TudoContributionViewSet,
                               TudoFeedViewset, TudoMediaViewset,
                               TudoTransactionsViewset, TudoViewset,
                               VerificationViewSet, WithdrawTudoViewSet)

router = DefaultRouter(trailing_slash=False)
router.register(r'user/register', RegisterUserViewSet, basename='user')
router.register(r'user/login', LoginUserViewSet, basename='user')
router.register(r'bank-details', BankDetailsViewSet, basename='user-bank')
router.register(r'bank-list', BankListView, basename='user-bank-list')
router.register(r'card-details', DebitCardViewSet, basename='user-cards')
router.register(r'user/transaction-history', TransactionHistoryViewSet,
                basename='tudo-transaction-history')


urlpatterns = [
    url(r'', include(router.urls)),
    path('password-reset-link', GetPasswordResetLinkView.as_view()),
    path('password-reset-change/<uidb64>/<token>',
         PasswordResetView.as_view(), name='password_reset'),
    path('user-profile', ProfileView.as_view(), name='user-profile'),
    path('logout', LogoutView.as_view())
]
