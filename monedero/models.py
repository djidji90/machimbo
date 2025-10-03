from decimal import Decimal
import uuid
from django.db.models import JSONField  # ✅ Correcto
import logging
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
from django.db.models.functions import Cast
from django.db.models import FloatField
from django.db.models import Max, F
from django.db.models import Sum, F, Q
from cryptography.fernet import Fernet
from datetime import timedelta
from django.db import connection
from django.core.cache import cache
from django_celery_results.models import TaskResult
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json
from django.urls import reverse

logger = logging.getLogger(__name__)
User = get_user_model()

## ----------------------------
## 1. MODELOS DE CONFIGURACIÓN
## ----------------------------

class ConfiguracionSistema(models.Model):
    """
    Configuración centralizada del sistema financiero
    """
    # Límites de operaciones
    limite_transferencia_diaria = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('500000.00'))
    limite_recarga_diaria = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100000.00'))
    minimo_transferencia = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1000.00'))
    
    # Comisiones
    comision_transferencia_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    comision_transferencia_minima = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100.00'))
    comision_recarga_agente = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    
    # Seguridad
    requiere_verificacion_monto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('50000.00'))
    max_intentos_verificacion = models.PositiveIntegerField(default=3)
    max_operaciones_diarias = models.PositiveIntegerField(default=10)
    
    # Configuración Celery
    tiempo_espera_procesamiento = models.PositiveIntegerField(
        default=30, 
        help_text="Tiempo en segundos para procesamiento asíncrono"
    )
    reintentos_fallidos = models.PositiveIntegerField(default=3)

    class Meta:
        verbose_name = "Configuración del Sistema"
        verbose_name_plural = "Configuraciones del Sistema"

    @classmethod
    def cargar(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Configuración del Sistema Financiero"

## ----------------------------
## 2. MODELOS DE AGENCIAS Y AGENTES
## ----------------------------


 # Asegúrate de ajustar esto si hay import circular
class Agencia(models.Model):
    """
    Modelo para agencias físicas o virtuales que gestionan agentes
    """
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    direccion = models.TextField()
    ciudad = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    email = models.EmailField()
    activa = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    clave_encripcion = models.BinaryField(editable=False, null=True, blank=True)
    zona_horaria = models.CharField(max_length=50, default="UTC")

    class Meta:
        verbose_name = "Agencia"    
        verbose_name_plural = "Agencias"
        ordering = ["-fecha_registro"]
        permissions = [
            ("view_dashboard_agencia", "Puede ver el dashboard de la agencia"),
        ]

    def save(self, *args, **kwargs):
        if not self.clave_encripcion:
            self.clave_encripcion = Fernet.generate_key()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({self.ciudad})"

    def agentes_activos(self):
        return self.agentes_asociados.filter(activo=True) 

    def get_absolute_url(self):
        return reverse('agencia_dashboard', kwargs={'pk': self.pk})

    @property
    def estadisticas(self):
        cache_key = f"agencia_stats:{self.pk}"
        stats = cache.get(cache_key)

        if not stats:
            stats = {
                'total_agentes': self.agentes_asociados.count(),
                'agentes_activos': self.agentes_asociados.filter(activo=True).count(),
                'total_recargas': Recarga.objects.filter(agente__agencia=self).count(),
                'recargas_mes': Recarga.objects.filter(
                    agente__agencia=self,
                    fecha_creacion__month=timezone.now().month
                ).count(),
                'comision_total': Recarga.objects.filter(
                    agente__agencia=self
                ).aggregate(total=Sum('comision_agente'))['total'] or 0
            }
            cache.set(cache_key, stats, timeout=300)

        return stats

class Agente(models.Model):
    """
    Modelo para agentes autorizados a procesar recargas
    """
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="agente")
    agencia = models.ForeignKey(Agencia, on_delete=models.PROTECT, related_name="agentes_asociados")
    codigo_agente = models.CharField(max_length=20, unique=True)
    comision_acumulada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    _pin_operaciones = models.CharField(max_length=255, blank=True, null=True)
    ultima_actividad = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["-fecha_registro"]
        permissions = [
            ("procesar_recargas", "Puede procesar recargas de saldo"),
            ("view_dashboard_agente", "Puede ver el dashboard de agente"),
        ]

    def __str__(self):
        return f"{self.usuario.get_full_name()} ({self.codigo_agente})"

    def set_pin_operaciones(self, raw_pin):
        """Encripta y almacena el PIN de operaciones del agente"""
        if len(raw_pin) != 6 or not raw_pin.isdigit():
            raise ValidationError("El PIN debe tener exactamente 6 dígitos")
        fernet = Fernet(self.agencia.clave_encripcion)
        self._pin_operaciones = fernet.encrypt(raw_pin.encode()).decode()
        self.save()

    def verificar_pin_operaciones(self, raw_pin):
        """Verifica el PIN de operaciones del agente"""
        if not self._pin_operaciones:
            return False
        try:
            fernet = Fernet(self.agencia.clave_encripcion)
            return fernet.decrypt(self._pin_operaciones.encode()).decode() == raw_pin
        except:
            return False

    def actualizar_comision(self, monto):
        """Actualiza la comisión acumulada del agente"""
        self.comision_acumulada += Decimal(monto)
        self.ultima_actividad = timezone.now()
        self.save()

    def get_absolute_url(self):
        return reverse('agente_dashboard', kwargs={'pk': self.pk})

    @property
    def estadisticas(self):
        cache_key = f"agente_stats:{self.pk}"
        stats = cache.get(cache_key)
        
        if not stats:
            hoy = timezone.now().date()
            stats = {
                'total_recargas': self.recargas_procesadas.count(),
                'recargas_hoy': self.recargas_procesadas.filter(
                    fecha_creacion__date=hoy
                ).count(),
                'comision_hoy': self.recargas_procesadas.filter(
                    fecha_creacion__date=hoy
                ).aggregate(total=Sum('comision_agente'))['total'] or 0,
                'comision_mes': self.recargas_procesadas.filter(
                    fecha_creacion__month=hoy.month
                ).aggregate(total=Sum('comision_agente'))['total'] or 0,
                'clientes_unicos': self.recargas_procesadas.values('usuario').distinct().count()
            }
            cache.set(cache_key, stats, timeout=300)  # Cache por 5 minutos
        
        return stats

## ----------------------------
## 3. MODELOS DE NÚCLEO
## ----------------------------

class Monedero(models.Model):
    """
    Modelo principal para manejar saldos de usuarios
    """
    usuario = models.OneToOneField(User, on_delete=models.PROTECT, related_name="monedero")
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    saldo_retenido = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    nivel_verificacion = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = "Monedero"
        verbose_name_plural = "Monederos"
        indexes = [
            models.Index(fields=['usuario']),
            models.Index(fields=['saldo']),
        ]

    def __str__(self):
        return f"Monedero de {self.usuario.username}"

    @property
    def saldo_disponible(self):
        return (self.saldo - self.saldo_retenido).quantize(Decimal('0.00'))

    @transaction.atomic
    def actualizar_saldo(self, monto, motivo=None, retener=False):
        """
        Actualiza el saldo de forma segura con transacción atómica
        """
        monto = Decimal(monto).quantize(Decimal('0.00'))
        
        with transaction.atomic():
            monedero = Monedero.objects.select_for_update().get(pk=self.pk)
            
            if retener:
                monedero.saldo_retenido += monto
            else:
                monedero.saldo += monto
                
            monedero.save()
            
            AuditoriaMonedero.registrar(
                monedero=monedero,
                accion='RETENCION' if retener else 'ACTUALIZACION',
                estado_anterior={'saldo': float(monedero.saldo - monto)},
                estado_posterior={'saldo': float(monedero.saldo)},
                metadata={'motivo': motivo, 'monto': float(monto)}
            )
            
            return monedero.saldo



    @property
    def estadisticas(self):
        cache_key = f"monedero_stats:{self.pk}"
        stats = cache.get(cache_key)
        
        if not stats:
            hoy = timezone.now().date()

            # Obtener el saldo máximo desde estado_posterior['saldo'] como float
            max_saldo = AuditoriaMonedero.objects.filter(
                monedero=self,
                accion='ACTUALIZACION'
            ).annotate(
                saldo_extraido=Cast(F("estado_posterior__saldo"), FloatField())
            ).aggregate(
                max_saldo=Max("saldo_extraido")
            )['max_saldo'] or 0

            stats = {
                'total_transferencias': Transferencia.objects.filter(
                    Q(emisor=self.usuario) | Q(receptor=self.usuario)
                ).count(),
                'transferencias_mes': Transferencia.objects.filter(
                    Q(emisor=self.usuario) | Q(receptor=self.usuario),
                    fecha_creacion__month=hoy.month
                ).count(),
                'total_recargas': Recarga.objects.filter(usuario=self.usuario).count(),
                'recargas_mes': Recarga.objects.filter(
                    usuario=self.usuario,
                    fecha_creacion__month=hoy.month
                ).count(),
                'saldo_maximo': max_saldo
            }
            cache.set(cache_key, stats, timeout=300)
        
        return stats


## ----------------------------
## 4. MODELOS DE OPERACIONES
## ----------------------------

