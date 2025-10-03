class MonederoError(Exception):
    """Base exception for monedero app"""
    default_detail = "Error en operación de monedero"

class SaldoInsuficienteError(MonederoError):
    default_detail = "Saldo insuficiente para realizar la operación"

class LimiteDiarioExcedidoError(MonederoError):
    default_detail = "Límite diario de operaciones excedido"

class DispositivoNoAutorizadoError(MonederoError):
    default_detail = "Dispositivo no autorizado para esta operación"

class PinIncorrectoError(MonederoError):
    default_detail = "PIN incorrecto"
    def __init__(self, intentos_restantes):
        self.intentos_restantes = intentos_restantes