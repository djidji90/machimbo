from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _
from datetime import date


class CustomUser(AbstractUser):
    GENDER_CHOICES = [
        ('M', _('Masculino')),
        ('F', _('Femenino')),
        ('O', _('Otro')),
    ]

    first_name = models.CharField(_("Nombre"), max_length=200, blank=True)
    last_name = models.CharField(_("Apellido"), max_length=100, blank=True)
    email = models.EmailField(_("Correo electrónico"), unique=True)
    phone = models.CharField(_("Teléfono"), max_length=15, blank=True)
    city = models.CharField(_("Ciudad"), max_length=100, blank=True)
    neighborhood = models.CharField(_("Barrio"), max_length=100, blank=True)

    gender = models.CharField(_("Género"), max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    birth_date = models.DateField(_("Fecha de nacimiento"), blank=True, null=True)
    profile_image = models.ImageField(_("Foto de perfil"), upload_to='profiles/', blank=True, null=True)
    country = models.CharField(_("País"), max_length=100, blank=True)
    terms_accepted = models.BooleanField(_("Aceptó los términos"), default=False)

    # Verificación de cuenta
    is_verified = models.BooleanField(_("Verificado"), default=False)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    groups = models.ManyToManyField(Group, related_name="custom_users", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="custom_users_permissions", blank=True)

    def __str__(self):
        return self.email

    @property
    def age(self):
        if self.birth_date:
            today = date.today()
            return today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
        return None


class VerificationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', _('Pendiente')),
        ('approved', _('Aprobado')),
        ('rejected', _('Rechazado')),
    ]

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="verification_request")
    document = models.FileField(_("Documento"), upload_to='verification_documents/', blank=True, null=True)
    links = models.TextField(_("Enlaces oficiales"), blank=True, null=True, help_text=_("Redes sociales, sitio web, etc."))
    status = models.CharField(_("Estado"), max_length=10, choices=STATUS_CHOICES, default='pending')
    feedback = models.TextField(_("Comentarios de revisión"), blank=True, null=True)
    requested_at = models.DateTimeField(_("Fecha de solicitud"), auto_now_add=True)
    reviewed_at = models.DateTimeField(_("Fecha de revisión"), blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} - {self.get_status_display()}"


class UserVisit(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="visitas")
    ip = models.GenericIPAddressField()
    ciudad = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    pais = models.CharField(max_length=100, blank=True, null=True)
    latitud = models.CharField(max_length=50, blank=True, null=True)
    longitud = models.CharField(max_length=50, blank=True, null=True)
    proveedor = models.CharField(max_length=200, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    navegador = models.CharField(max_length=100, blank=True, null=True)
    sistema_operativo = models.CharField(max_length=100, blank=True, null=True)
    es_recurrente = models.BooleanField(default=False)
    url_referencia = models.URLField(blank=True, null=True)
    fecha_visita = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ip} - {self.pais} ({self.ciudad}) - {self.fecha_visita}"


class UserMedia(models.Model):
    MEDIA_CHOICES = [
        ('audio', _('Audio')),
        ('image', _('Imagen')),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    media_type = models.CharField(_("Tipo de archivo"), max_length=10, choices=MEDIA_CHOICES)
    file = models.FileField(_("Archivo"), upload_to='user_media/')
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.media_type}"