class Transferencia(models.Model):
    """
    Modelo optimizado para transferencias entre usuarios
    """
    class Estados(models.TextChoices):
        PENDIENTE = "PENDIENTE", _("Pendiente")
        COMPLETADA = "COMPLETADA", _("Completada")
        FALLIDA = "FALLIDA", _("Fallida")
        REVERTIDA = "REVERTIDA", _("Revertida")
        EN_VERIFICACION = "EN_VERIFICACION", _("En Verificación")
        PROGRAMADA = "PROGRAMADA", _("Programada")

    referencia = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    emisor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="transferencias_enviadas")
    receptor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="transferencias_recibidas")
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('5000.00'))])
    comision = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.PENDIENTE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_procesamiento = models.DateTimeField(null=True, blank=True)
    fecha_programada = models.DateTimeField(null=True, blank=True)
    codigo_verificacion = models.CharField(max_length=6, null=True, blank=True)
    metadata = models.JSONField(default=dict)
    tarea_programada = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Transferencia"
        verbose_name_plural = "Transferencias"
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=['emisor', 'estado']),
            models.Index(fields=['receptor', 'estado']),
            models.Index(fields=['fecha_creacion']),
            models.Index(fields=['fecha_programada']),
        ]

    def __str__(self):
        return f"Transferencia {self.referencia}"

    def clean(self):
        config = ConfiguracionSistema.cargar()
        
        if self.emisor == self.receptor:
            raise ValidationError("No puedes transferirte a ti mismo")
            
        if self.cantidad < config.minimo_transferencia:
            raise ValidationError(f"El monto mínimo es {config.minimo_transferencia} XOF")
        
        # Calcular comisión automáticamente
        self.comision = max(
            self.cantidad * config.comision_transferencia_porcentaje / 100,
            config.comision_transferencia_minima
        ).quantize(Decimal('0.00'))

    @transaction.atomic
    def procesar(self):
        """
        Procesa la transferencia de forma segura:
        1. Verifica requisitos
        2. Debita al emisor (monto + comisión)
        3. Acredita al receptor (monto)
        4. Actualiza estados
        5. Notifica a los usuarios implicados
        """
        config = ConfiguracionSistema.cargar()
        
        if self.estado not in [self.Estados.PENDIENTE, self.Estados.PROGRAMADA]:
            raise ValidationError("Solo se pueden procesar transferencias pendientes o programadas")
        
        try:
            with transaction.atomic():
                # Bloquear registros para evitar condiciones de carrera
                emisor_monedero = Monedero.objects.select_for_update().get(usuario=self.emisor)
                receptor_monedero = Monedero.objects.select_for_update().get(usuario=self.receptor)
                
                # Verificar límites diarios
                hoy = timezone.now().date()
                total_transferido_hoy = Transferencia.objects.filter(
                    emisor=self.emisor,
                    estado=self.Estados.COMPLETADA,
                    fecha_creacion__date=hoy
                ).aggregate(total=Sum('cantidad'))['total'] or 0
                
                if (total_transferido_hoy + self.cantidad) > config.limite_transferencia_diaria:
                    raise ValidationError("Límite diario de transferencias excedido")
                
                # Verificar saldo suficiente
                total_debito = self.cantidad + self.comision
                if emisor_monedero.saldo_disponible < total_debito:
                    raise ValidationError("Saldo insuficiente para completar la transferencia")
                
                # Ejecutar movimientos
                emisor_monedero.actualizar_saldo(-total_debito, motivo=f"Transferencia {self.referencia}")
                receptor_monedero.actualizar_saldo(self.cantidad, motivo=f"Transferencia {self.referencia}")
                
                # Actualizar estado
                self.estado = self.Estados.COMPLETADA
                self.fecha_procesamiento = timezone.now()
                self.save()
            
                # Registrar auditoría
                AuditoriaTransferencia.registrar(
                    transferencia=self,
                    accion='TRANSFERENCIA_COMPLETADA',
                    detalles={
                        'monto_transferido': float(self.cantidad),
                        'comision': float(self.comision)
                    }
                )
                
                # Notificar a los usuarios implicados
                Notificacion.notificar_transferencia(self)
                
                # Si era programada, eliminar la tarea periódica
                if self.tarea_programada:
                    try:
                        PeriodicTask.objects.filter(name=self.tarea_programada).delete()
                        self.tarea_programada = None
                        self.save()
                    except Exception as e:
                        logger.error(f"Error eliminando tarea programada {self.tarea_programada}: {str(e)}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error procesando transferencia {self.referencia}: {str(e)}")
            self.estado = self.Estados.FALLIDA
            self.save()
            
            AuditoriaTransferencia.registrar(
                transferencia=self,
                accion='TRANSFERENCIA_FALLIDA',
                error=str(e)
            )
            
            # Notificar al emisor sobre la falla
            Notificacion.objects.create(
                usuario=self.emisor,
                tipo=Notificacion.Tipos.TRANSFERENCIA,
                titulo="Transferencia fallida",
                mensaje=f"La transferencia de {self.cantidad} XOF no pudo completarse: {str(e)}",
                metadata={
                    "referencia": str(self.referencia),
                    "error": str(e)
                },
                importante=True
            )
            
            raise ValidationError(f"Error al procesar transferencia: {str(e)}")

    def programar(self, fecha_ejecucion):
        """Programa una transferencia para ejecutarse en el futuro"""
        from .tasks import ejecutar_transferencia_programada
        
        self.estado = self.Estados.PROGRAMADA
        self.fecha_programada = fecha_ejecucion
        self.save()
        
        # Crear tarea periódica
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.SECONDS,
        )
        
        nombre_tarea = f"transferencia_{self.referencia}"
        
        task = PeriodicTask.objects.create(
            interval=schedule,
            name=nombre_tarea,
            task='finanzas.tasks.ejecutar_transferencia_programada',
            args=json.dumps([str(self.pk)]),
            start_time=fecha_ejecucion,
            one_off=True
        )
        
        self.tarea_programada = nombre_tarea
        self.save()
        
        return task

