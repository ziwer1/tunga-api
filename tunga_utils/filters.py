import django_filters


class GenericDateFilterSet(django_filters.FilterSet):
    min_date = django_filters.IsoDateTimeFilter(name='created_at', lookup_expr='gte')
    max_date = django_filters.IsoDateTimeFilter(name='created_at', lookup_expr='lte')


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass
