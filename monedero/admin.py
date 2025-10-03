from datetime import timezone
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
import json
from cryptography.fernet import Fernet, InvalidToken
from django.contrib.auth import get_user_model
from django.forms import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils.html import format_html
from django.db import transaction
from django import forms

from monedero.models import Agencia, Agente, AuditoriaAgente, AuditoriaMonedero, AuditoriaRecarga, AuditoriaRetencion, AuditoriaTransferencia, ConfiguracionSistema, DashboardAdmin, Monedero, Notificacion, Recarga, Reporte, Transaccion, TransaccionRetenida, Transferencia

User = get_user_model()

class AgenteForm(forms.ModelForm):
    pin_nuevo = forms.CharField(
        label="PIN de Operaciones",
        max_length=6,
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Ingrese un PIN de 6 dígitos (dejar en blanco para no cambiar)"
    )
    
    pin_confirmacion = forms.CharField(
        label="Confirmar PIN",
        max_length=6,
        required=False,
        widget=forms.PasswordInput(render_value=True)
    )

    class Meta:
        model = Agente
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['usuario'].disabled = True
            self.fields['agencia'].disabled = True
    
    def clean(self):
        cleaned_data = super().clean()
        pin_nuevo = cleaned_data.get('pin_nuevo')
        pin_confirmacion = cleaned_data.get('pin_confirmacion')
        
        if pin_nuevo or pin_confirmacion:
            if pin_nuevo != pin_confirmacion:
                raise ValidationError("Los PINs no coinciden")
            
            if len(pin_nuevo) != 6 or not pin_nuevo.isdigit():
                raise ValidationError("El PIN debe tener exactamente 6 dígitos numéricos")
        
        return cleaned_data

# Configuración del sistema
@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    list_display = ('limite_transferencia_diaria', 'limite_recarga_diaria', 'minimo_transferencia')
    fieldsets = (
        ('Límites de Operaciones', {
            'fields': ('limite_transferencia_diaria', 'limite_recarga_diaria', 'minimo_transferencia')
        }),
        ('Comisiones', {
            'fields': ('comision_transferencia_porcentaje', 'comision_transferencia_minima', 'comision_recarga_agente')
        }),
        ('Seguridad', {
            'fields': ('requiere_verificacion_monto', 'max_intentos_verificacion', 'max_operaciones_diarias')
        }),
        ('Configuración Celery', {
            'fields': ('tiempo_espera_procesamiento', 'reintentos_fallidos')
        }),
    )

    def has_add_permission(self, request):
        return not ConfiguracionSistema.objects.exists()

# Agencias
class AgenteInline(admin.TabularInline):
    model = Agente
    extra = 0
    fields = ('codigo_agente', 'usuario', 'activo', 'comision_acumulada', 'ultima_actividad')
    readonly_fields = ('comision_acumulada', 'ultima_actividad')
    fk_name = 'agencia'

