# check_deploy.py
import os
import sys
import django
from django.conf import settings
from django.core.management import execute_from_command_line

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djidji1.settings')

try:
    django.setup()
except Exception as e:
    print(f"❌ Error configurando Django: {e}")
    sys.exit(1)

def check_deploy_readiness():
    issues = []
    warnings = []
    
    print("🔍 Verificando preparación para deploy...\n")
    
    # 1. Variables de entorno críticas
    critical_vars = ['SECRET_KEY', 'DATABASE_URL', 'ALLOWED_HOSTS']
    
    for var in critical_vars:
        env_value = os.getenv(var)
        setting_value = getattr(settings, var, None)
        
        if not env_value and not setting_value:
            issues.append(f"❌ Variable crítica faltante: {var}")
        else:
            print(f"✅ {var}: {'Configurado' if env_value else 'Usando valor de settings'}")
    
    # 2. Configuración de seguridad básica
    security_checks = [
        ('DEBUG', False, 'DEBUG debe ser False en producción'),
        ('CSRF_COOKIE_SECURE', True, 'CSRF_COOKIE_SECURE debe ser True'),
        ('SESSION_COOKIE_SECURE', True, 'SESSION_COOKIE_SECURE debe ser True'),
    ]
    
    for setting, expected, message in security_checks:
        actual = getattr(settings, setting, None)
        if actual != expected:
            if setting == 'DEBUG' and actual:
                issues.append(f"❌ {message}")
            else:
                warnings.append(f"⚠️  {message} (actual: {actual})")
        else:
            print(f"✅ {setting}: {actual}")
    
    # 3. Base de datos
    try:
        from django.db import connection
        connection.ensure_connection()
        print("✅ Conexión a BD exitosa")
    except Exception as e:
        issues.append(f"❌ Error conectando a BD: {e}")
    
    # 4. Archivos estáticos
    if not hasattr(settings, 'STATIC_ROOT') or not settings.STATIC_ROOT:
        issues.append("❌ STATIC_ROOT no configurado")
    else:
        print(f"✅ STATIC_ROOT: {settings.STATIC_ROOT}")
    
    # 5. Verificar aplicaciones instaladas
    required_apps = [
        'django.contrib.staticfiles',
        'corsheaders', 
        'rest_framework',
        'whitenoise.runserver_nostatic'
    ]
    
    for app in required_apps:
        if app not in settings.INSTALLED_APPS:
            warnings.append(f"⚠️  App recomendada no instalada: {app}")
        else:
            print(f"✅ App instalada: {app}")
    
    # 6. Verificar middleware
    required_middleware = [
        'whitenoise.middleware.WhiteNoiseMiddleware',
        'corsheaders.middleware.CorsMiddleware'
    ]
    
    for middleware in required_middleware:
        if middleware not in settings.MIDDLEWARE:
            warnings.append(f"⚠️  Middleware recomendado no instalado: {middleware}")
        else:
            print(f"✅ Middleware instalado: {middleware}")
    
    return issues, warnings

if __name__ == "__main__":
    issues, warnings = check_deploy_readiness()
    
    print("\n" + "="*50)
    
    if warnings:
        print("\nAdvertencias:")
        for warning in warnings:
            print(f"  {warning}")
    
    if issues:
        print("\n❌ Problemas críticos encontrados:")
        for issue in issues:
            print(f"  {issue}")
        print(f"\nTotal: {len(issues)} problema(s) crítico(s)")
        sys.exit(1)
    else:
        print("\n🎉 ¡No se encontraron problemas críticos!")
        if warnings:
            print(f"Tienes {len(warnings)} advertencia(s) para revisar")
        else:
            print("¡Todo listo para deploy!")