class Recarga(models.Model):
    """
    Modelo especializado para recargas de saldo con agentes
    """
    class Estados(models.TextChoices):
        PENDIENTE = "PENDIENTE", _("Pendiente")
        COMPLETADA = "COMPLETADA", _("Completada")
        RECHAZADA = "RECHAZADA", _("Rechazada")
        EN_PROCESO = "EN_PROCESO", _("En Proceso")

    referencia = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='recargas')
    agente = models.ForeignKey(Agente, on_delete=models.PROTECT, null=True, blank=True, related_name='recargas_procesadas')
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    comision_agente = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    monto_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.PENDIENTE)
    metodo_pago = models.CharField(max_length=50)
    datos_pago = models.JSONField(default=dict)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_procesamiento = models.DateTimeField(null=True, blank=True)
    tarea_procesamiento = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = 'Recarga de Saldo'
        verbose_name_plural = 'Recargas de Saldo'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['usuario', 'estado']),
            models.Index(fields=['agente', 'estado']),
            models.Index(fields=['fecha_creacion']),
        ]

    def __str__(self):
        return f"Recarga #{self.referencia}"

    def save(self, *args, **kwargs):
        # Calcular comisión (1%) y monto neto
        if not self.pk:
            config = ConfiguracionSistema.cargar()
            self.comision_agente = self.monto * config.comision_recarga_agente / 100
            self.monto_neto = self.monto - self.comision_agente
        
        super().save(*args, **kwargs)

    @transaction.atomic
    def procesar(self, agente):
        """Procesa la recarga y actualiza los saldos"""
        if self.estado != self.Estados.PENDIENTE:
            raise ValidationError("Solo se pueden procesar recargas pendientes")
        
        config = ConfiguracionSistema.cargar()
        
        try:
            with transaction.atomic():
                # Verificar límites diarios
                hoy = timezone.now().date()
                total_recargado_hoy = Recarga.objects.filter(
                    usuario=self.usuario,
                    estado=self.Estados.COMPLETADA,
                    fecha_creacion__date=hoy
                ).aggregate(total=Sum('monto'))['total'] or 0
                
                if (total_recargado_hoy + self.monto) > config.limite_recarga_diaria:
                    raise ValidationError("Límite diario de recargas excedido")
                
                # Bloquear registros
                monedero_usuario = Monedero.objects.select_for_update().get(usuario=self.usuario)
                monedero_agente = Monedero.objects.select_for_update().get(usuario=agente.usuario)
                
                # Acreditar monto neto al usuario
                monedero_usuario.actualizar_saldo(self.monto_neto, motivo=f"Recarga {self.referencia}")
                
                # Acreditar comisión al agente
                monedero_agente.actualizar_saldo(
                    self.comision_agente,
                    motivo=f"Comisión por recarga {self.referencia}"
                )
                agente.actualizar_comision(self.comision_agente)
                
                # Actualizar estado
                self.agente = agente
                self.estado = self.Estados.COMPLETADA
                self.fecha_procesamiento = timezone.now()
                self.save()
                
                AuditoriaRecarga.registrar(
                    recarga=self,
                    accion='RECARGA_COMPLETADA'
                )
                
                # Notificar al usuario sobre la recarga exitosa
                Notificacion.notificar_recarga(self)
                
                # Notificar al agente sobre la comisión obtenida
                Notificacion.objects.create(
                    usuario=agente.usuario,
                    tipo=Notificacion.Tipos.RECARGA,
                    titulo="Comisión por recarga",
                    mensaje=f"Has recibido {self.comision_agente} XOF de comisión por la recarga {self.referencia}",
                    metadata={
                        "referencia": str(self.referencia),
                        "monto_recarga": float(self.monto),
                        "comision": float(self.comision_agente),
                        "usuario": self.usuario.username
                    }
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error procesando recarga {self.referencia}: {str(e)}")
            self.estado = self.Estados.RECHAZADA
            self.save()
            
            AuditoriaRecarga.registrar(
                recarga=self,
                accion='RECARGA_FALLIDA',
                error=str(e)
            )
            
            # Notificar al usuario sobre la recarga fallida
            Notificacion.objects.create(
                usuario=self.usuario,
                tipo=Notificacion.Tipos.RECARGA,
                titulo="Recarga fallida",
                mensaje=f"La recarga de {self.monto} XOF no pudo completarse: {str(e)}",
                metadata={
                    "referencia": str(self.referencia),
                    "error": str(e)
                },
                importante=True
            )
            
            raise ValidationError(f"Error al procesar recarga: {str(e)}")

    def procesar_async(self):
        """Envía la recarga a procesamiento asíncrono"""
        from .tasks import procesar_recarga_async
        
        if self.estado != self.Estados.PENDIENTE:
            return False
            
        self.estado = self.Estados.EN_PROCESO
        self.save()
        
        task = procesar_recarga_async.delay(self.pk)
        self.tarea_procesamiento = task.id
        self.save()
        
        return task.id

## ----------------------------
## 5. MODELOS DE AUDITORÍA
## ----------------------------

class AuditoriaTransferencia(models.Model):
    transferencia = models.ForeignKey(Transferencia, on_delete=models.CASCADE, related_name='auditorias')
    accion = models.CharField(max_length=50)
    fecha = models.DateTimeField(auto_now_add=True)
    detalles = models.JSONField(default=dict)
    error = models.TextField(null=True, blank=True)
    tarea_celery = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = 'Auditoría de Transferencia'
        verbose_name_plural = 'Auditorías de Transferencias'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['transferencia', 'accion']),
            models.Index(fields=['fecha']),
        ]

    @classmethod
    def registrar(cls, transferencia, accion, detalles=None, error=None, tarea=None):
        return cls.objects.create(
            transferencia=transferencia,
            accion=accion,
            detalles=detalles or {},
            error=error,
            tarea_celery=tarea
        )