@admin.register(Agente)
class AgenteAdmin(admin.ModelAdmin):
    form = AgenteForm
    list_display = (
        'codigo_agente', 
        'usuario_link', 
        'agencia_link', 
        'activo', 
        'fecha_registro_short',
        'ultima_actividad_short'
    )
    list_filter = ('activo', 'agencia', 'fecha_registro')
    search_fields = (
        'codigo_agente', 
        'usuario__username', 
        'usuario__first_name', 
        'usuario__last_name'
    )
    raw_id_fields = ('usuario',)
    readonly_fields = (
        'fecha_registro', 
        'ultima_actividad', 
        'comision_acumulada',
        'pin_estado'
    )
    list_select_related = ('usuario', 'agencia')
    date_hierarchy = 'fecha_registro'
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'usuario', 
                'agencia', 
                'codigo_agente', 
                'activo'
            )
        }),
        ('Seguridad', {
            'fields': (
                'pin_nuevo',
                'pin_confirmacion',
                'pin_estado'
            ),
            'classes': ('collapse',)
        }),
        ('Estadísticas', {
            'fields': (
                'comision_acumulada',
                'ultima_actividad',
                'fecha_registro'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def usuario_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.usuario.id])
        return format_html(
            '<a href="{}">{} ({})</a>', 
            url, 
            obj.usuario.get_full_name(), 
            obj.usuario.username
        )
    usuario_link.short_description = 'Usuario'
    usuario_link.admin_order_field = 'usuario__username'
    
    def agencia_link(self, obj):
        url = reverse('admin:monedero_agencia_change', args=[obj.agencia.id])
        return format_html('<a href="{}">{}</a>', url, obj.agencia.nombre)
    agencia_link.short_description = 'Agencia'
    agencia_link.admin_order_field = 'agencia__nombre'
    
    def pin_estado(self, obj):
        if obj._pin_operaciones:
            return "Configurado (último cambio: {})".format(
                obj.ultima_actividad.strftime('%Y-%m-%d %H:%M') if obj.ultima_actividad else 'N/A'
            )
        return "No configurado"
    pin_estado.short_description = 'Estado del PIN'
    
    def fecha_registro_short(self, obj):
        return obj.fecha_registro.strftime('%Y-%m-%d')
    fecha_registro_short.short_description = 'Registro'
    fecha_registro_short.admin_order_field = 'fecha_registro'
    
    def ultima_actividad_short(self, obj):
        return obj.ultima_actividad.strftime('%Y-%m-%d %H:%M') if obj.ultima_actividad else 'N/A'
    ultima_actividad_short.short_description = 'Última Actividad'
    ultima_actividad_short.admin_order_field = 'ultima_actividad'
    
    def get_fieldsets(self, request, obj=None):
        if not obj:
            return (
                ('Información Básica', {
                    'fields': (
                        'usuario', 
                        'agencia', 
                        'codigo_agente', 
                        'activo'
                    )
                }),
                ('Seguridad', {
                    'fields': (
                        'pin_nuevo',
                        'pin_confirmacion'
                    )
                }),
            )
        return super().get_fieldsets(request, obj)
    
    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            pin_nuevo = form.cleaned_data.get('pin_nuevo')
            
            if pin_nuevo:
                try:
                    obj.set_pin_operaciones(pin_nuevo)
                    obj.ultima_actividad = timezone.now()
                except ValidationError as e:
                    self.message_user(request, f"Error al configurar PIN: {e}", level='error')
                    return
            
            super().save_model(request, obj, form, change)
            
            if pin_nuevo and change:
                self.message_user(request, "PIN actualizado correctamente", level='success')

@admin.register(Agencia)
class AgenciaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 
        'codigo', 
        'ciudad', 
        'activa', 
        'fecha_registro_short',
        'total_agentes'
    )
    list_filter = ('activa', 'ciudad')
    search_fields = ('nombre', 'codigo', 'ciudad')
    readonly_fields = ('fecha_registro', 'clave_encripcion_preview')
    inlines = [AgenteInline]
    
    def fecha_registro_short(self, obj):
        return obj.fecha_registro.strftime('%Y-%m-%d')
    fecha_registro_short.short_description = 'Registro'
    fecha_registro_short.admin_order_field = 'fecha_registro'
    
    def total_agentes(self, obj):
        return obj.agentes_asociados.count()
    total_agentes.short_description = 'Agentes'
    
    def clave_encripcion_preview(self, obj):
        if obj.clave_encripcion:
            return format_html(
                '<code style="word-break: break-word">{}</code>', 
                obj.clave_encripcion.decode('utf-8')[:50] + '...'
            )
        return "No generada"
    clave_encripcion_preview.short_description = 'Clave de Encriptación'

# ... [Resto de las configuraciones de admin para otros modelos] ...

# Monederos
@admin.register(Monedero)
class MonederoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'saldo', 'saldo_retenido', 'saldo_disponible', 'nivel_verificacion')
    list_filter = ('nivel_verificacion',)
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name')
    readonly_fields = ('saldo_disponible', 'estadisticas_dashboard')
    fieldsets = (
        (None, {
            'fields': ('usuario', 'nivel_verificacion')
        }),
        ('Saldos', {
            'fields': ('saldo', 'saldo_retenido', 'saldo_disponible', 'limite_credito')
        }),
        ('Estadísticas', {
            'fields': ('estadisticas_dashboard',)
        }),
    )

    def estadisticas_dashboard(self, obj):
        stats = obj.estadisticas
        return format_html(
            "<b>Transferencias:</b> {} ({} este mes)<br>"
            "<b>Recargas:</b> {} ({} este mes)<br>"
            "<b>Saldo máximo histórico:</b> {} XOF".format(
                stats['total_transferencias'],
                stats['transferencias_mes'],
                stats['total_recargas'],
                stats['recargas_mes'],
                stats['saldo_maximo']
            )
        )
    estadisticas_dashboard.short_description = 'Estadísticas'

# Transferencias
class AuditoriaTransferenciaInline(admin.TabularInline):
    model = AuditoriaTransferencia
    extra = 0
    readonly_fields = ('accion', 'fecha', 'detalles', 'error')

