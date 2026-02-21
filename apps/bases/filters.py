
import django_filters as filters


class BaseFilterOrderBy(filters.FilterSet):
    """
        Define a default filter-class and
        will use everywhere where required order by
    """

    order_by = filters.CharFilter(method='order_by_filter')

    def order_by_filter(self, qs, name, value) -> object:
        try:
            if value.startswith("-"):
                field = [f.name for f in self._meta.model._meta.fields if f.name.lower() == value[1:]][0]
                field = f"-{field}"
            else:
                field = [f.name for f in self._meta.model._meta.fields if f.name.lower() == value][0]
            qs = qs.order_by(field)
        except Exception:
            try:
                qs = qs.order_by(value)
            except Exception:
                pass
        return qs
