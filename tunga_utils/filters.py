import django_filters


class GenericDateFilterSet(django_filters.FilterSet):
    min_date = django_filters.IsoDateTimeFilter(name='created_at', lookup_type='gte')
    max_date = django_filters.IsoDateTimeFilter(name='created_at', lookup_type='lte')