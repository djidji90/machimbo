import django_filters as filters
from ventas.models import Producto
from django.db import models  # Para Q(...)
from rest_framework.pagination import PageNumberPagination  # Para CustomPagination
from rest_framework.response import Response  # Para retornar la respuesta paginada


class ProductoFilter(filters.FilterSet):
    precio_min = filters.NumberFilter(field_name="precio", lookup_expr='gte')
    precio_max = filters.NumberFilter(field_name="precio", lookup_expr='lte')
    categoria = filters.CharFilter(field_name='categoria__nombre', lookup_expr='iexact')
    proveedor = filters.CharFilter(field_name='proveedor__nombre', lookup_expr='icontains')
    disponible = filters.BooleanFilter(field_name='disponible')
    destacado = filters.BooleanFilter(field_name='destacado')
    busqueda = filters.CharFilter(method='filtrar_busqueda')

    class Meta:
        model = Producto
        fields = ['categoria', 'destacado', 'disponible', 'precio_min', 'precio_max', 'proveedor']

    def filtrar_busqueda(self, queryset, name, value):
        return queryset.filter(
            models.Q(nombre__icontains=value) |
            models.Q(descripcion__icontains=value) |
            models.Q(categoria__nombre__icontains=value)
        )

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'results': data
        })