class AuditoriaRecarga(models.Model):
    recarga = models.ForeignKey(Recarga, on_delete=models.CASCADE, related_name='auditorias')
    accion = models.CharField(max_length=50)
    fecha = models.DateTimeField(auto_now_add=True)
    detalles = models.JSONField(default=dict)
    error = models.TextField(null=True, blank=True)
    tarea_celery = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = 'Auditoría de Recarga'
        verbose_name_plural = 'Auditorías de Recargas'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['recarga', 'accion']),
            models.Index(fields=['fecha']),
        ]

    @classmethod
    def registrar(cls, recarga, accion, detalles=None, error=None, tarea=None):
        return cls.objects.create(
            recarga=recarga,
            accion=accion,
            detalles=detalles or {},
            error=error,
            tarea_celery=tarea
        )



class AuditoriaMonedero(models.Model):
    monedero = models.ForeignKey(
        Monedero, 
        on_delete=models.CASCADE,
        related_name='auditorias'
    )
    accion = models.CharField(max_length=50)
    fecha = models.DateTimeField(auto_now_add=True)
    estado_anterior = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict
    )
    estado_posterior = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict
    )
    metadata = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict
    )
    tarea_celery = models.CharField(
        max_length=100, 
        null=True, 
        blank=True
    )

    class Meta:
        ordering = ['-fecha']  # Orden por defecto
        indexes = [
            models.Index(fields=['monedero', 'fecha']),
            models.Index(
                fields=['estado_posterior'],
                condition=models.Q(estado_posterior__has_key='saldo'),
                name='idx_saldo_posterior'
            ),
            models.Index(
                fields=['estado_anterior'],
                condition=models.Q(estado_anterior__has_key='saldo'),
                name='idx_saldo_anterior'
            )
        ]

    def __str__(self):
        return f"Auditoría {self.id} - {self.accion}"
class AuditoriaAgente(models.Model):
    agente = models.ForeignKey(Agente, on_delete=models.CASCADE, related_name='auditorias')
    accion = models.CharField(max_length=50)
    fecha = models.DateTimeField(auto_now_add=True)
    detalles = models.JSONField(default=dict)
    tarea_celery = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = 'Auditoría de Agente'
        verbose_name_plural = 'Auditorías de Agentes'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['agente', 'accion']),
            models.Index(fields=['fecha']),
        ]

    @classmethod
    def registrar(cls, agente, accion, detalles=None, tarea=None):
        return cls.objects.create(
            agente=agente,
            accion=accion,
            detalles=detalles or {},
            tarea_celery=tarea
        )

