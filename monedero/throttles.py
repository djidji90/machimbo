# monedero/throttles.py
from rest_framework.throttling import UserRateThrottle

class DeviceRegistrationRateThrottle(UserRateThrottle):
    scope = 'device_registration'
    rate = '5/hour'