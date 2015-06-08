from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
import rest_framework.authentication
from rest_framework import exceptions

import nodeconductor.logging.middleware


TOKEN_KEY = 'x-auth-token'


class TokenAuthentication(rest_framework.authentication.TokenAuthentication):
    """
    Custom token-based authentication.

    Use TOKEN_KEY from request query parameters if authentication token was not found in header.
    """

    def get_authorization_value(self, request):
        auth = rest_framework.authentication.get_authorization_header(request)
        if not auth:
            auth = request.query_params.get(TOKEN_KEY, '')
        return auth

    def authenticate(self, request):
        auth = self.get_authorization_value(request).split()

        if not auth or auth[0].lower() != b'token':
            return None

        if len(auth) == 1:
            msg = _('Invalid token. No credentials provided.')
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = _('Invalid token. Token string should not contain spaces.')
            raise exceptions.AuthenticationFailed(msg)

        return self.authenticate_credentials(auth[1])


def user_capturing_auth(auth):
    class CapturingAuthentication(auth):
        def authenticate(self, request):
            result = super(CapturingAuthentication, self).authenticate(request)
            if result is not None:
                user, _ = result
                nodeconductor.logging.middleware.set_current_user(user)
            return result

    return CapturingAuthentication

SessionAuthentication = user_capturing_auth(rest_framework.authentication.SessionAuthentication)
TokenAuthentication = user_capturing_auth(TokenAuthentication)
