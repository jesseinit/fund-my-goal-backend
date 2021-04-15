from rest_framework import exceptions, permissions

from utils.helpers import retrieve_from_redis


class IsTokenBlackListed(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.headers.get("authorization"):
            try:
                token = "".join(request.headers.get("authorization").split())[6:]
                user_id = request.user.id
                black_listed_tokens = retrieve_from_redis('blacklisted_tokens')
                if black_listed_tokens is not None:
                    invalid_tokens = [
                        invalid_token['token'] for invalid_token in black_listed_tokens
                        if invalid_token['user_id'] == user_id
                    ]
                    if token in invalid_tokens:
                        raise exceptions.PermissionDenied({
                            'error':
                            'BlacklistedToken',
                            'message':
                            'Session has expired. Please login again.'
                        })
                    else:
                        return True
                else:
                    return True
            except (KeyError, IndexError):
                raise exceptions.PermissionDenied({
                    'error':
                    'You do not have permission to perform this action.',
                    'message':
                    'Session has expired. Please login again.'
                })
        else:
            return False


class AllowListRetrieveOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user.is_authenticated is not True:
            if view.action in ['list', 'retrieve']:
                return True
            else:
                raise exceptions.PermissionDenied({
                    'error': 'You do not have permission to perform this action.',
                    'status': 403
                })
        return True