@admin.register(Transferencia)
class TransferenciaAdmin(admin.ModelAdmin):
    list_display = ('referencia', 'emisor', 'receptor', 'cantidad', 'comision', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('referencia', 'emisor__username', 'receptor__username')
    readonly_fields = ('referencia', 'comision', 'fecha_creacion', 'fecha_procesamiento', 'metadata_display')
    inlines = [AuditoriaTransferenciaInline]
    fieldsets = (
        (None, {
            'fields': ('referencia', 'estado')
        }),
        ('Partes', {
            'fields': ('emisor', 'receptor')
        }),
        ('Montos', {
            'fields': ('cantidad', 'comision')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_procesamiento', 'fecha_programada')
        }),
        ('Verificación', {
            'fields': ('codigo_verificacion',)
        }),
        ('Metadata', {
            'fields': ('metadata_display',)
        }),
    )

    def metadata_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.metadata, indent=2))
    metadata_display.short_description = 'Metadata'

# Recargas
class AuditoriaRecargaInline(admin.TabularInline):
    model = AuditoriaRecarga
    extra = 0
    readonly_fields = ('accion', 'fecha', 'detalles', 'error')

@admin.register(Recarga)
class RecargaAdmin(admin.ModelAdmin):
    list_display = ('referencia', 'usuario', 'agente', 'monto', 'comision_agente', 'monto_neto', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('referencia', 'usuario__username', 'agente__codigo_agente')
    readonly_fields = ('referencia', 'comision_agente', 'monto_neto', 'fecha_creacion', 'fecha_procesamiento', 'datos_pago_display')
    inlines = [AuditoriaRecargaInline]
    fieldsets = (
        (None, {
            'fields': ('referencia', 'estado')
        }),
        ('Partes', {
            'fields': ('usuario', 'agente')
        }),
        ('Montos', {
            'fields': ('monto', 'comision_agente', 'monto_neto')
        }),
        ('Pago', {
            'fields': ('metodo_pago', 'datos_pago_display')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_procesamiento')
        }),
    )

    def datos_pago_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.datos_pago, indent=2))
    datos_pago_display.short_description = 'Datos de Pago'

# Auditorías
@admin.register(AuditoriaMonedero)
class AuditoriaMonederoAdmin(admin.ModelAdmin):
    list_display = ('monedero', 'accion', 'fecha')
    list_filter = ('accion', 'fecha')
    search_fields = ('monedero__usuario__username',)
    readonly_fields = ('monedero', 'accion', 'fecha', 'estado_anterior_display', 'estado_posterior_display', 'metadata_display')

    def estado_anterior_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.estado_anterior, indent=2))
    estado_anterior_display.short_description = 'Estado Anterior'

    def estado_posterior_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.estado_posterior, indent=2))
    estado_posterior_display.short_description = 'Estado Posterior'

    def metadata_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.metadata, indent=2))
    metadata_display.short_description = 'Metadata'

@admin.register(AuditoriaAgente)
class AuditoriaAgenteAdmin(admin.ModelAdmin):
    list_display = ('agente', 'accion', 'fecha')
    list_filter = ('accion', 'fecha')
    search_fields = ('agente__codigo_agente', 'agente__usuario__username')
    readonly_fields = ('detalles_display',)

    def detalles_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.detalles, indent=2))
    detalles_display.short_description = 'Detalles'

# Dashboard y Reportes
@admin.register(DashboardAdmin)
class DashboardAdminAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ultima_actualizacion')
    readonly_fields = ('ultima_actualizacion', 'estadisticas_sistema')

    def estadisticas_sistema(self, obj):
        stats = DashboardAdmin.obtener_estadisticas()
        return format_html(
            "<b>Usuarios:</b> {} ({} activos, {} nuevos hoy)<br>"
            "<b>Transferencias:</b> {} ({} hoy)<br>"
            "<b>Recargas:</b> {} ({} hoy)<br>"
            "<b>Saldo total:</b> {} XOF<br>"
            "<b>Comisiones:</b> {} XOF<br>"
            "<b>Agentes:</b> {} activos<br>"
            "<b>Agencias:</b> {} activas".format(
                stats['total_usuarios'],
                stats['usuarios_activos'],
                stats['nuevos_usuarios_hoy'],
                stats['total_transferencias'],
                stats['transferencias_hoy'],
                stats['total_recargas'],
                stats['recargas_hoy'],
                stats['saldo_total'],
                stats['comisiones_total'],
                stats['agentes_activos'],
                stats['agencias_activas']
            )
        )
    estadisticas_sistema.short_description = 'Estadísticas del Sistema'