## ----------------------------
## 6. MODELOS DE DASHBOARD Y REPORTES
## ----------------------------

class DashboardAdmin(models.Model):
    """
    Modelo para almacenar configuraciones del dashboard de administración
    """
    nombre = models.CharField(max_length=100, default="Dashboard Principal")
    configuracion = models.JSONField(default=dict)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dashboard de Administración"
        verbose_name_plural = "Dashboards de Administración"

    def __str__(self):
        return self.nombre

    @classmethod
    def obtener_estadisticas(cls):
        cache_key = "dashboard_admin_stats"
        stats = cache.get(cache_key)
        
        if not stats:
            hoy = timezone.now().date()
            stats = {
                'total_usuarios': User.objects.count(),
                'usuarios_activos': User.objects.filter(is_active=True).count(),
                'nuevos_usuarios_hoy': User.objects.filter(date_joined__date=hoy).count(),
                'total_transferencias': Transferencia.objects.count(),
                'transferencias_hoy': Transferencia.objects.filter(fecha_creacion__date=hoy).count(),
                'total_recargas': Recarga.objects.count(),
                'recargas_hoy': Recarga.objects.filter(fecha_creacion__date=hoy).count(),
                'saldo_total': Monedero.objects.aggregate(total=Sum('saldo'))['total'] or 0,
                'comisiones_total': Recarga.objects.aggregate(total=Sum('comision_agente'))['total'] or 0,
                'agentes_activos': Agente.objects.filter(activo=True).count(),
                'agencias_activas': Agencia.objects.filter(activa=True).count()
            }
            cache.set(cache_key, stats, timeout=3600)  # Cache por 1 hora
        
        return stats

class Reporte(models.Model):
    """
    Modelo para generar y almacenar reportes del sistema
    """
    class TiposReporte(models.TextChoices):
        TRANSFERENCIAS = "TRANSFERENCIAS", _("Reporte de Transferencias")
        RECARGAS = "RECARGAS", _("Reporte de Recargas")
        AGENTES = "AGENTES", _("Reporte de Agentes")
        USUARIOS = "USUARIOS", _("Reporte de Usuarios")

    tipo = models.CharField(max_length=20, choices=TiposReporte.choices)
    parametros = models.JSONField(default=dict)
    archivo = models.FileField(upload_to='reportes/', null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_completado = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tarea_celery = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Reporte"
        verbose_name_plural = "Reportes"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Reporte de {self.get_tipo_display()}"

    def generar_async(self):
        """Envía la generación del reporte a Celery"""
        from .tasks import generar_reporte_async
        
        task = generar_reporte_async.delay(self.pk)
        self.tarea_celery = task.id
        self.save()
        
        return task.id

## ----------------------------
## 7. MODELOS DE NOTIFICACIONES
## ----------------------------

class Notificacion(models.Model):
    class Tipos(models.TextChoices):
        TRANSFERENCIA = "TRANSFERENCIA", _("Transferencia")
        RECARGA = "RECARGA", _("Recarga de saldo")
        ALERTA_SEGURIDAD = "ALERTA_SEG", _("Alerta de seguridad")
        VERIFICACION = "VERIFICACION", _("Verificación requerida")
        SISTEMA = "SISTEMA", _("Mensaje del sistema")
        REPORTE = "REPORTE", _("Reporte generado")

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notificaciones_monedero")
    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    titulo = models.CharField(max_length=100)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)
    importante = models.BooleanField(default=False)
    tarea_celery = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones_Monederos"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["usuario", "leida"]),
            models.Index(fields=["tipo", "fecha"]),
        ]

    def __str__(self):
        return f"Notificación para {self.usuario.username} - {self.titulo}"

    @classmethod
    def notificar_transferencia(cls, transferencia):
        """Notifica a ambos participantes de una transferencia"""
        # Notificación al emisor
        cls.objects.create(
            usuario=transferencia.emisor,
            tipo=cls.Tipos.TRANSFERENCIA,
            titulo="Transferencia enviada",
            mensaje=f"Has enviado {transferencia.cantidad} XOF a {transferencia.receptor.username}",
            metadata={
                "referencia": str(transferencia.referencia),
                "monto": float(transferencia.cantidad),
                "comision": float(transferencia.comision)
            }
        )

        # Notificación al receptor (si no es el mismo usuario)
        if transferencia.emisor != transferencia.receptor:
            cls.objects.create(
                usuario=transferencia.receptor,
                tipo=cls.Tipos.TRANSFERENCIA,
                titulo="Transferencia recibida",
                mensaje=f"Has recibido {transferencia.cantidad} XOF de {transferencia.emisor.username}",
                metadata={
                    "referencia": str(transferencia.referencia),
                    "monto": float(transferencia.cantidad)
                }
            )

    @classmethod
    def notificar_recarga(cls, recarga):
        """Notifica al usuario sobre su recarga"""
        cls.objects.create(
            usuario=recarga.usuario,
            tipo=cls.Tipos.RECARGA,
            titulo="Recarga completada",
            mensaje=f"Se ha acreditado {recarga.monto_neto} XOF a tu monedero",
            metadata={
                "referencia": str(recarga.referencia),
                "monto_bruto": float(recarga.monto),
                "comision": float(recarga.comision_agente),
                "agente": recarga.agente.codigo_agente if recarga.agente else "Sistema"
            }
        )

    @classmethod
    def notificar_reporte(cls, reporte, usuario):
        """Notifica cuando un reporte está listo"""
        cls.objects.create(
            usuario=usuario,
            tipo=cls.Tipos.REPORTE,
            titulo=f"Reporte de {reporte.get_tipo_display()} listo",
            mensaje=f"El reporte que solicitaste está disponible para descargar.",
            metadata={
                "reporte_id": reporte.pk,
                "tipo": reporte.tipo,
                "fecha_creacion": reporte.fecha_creacion.isoformat()
            },
            tarea_celery=reporte.tarea_celery
        )

