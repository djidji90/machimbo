from rest_framework import serializers
from django.contrib.auth import get_user_model
from datetime import date
from .models import CustomUser, UserVisit, VerificationRequest

CustomUser = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, label="Confirmar contraseña")
    terms_accepted = serializers.BooleanField()

    class Meta:
        model = CustomUser
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'city',
            'neighborhood',
            'gender',
            'birth_date',
            'country',
            'password',
            'password2',
            'terms_accepted',
        ]

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este correo ya está registrado.")
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Las contraseñas no coinciden."})

        if not data.get('terms_accepted'):
            raise serializers.ValidationError({"terms_accepted": "Debes aceptar los términos para continuar."})

        birth_date = data.get('birth_date')
        if birth_date:
            today = date.today()
            age = today.year - birth_date.year - (
                (today.month, today.day) < (birth_date.month, birth_date.day)
            )
            if age < 13:
                raise serializers.ValidationError({"birth_date": "Debes tener al menos 13 años para registrarte."})

        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    age = serializers.ReadOnlyField()
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'city',
            'neighborhood',
            'gender',
            'birth_date',
            'country',
            'profile_image',
            'is_verified',
            'age',
        ]


class VerificationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationRequest
        fields = [
            'id',
            'document',
            'links',
            'status',
            'feedback',
            'requested_at',
            'reviewed_at',
        ]
        read_only_fields = ['status', 'feedback', 'requested_at', 'reviewed_at']

    def create(self, validated_data):
        user = self.context['request'].user
        if hasattr(user, "verification_request"):
            raise serializers.ValidationError("Ya has enviado una solicitud de verificación.")
        return VerificationRequest.objects.create(user=user, **validated_data)


class VerificationRequestAdminSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = VerificationRequest
        fields = [
            'id',
            'user',
            'document',
            'links',
            'status',
            'feedback',
            'requested_at',
            'reviewed_at',
        ]


class UserVisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserVisit
        fields = '__all__'
