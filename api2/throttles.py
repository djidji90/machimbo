from rest_framework.throttling import UserRateThrottle

class UploadThrottle(UserRateThrottle):
    scope = 'upload'
    rate = '10/hour'
    
    def allow_request(self, request, view):
        if request.method.lower() in ['post', 'put', 'patch']:
            return super().allow_request(request, view)
        return True