@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'creado_por', 'fecha_creacion', 'fecha_completado', 'descargar_reporte')
    list_filter = ('tipo', 'fecha_creacion')
    search_fields = ('creado_por__username',)
    readonly_fields = ('fecha_creacion', 'fecha_completado', 'parametros_display')

    def descargar_reporte(self, obj):
        if obj.archivo:
            return format_html(
                '<a href="{}" download>Descargar</a>',
                obj.archivo.url
            )
        return "Pendiente"
    descargar_reporte.short_description = 'Archivo'

    def parametros_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.parametros, indent=2))
    parametros_display.short_description = 'Parámetros'

# Notificaciones y Transacciones
@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'titulo', 'leida', 'fecha')
    list_filter = ('tipo', 'leida', 'fecha')
    search_fields = ('usuario__username', 'titulo')
    readonly_fields = ('fecha', 'metadata_display')

    def metadata_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.metadata, indent=2))
    metadata_display.short_description = 'Metadata'

@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'monto', 'referencia', 'estado', 'creado_en')
    list_filter = ('tipo', 'estado', 'creado_en')
    search_fields = ('usuario__username', 'referencia')
    readonly_fields = ('creado_en', 'actualizado_en', 'metadata_display', 'relacion_link')

    def metadata_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.metadata, indent=2))
    metadata_display.short_description = 'Metadata'

    def relacion_link(self, obj):
        if obj.relacion_contenido and obj.relacion_id:
            url = reverse(f'admin:{obj.relacion_contenido.app_label}_{obj.relacion_contenido.model}_change', args=[obj.relacion_id])
            return format_html('<a href="{}">Ver {} #{}</a>', url, obj.relacion_contenido.name, obj.relacion_id)
        return "-"
    relacion_link.short_description = 'Relacionado con'

@admin.register(TransaccionRetenida)
class TransaccionRetenidaAdmin(admin.ModelAdmin):
    list_display = ('referencia', 'usuario', 'monto', 'estado', 'fecha_creacion', 'fecha_expiracion', 'relacion_link')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('referencia', 'usuario__username', 'motivo')
    readonly_fields = ('referencia', 'fecha_creacion', 'fecha_actualizacion', 'metadata_display', 'relacion_link')
    actions = ['liberar_retenciones', 'aplicar_retenciones', 'cancelar_retenciones']
    
    def relacion_link(self, obj):
        if obj.relacion_contenido and obj.relacion_id:
            url = reverse(f'admin:{obj.relacion_contenido.app_label}_{obj.relacion_contenido.model}_change', args=[obj.relacion_id])
            return format_html('<a href="{}">Ver {} #{}</a>', url, obj.relacion_contenido.name, obj.relacion_id)
        return "-"
    relacion_link.short_description = 'Relacionado con'
    
    def metadata_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.metadata, indent=2))
    metadata_display.short_description = 'Metadata'
    
    @admin.action(description='Liberar retenciones seleccionadas')
    def liberar_retenciones(self, request, queryset):
        for retencion in queryset:
            try:
                retencion.liberar()
                self.message_user(request, f"Retención {retencion.referencia} liberada")
            except Exception as e:
                self.message_user(request, f"Error liberando {retencion.referencia}: {str(e)}", level='error')
    
    @admin.action(description='Aplicar retenciones seleccionadas')
    def aplicar_retenciones(self, request, queryset):
        for retencion in queryset:
            try:
                retencion.aplicar()
                self.message_user(request, f"Retención {retencion.referencia} aplicada")
            except Exception as e:
                self.message_user(request, f"Error aplicando {retencion.referencia}: {str(e)}", level='error')
    
    @admin.action(description='Cancelar retenciones seleccionadas')
    def cancelar_retenciones(self, request, queryset):
        for retencion in queryset:
            try:
                retencion.cancelar()
                self.message_user(request, f"Retención {retencion.referencia} cancelada")
            except Exception as e:
                self.message_user(request, f"Error cancelando {retencion.referencia}: {str(e)}", level='error')

@admin.register(AuditoriaRetencion)
class AuditoriaRetencionAdmin(admin.ModelAdmin):
    list_display = ('retencion', 'accion', 'fecha')
    list_filter = ('accion', 'fecha')
    search_fields = ('retencion__referencia', 'retencion__usuario__username')
    readonly_fields = ('detalles_display',)
    
    def detalles_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.detalles, indent=2))
    detalles_display.short_description = 'Detalles'