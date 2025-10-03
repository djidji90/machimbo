from rest_framework import serializers
from decimal import Decimal
from django.contrib.auth import get_user_model
from .models import (
    ConfiguracionSistema,
    Agencia,
    Agente,
    Monedero,
    Transferencia,
    Recarga,
    AuditoriaTransferencia,
    AuditoriaRecarga,
    AuditoriaMonedero,
    AuditoriaAgente,
    DashboardAdmin,
    Reporte,
    Notificacion,
    Transaccion
)

User = get_user_model()

## ----------------------------
## 1. SERIALIZERS DE CONFIGURACIÓN
## ----------------------------

class ConfiguracionSistemaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionSistema
        fields = '__all__'
        read_only_fields = ('id',)

    def validate_limite_transferencia_diaria(self, value):
        if value <= 0:
            raise serializers.ValidationError("El límite debe ser mayor que cero")
        return value

    def validate_comision_transferencia_porcentaje(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("El porcentaje debe estar entre 0 y 100")
        return value

## ----------------------------
## 2. SERIALIZERS DE AGENCIAS Y AGENTES
## ----------------------------

class AgenciaSerializer(serializers.ModelSerializer):
    agentes_activos = serializers.SerializerMethodField()
    url_dashboard = serializers.SerializerMethodField()

    class Meta:
        model = Agencia
        fields = [
            'id', 'codigo', 'nombre', 'direccion', 'ciudad', 'telefono', 'email',
            'activa', 'fecha_registro', 'zona_horaria', 'agentes_activos', 'url_dashboard'
        ]
        read_only_fields = ('fecha_registro', 'agentes_activos', 'url_dashboard')
        extra_kwargs = {
            'clave_encripcion': {'write_only': True}
        }

    def get_agentes_activos(self, obj):
        return obj.agentes_activos().count()

    def get_url_dashboard(self, obj):
        return obj.get_absolute_url()


class AgenteSerializer(serializers.ModelSerializer):
    usuario_info = serializers.SerializerMethodField()
    agencia_info = serializers.SerializerMethodField()
    estadisticas = serializers.SerializerMethodField()

    class Meta:
        model = Agente
        fields = [
            'id', 'usuario', 'usuario_info', 'agencia', 'agencia_info', 
            'codigo_agente', 'comision_acumulada', 'activo', 
            'fecha_registro', 'ultima_actividad', 'estadisticas'
        ]
        read_only_fields = [
            'id', 'usuario_info', 'agencia_info', 'comision_acumulada',
            'fecha_registro', 'ultima_actividad', 'estadisticas'
        ]
        extra_kwargs = {
            '_pin_operaciones': {'write_only': True},
            'usuario': {'required': True},
            'agencia': {'required': True}
        }

    def get_usuario_info(self, obj):
        """Información básica del usuario asociado"""
        usuario = obj.usuario
        return {
            'username': usuario.username,
            'email': usuario.email,
            'nombre_completo': usuario.get_full_name(),
            'is_active': usuario.is_active
        }

    def get_agencia_info(self, obj):
        """Información básica de la agencia"""
        agencia = obj.agencia
        return {
            'id': agencia.id,
            'nombre': agencia.nombre,
            'ciudad': agencia.ciudad,
            'codigo': agencia.codigo,
            'activa': agencia.activa
        }

    def get_estadisticas(self, obj):
        """Obtiene estadísticas del agente usando el property del modelo"""
        return obj.estadisticas

    def validate_codigo_agente(self, value):
        """Valida el código del agente"""
        if not value.isalnum():
            raise serializers.ValidationError("El código solo puede contener letras y números")
        return value.upper()

    def validate(self, data):
        """Validaciones adicionales"""
        # Verifica unicidad del código de agente al crear
        if self.instance is None and Agente.objects.filter(codigo_agente=data.get('codigo_agente')).exists():
            raise serializers.ValidationError
## ----------------------------
## 3. SERIALIZERS DE NÚCLEO
## ----------------------------

class MonederoSerializer(serializers.ModelSerializer):
    usuario_info = serializers.SerializerMethodField()
    saldo_disponible = serializers.SerializerMethodField()
    estadisticas = serializers.SerializerMethodField()

    class Meta:
        model = Monedero
        fields = [
            'id', 'usuario', 'usuario_info', 'saldo', 'saldo_disponible', 'saldo_retenido',
            'limite_credito', 'nivel_verificacion', 'fecha_actualizacion', 'estadisticas'
        ]
        read_only_fields = (
            'id', 'usuario_info', 'saldo', 'saldo_disponible', 'saldo_retenido',
            'fecha_actualizacion', 'estadisticas'
        )

    def get_usuario_info(self, obj):
        return {
            'username': obj.usuario.username,
            'email': obj.usuario.email
        }

    def get_saldo_disponible(self, obj):
        return float(obj.saldo_disponible)

    def get_estadisticas(self, obj):
        return obj.estadisticas

## ----------------------------
## 4. SERIALIZERS DE OPERACIONES
## ----------------------------

class TransferenciaSerializer(serializers.ModelSerializer):
    emisor_info = serializers.SerializerMethodField()
    receptor_info = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    comision = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Transferencia
        fields = [
            'referencia', 'emisor', 'emisor_info', 'receptor', 'receptor_info', 'cantidad',
            'comision', 'estado', 'estado_display', 'fecha_creacion', 'fecha_procesamiento',
            'fecha_programada', 'codigo_verificacion', 'metadata', 'tarea_programada'
        ]
        read_only_fields = (
            'referencia', 'emisor_info', 'receptor_info', 'comision', 'estado',
            'fecha_creacion', 'fecha_procesamiento', 'metadata', 'tarea_programada'
        )

    def get_emisor_info(self, obj):
        return {
            'username': obj.emisor.username,
            'email': obj.emisor.email,
            'nombre_completo': obj.emisor.get_full_name()
        }

    def get_receptor_info(self, obj):
        return {
            'username': obj.receptor.username,
            'email': obj.receptor.email,
            'nombre_completo': obj.receptor.get_full_name()
        }

    def validate(self, data):
        config = ConfiguracionSistema.cargar()
        
        if data['emisor'] == data['receptor']:
            raise serializers.ValidationError("No puedes transferirte a ti mismo")
            
        if data['cantidad'] < config.minimo_transferencia:
            raise serializers.ValidationError(
                f"El monto mínimo es {config.minimo_transferencia} XOF"
            )
        
        return data

class RecargaSerializer(serializers.ModelSerializer):
    usuario_info = serializers.SerializerMethodField()
    agente_info = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    comision_agente = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    monto_neto = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Recarga
        fields = [
            'referencia', 'usuario', 'usuario_info', 'agente', 'agente_info', 'monto',
            'comision_agente', 'monto_neto', 'estado', 'estado_display', 'metodo_pago',
            'datos_pago', 'fecha_creacion', 'fecha_procesamiento', 'tarea_procesamiento'
        ]
        read_only_fields = (
            'referencia', 'usuario_info', 'agente_info', 'comision_agente', 'monto_neto',
            'estado', 'fecha_creacion', 'fecha_procesamiento', 'tarea_procesamiento'
        )

    def get_usuario_info(self, obj):
        return {
            'username': obj.usuario.username,
            'email': obj.usuario.email
        }

    def get_agente_info(self, obj):
        if not obj.agente:
            return None
        return {
            'codigo_agente': obj.agente.codigo_agente,
            'nombre': obj.agente.usuario.get_full_name()
        }

    def validate_monto(self, value):
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor que cero")
        return value

## ----------------------------
## 5. SERIALIZERS DE AUDITORÍA
## ----------------------------

class AuditoriaBaseSerializer(serializers.ModelSerializer):
    fecha = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')

class AuditoriaTransferenciaSerializer(AuditoriaBaseSerializer):
    transferencia_referencia = serializers.CharField(source='transferencia.referencia', read_only=True)

    class Meta:
        model = AuditoriaTransferencia
        fields = '__all__'

class AuditoriaRecargaSerializer(AuditoriaBaseSerializer):
    recarga_referencia = serializers.CharField(source='recarga.referencia', read_only=True)

    class Meta:
        model = AuditoriaRecarga
        fields = '__all__'

class AuditoriaMonederoSerializer(AuditoriaBaseSerializer):
    monedero_usuario = serializers.CharField(source='monedero.usuario.username', read_only=True)

    class Meta:
        model = AuditoriaMonedero
        fields = '__all__'

class AuditoriaAgenteSerializer(AuditoriaBaseSerializer):
    agente_codigo = serializers.CharField(source='agente.codigo_agente', read_only=True)

    class Meta:
        model = AuditoriaAgente
        fields = '__all__'

## ----------------------------
## 6. SERIALIZERS DE DASHBOARD Y REPORTES
## ----------------------------

class DashboardAdminSerializer(serializers.ModelSerializer):
    estadisticas = serializers.SerializerMethodField()
    ultima_actualizacion = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = DashboardAdmin
        fields = '__all__'

    def get_estadisticas(self, obj):
        return obj.obtener_estadisticas()

class ReporteSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    creado_por_info = serializers.SerializerMethodField()
    fecha_creacion = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
    fecha_completado = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = Reporte
        fields = '__all__'

    def get_creado_por_info(self, obj):
        if not obj.creado_por:
            return None
        return {
            'username': obj.creado_por.username,
            'nombre_completo': obj.creado_por.get_full_name()
        }

## ----------------------------
## 7. SERIALIZERS DE NOTIFICACIONES
## ----------------------------

class NotificacionSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    fecha = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = Notificacion
        fields = '__all__'

## ----------------------------
## 8. SERIALIZERS DE TRANSACCIONES
## ----------------------------

class TransaccionSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    usuario_info = serializers.SerializerMethodField()
    relacion_info = serializers.SerializerMethodField()
    creado_en = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
    actualizado_en = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = Transaccion
        fields = '__all__'

    def get_usuario_info(self, obj):
        return {
            'username': obj.usuario.username,
            'email': obj.usuario.email
        }

    def get_relacion_info(self, obj):
        if not obj.relacion:
            return None
        
        # Puedes personalizar esto según tus modelos relacionados
        return {
            'modelo': obj.relacion_contenido.model,
            'id': obj.relacion_id,
            'representacion': str(obj.relacion)
        }

## ----------------------------
## SERIALIZERS PARA OPERACIONES ESPECÍFICAS
## ----------------------------

class TransferenciaCreateSerializer(serializers.Serializer):
    receptor = serializers.CharField()
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=2)
    programar = serializers.BooleanField(default=False)
    fecha_programada = serializers.DateTimeField(required=False)

    def validate_receptor(self, value):
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Usuario receptor no encontrado")

class RecargaCreateSerializer(serializers.Serializer):
    monto = serializers.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = serializers.CharField(max_length=50)
    datos_pago = serializers.JSONField()

class PinOperacionesSerializer(serializers.Serializer):
    pin = serializers.CharField(max_length=6, min_length=6)

class CodigoVerificacionSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=6)
