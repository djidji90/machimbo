from django import forms

from monedero.models import Agente


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
                raise forms.ValidationError("Los PINs no coinciden")
            
            if len(pin_nuevo) != 6 or not pin_nuevo.isdigit():
                raise forms.ValidationError("El PIN debe tener exactamente 6 dígitos numéricos")
        
        return cleaned_data