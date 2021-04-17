from django.conf.urls import url
from django.urls import include
from rest_framework.routers import DefaultRouter

goal_router = DefaultRouter(trailing_slash=False)


goal_router.register(r'goal/contribute', TudoContributionViewSet, basename='user-goal')
goal_router.register(r'goal/trending', TrendingTudoViewset, basename='trending-goal')
goal_router.register(r'goal/withdraw', WithdrawTudoViewSet, basename='withdraw-goal')
goal_router.register(r'goal/search', PublicSearchTudoViewset, basename='search-goal')
goal_router.register(r'goal/transactions', TudoTransactionsViewset,
                     basename='goal-transactions')
goal_router.register(r'goal/get-contribution',
                     GetTudoContributionViewset, basename='user-goal')
goal_router.register(r'goal/top-up', TopUpTudoViewset, basename='user-goal')
goal_router.register(r'goal/like', LikeTudoViewset, basename='user-goal')
goal_router.register(r'goal/follow', FollowTudoViewset, basename='user-goal')
goal_router.register(r'goal/comment', CommentTudoViewset, basename='user-goal')
goal_router.register(r'goal/media', TudoMediaViewset, basename='goal-media')
goal_router.register(r'goal/shared-goal', SharedTudoViewset, basename='shared-goal')
goal_router.register(r'goal', TudoViewset, basename='user-goal')
goal_router.register(r'shared-goal', SharedTudoViewset, basename='shared-goal')
goal_router.register(r'my-goal-feed', TudoFeedViewset, basename='my-goal-feed')


urlpatters = [url(r'', include(goal_router.urls)), ]