class Transaccion(models.Model):
    """Modelo extendido para integración con pedidos"""
    TIPOS = (
        ('DEBITO', 'Débito'),
        ('CREDITO', 'Crédito'),
        ('RETENCION', 'Retención'),
    )
    
    ESTADOS = (
        ('PENDIENTE', 'Pendiente'),
        ('COMPLETADA', 'Completada'),
        ('FALLIDA', 'Fallida'),
        ('REVERTIDA', 'Revertida'),
    )
    
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='transacciones')
    tipo = models.CharField(max_length=10, choices=TIPOS)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    referencia = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField()
    estado = models.CharField(max_length=10, choices=ESTADOS, default='COMPLETADA')
    metadata = JSONField(default=dict)
    relacion_contenido = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    relacion_id = models.PositiveIntegerField(null=True, blank=True)
    relacion = GenericForeignKey('relacion_contenido', 'relacion_id')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transacción'
        verbose_name_plural = 'Transacciones'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['usuario', 'tipo']),
            models.Index(fields=['referencia']),
            models.Index(fields=['relacion_contenido', 'relacion_id']),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.monto} - {self.usuario}"
    


class TransaccionRetenida(models.Model):
    """
    Modelo para gestionar retenciones de fondos en el monedero asociadas a operaciones como pedidos.
    Garantiza que los fondos estén disponibles pero no utilizables para otras operaciones.
    """
    
    class Estados(models.TextChoices):
        ACTIVA = 'ACTIVA', _('Activa')
        LIBERADA = 'LIBERADA', _('Liberada')
        APLICADA = 'APLICADA', _('Aplicada')
        CANCELADA = 'CANCELADA', _('Cancelada')
    
    referencia = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    usuario = models.ForeignKey(
        get_user_model(), 
        on_delete=models.PROTECT,
        related_name='retenciones'
    )
    monto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.ACTIVA
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_expiracion = models.DateTimeField()
    motivo = models.CharField(max_length=255)
    
    # Relación genérica con el modelo que originó la retención (ej. Pedido)
    relacion_contenido = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    relacion_id = models.PositiveIntegerField(null=True, blank=True)
    relacion = GenericForeignKey('relacion_contenido', 'relacion_id')
    
    metadata = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = 'Transacción Retenida'
        verbose_name_plural = 'Transacciones Retenidas'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['usuario', 'estado']),
            models.Index(fields=['referencia']),
            models.Index(fields=['fecha_expiracion']),
            models.Index(fields=['relacion_contenido', 'relacion_id']),
        ]
    
    def __str__(self):
        return f"Retención {self.referencia} - {self.usuario.username} ({self.monto} XOF)"
    
    def clean(self):
        if self.fecha_expiracion <= timezone.now():
            raise ValidationError("La fecha de expiración debe ser en el futuro")
        
        if self.monto <= Decimal('0.00'):
            raise ValidationError("El monto debe ser positivo")
    
    @transaction.atomic
    def liberar(self):
        """Libera los fondos retenidos sin aplicar la transacción"""
        if self.estado != self.Estados.ACTIVA:
            raise ValidationError("Solo se pueden liberar retenciones activas")
        
        monedero = self.usuario.monedero
        monedero.actualizar_saldo(
            self.monto,
            motivo=f"Liberación retención {self.referencia}",
            retener=True  # Se libera de saldo_retenido
        )
        
        self.estado = self.Estados.LIBERADA
        self.save()
        
        AuditoriaRetencion.registrar(
            retencion=self,
            accion='LIBERACION',
            detalles={
                'monto': float(self.monto),
                'saldo_actual': float(monedero.saldo),
                'saldo_retenido_actual': float(monedero.saldo_retenido)
            }
        )
    
    @transaction.atomic
    def aplicar(self):
        """Aplica la retención, debitando definitivamente los fondos"""
        if self.estado != self.Estados.ACTIVA:
            raise ValidationError("Solo se pueden aplicar retenciones activas")
        
        monedero = self.usuario.monedero
        monedero.actualizar_saldo(
            -self.monto,
            motivo=f"Aplicación retención {self.referencia}",
            retener=True  # Se descuenta de saldo_retenido
        )
        
        self.estado = self.Estados.APLICADA
        self.save()
        
        AuditoriaRetencion.registrar(
            retencion=self,
            accion='APLICACION',
            detalles={
                'monto': float(self.monto),
                'saldo_actual': float(monedero.saldo),
                'saldo_retenido_actual': float(monedero.saldo_retenido)
            }
        )
    
    @transaction.atomic
    def cancelar(self):
        """Cancela la retención y devuelve los fondos al saldo disponible"""
        if self.estado != self.Estados.ACTIVA:
            raise ValidationError("Solo se pueden cancelar retenciones activas")
        
        monedero = self.usuario.monedero
        # Primero libera de saldo_retenido
        monedero.actualizar_saldo(
            self.monto,
            motivo=f"Liberación por cancelación retención {self.referencia}",
            retener=True
        )
        # Luego acredita al saldo disponible
        monedero.actualizar_saldo(
            self.monto,
            motivo=f"Cancelación retención {self.referencia}"
        )
        
        self.estado = self.Estados.CANCELADA
        self.save()
        
        AuditoriaRetencion.registrar(
            retencion=self,
            accion='CANCELACION',
            detalles={
                'monto': float(self.monto),
                'saldo_actual': float(monedero.saldo),
                'saldo_retenido_actual': float(monedero.saldo_retenido)
            }
        )
    
    @classmethod
    @transaction.atomic
    def crear_retencion(cls, usuario, monto, motivo, relacion_obj=None, dias_expiracion=3):
        """
        Crea una nueva retención de fondos de forma segura.
        
        Args:
            usuario: Usuario dueño del monedero
            monto: Monto a retener (Decimal)
            motivo: Descripción de la retención
            relacion_obj: Objeto relacionado (ej. Pedido)
            dias_expiracion: Días hasta la expiración automática
        
        Returns:
            TransaccionRetenida creada
        """
        monedero = usuario.monedero
        
        # Verificar saldo disponible
        if monedero.saldo_disponible < monto:
            raise ValidationError("Saldo insuficiente para la retención")
        
        # Crear la retención
        retencion = cls(
            usuario=usuario,
            monto=monto,
            motivo=motivo,
            fecha_expiracion=timezone.now() + timezone.timedelta(days=dias_expiracion)
        )
        
        if relacion_obj:
            retencion.relacion_contenido = ContentType.objects.get_for_model(relacion_obj)
            retencion.relacion_id = relacion_obj.pk
        
        retencion.full_clean()
        retencion.save()
        
        # Actualizar el monedero (retener fondos)
        monedero.actualizar_saldo(
            -monto,
            motivo=f"Retención {retencion.referencia}: {motivo}",
            retener=False  # Se descuenta de saldo y suma a saldo_retenido
        )
        
        AuditoriaRetencion.registrar(
            retencion=retencion,
            accion='CREACION',
            detalles={
                'monto': float(monto),
                'saldo_actual': float(monedero.saldo),
                'saldo_retenido_actual': float(monedero.saldo_retenido)
            }
        )
        
        return retencion

class AuditoriaRetencion(models.Model):
    """
    Auditoría para registrar todas las acciones sobre retenciones
    """
    retencion = models.ForeignKey(
        TransaccionRetenida,
        on_delete=models.CASCADE,
        related_name='auditorias'
    )
    accion = models.CharField(max_length=50)
    fecha = models.DateTimeField(auto_now_add=True)
    detalles = models.JSONField(default=dict)
    error = models.TextField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Auditoría de Retención'
        verbose_name_plural = 'Auditorías de Retenciones'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['retencion', 'accion']),
            models.Index(fields=['fecha']),
        ]
    
    @classmethod
    def registrar(cls, retencion, accion, detalles=None, error=None):
        return cls.objects.create(
            retencion=retencion,
            accion=accion,
            detalles=detalles or {},
            error=error
        )