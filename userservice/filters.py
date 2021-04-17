from django_filters import rest_framework as filters
from .models import Tudo, User


class TudoSearchFilter(filters.FilterSet):
    purpose = filters.CharFilter(
        field_name="goal_name", lookup_expr='icontains')
    category = filters.CharFilter(
        field_name="category__category", lookup_expr='icontains')
    date = filters.DateFilter(
        field_name="created_at", lookup_expr='date__lte')

    class Meta:
        model = Tudo
        fields = ['goal_name', 'category', 'created_at']
