from django.shortcuts import render
from django.http import JsonResponse
from django.urls import get_resolver

def home(request):
    return JsonResponse({
        "message": "Bienvenido a Djidji API 🚀",
        "status": "OK",
        "version": "1.0.0",
        "author": "Created by the Djidji Company, Malabo, Guinea Ecuatorial",
        "documentation_swagger": "/api/core/docs/swagger/",
        "documentation_redoc": "/api/core/docs/redoc/",
        "api_info": "/api/core/info/"
    })

def api_endpoints(request):
    resolver = get_resolver()
    urls = []

    def list_urls(patterns, prefix=''):
        for pattern in patterns:
            if hasattr(pattern, 'url_patterns'):
                list_urls(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                urls.append(prefix + str(pattern.pattern))

    list_urls(resolver.url_patterns)
    return JsonResponse({
        "status": "OK",
        "version": "1.0.0",
        "total_endpoints": len(urls),
        "endpoints": urls
    })
