import json
import uuid
import logging

import jwe
import jwt
import waffle

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from api.base.authentication import drf
from api.base import exceptions, settings

from framework import sentry
from framework.auth import get_or_create_user

from osf.features import flags
from osf.models import Institution

from website.mails import send_mail, WELCOME_OSF4I
from website.settings import OSF_SUPPORT_EMAIL, DOMAIN

logger = logging.getLogger(__name__)


class InstitutionAuthentication(BaseAuthentication):
    """A dedicated authentication class for view ``InstitutionAuth``.

    The ``InstitutionAuth`` view and the ``InstitutionAuthentication`` class are only and should
    only be used by OSF CAS for institution login. Changing this class and related tests may break
    the institution login feature. Please check with @longzeC / @mattF / @brianG before making any
    changes.
    """

    media_type = 'text/plain'

    def authenticate(self, request):
        """
        Handle CAS institution authentication request.

        The JWT `data` payload is expected in the following structure:
        {
            "provider": {
                "idp":  "",
                "id":   "",
                "user": {
                    "username":     "",
                    "fullname":     "",
                    "familyName":   "",
                    "givenName":    "",
                    "middleNames":  "",
                    "suffix":       "",
                }
            }
        }

        :param request: the POST request
        :return: user, None if authentication succeed
        :raises: AuthenticationFailed if authentication fails
        """

        # Verify / decrypt / decode the payload
        try:
            payload = jwt.decode(
                jwe.decrypt(request.body, settings.JWE_SECRET),
                settings.JWT_SECRET,
                options={'verify_exp': False},
                algorithm='HS256',
            )
        except (jwt.InvalidTokenError, TypeError, jwe.exceptions.MalformedData):
            raise AuthenticationFailed

        # Load institution and user data
        data = json.loads(payload['data'])
        provider = data['provider']
        institution = Institution.load(provider['id'])
        if not institution:
            raise AuthenticationFailed('Invalid institution id: "{}"'.format(provider['id']))
        username = provider['user'].get('username')
        fullname = provider['user'].get('fullname')
        given_name = provider['user'].get('givenName')
        family_name = provider['user'].get('familyName')
        middle_names = provider['user'].get('middleNames')
        suffix = provider['user'].get('suffix')

        # Use given name and family name to build full name if it is not provided
        if given_name and family_name and not fullname:
            fullname = given_name + ' ' + family_name

        # Non-empty full name is required. Fail the auth and inform sentry if not provided.
        if not fullname:
            message = 'Institution login failed: fullname required for ' \
                      'user "{}" from institution "{}"'.format(username, provider['id'])
            sentry.log_message(message)
            raise AuthenticationFailed(message)

        # Get an existing user or create a new one. If a new user is created, the user object is
        # confirmed but not registered,which is temporarily of an inactive status. If an existing
        # user is found, it is also possible that the user is inactive (e.g. unclaimed, disabled,
        # unconfirmed, etc.).
        user, created = get_or_create_user(fullname, username, reset_password=False)

        # Existing but inactive users need to be either "activated" or failed the auth
        activation_required = False
        new_password_required = False
        if not created:
            try:
                drf.check_user(user)
                logger.info('Institution SSO: active user "{}"'.format(username))
            except exceptions.UnclaimedAccountError:
                # Unclaimed user (i.e. a user that has been added as an unregistered contributor)
                user.unclaimed_records = {}
                activation_required = True
                # Unclaimed users have an unusable password when being added as an unregistered
                # contributor. Thus a random usable password must be assigned during activation.
                new_password_required = True
                logger.info('Institution SSO: unclaimed contributor "{}"'.format(username))
            except exceptions.UnconfirmedAccountError:
                if user.has_usable_password():
                    # Unconfirmed user from default username / password signup
                    user.email_verifications = {}
                    activation_required = True
                    # Unconfirmed users already have a usable password set by the creator during
                    # sign-up. However, it must be overwritten by a new random one so the creator
                    # (if he is not the real person) can not access the account after activation.
                    new_password_required = True
                    logger.info('Institution SSO: unconfirmed user "{}"'.format(username))
                else:
                    # Login take-over has not been implemented for unconfirmed user created via
                    # external IdP login (ORCiD).
                    message = 'Institution SSO is not eligible for an unconfirmed account ' \
                              'created via external IdP login: username = "{}"'.format(username)
                    sentry.log_message(message)
                    logger.error(message)
                    return None, None
            except exceptions.DeactivatedAccountError:
                # Deactivated user: login is not allowed for deactivated users
                message = 'Institution SSO is not eligible for a deactivated account: ' \
                          'username = "{}"'.format(username)
                sentry.log_message(message)
                logger.error(message)
                return None, None
            except exceptions.MergedAccountError:
                # Merged user: this shouldn't happen since merged users do not have an email
                message = 'Institution SSO is not eligible for a merged account: ' \
                          'username = "{}"'.format(username)
                sentry.log_message(message)
                logger.error(message)
                return None, None
            except exceptions.InvalidAccountError:
                # Other invalid status: this shouldn't happen unless the user happens to be in a
                # temporary state. Such state requires more updates before the user can be saved
                # to the database. (e.g. `get_or_create_user()` creates a temporary-state user.)
                message = 'Institution SSO is not eligible for an inactive account with ' \
                          'an unknown or invalid status: username = "{}"'.format(username)
                sentry.log_message(message)
                logger.error(message)
                return None, None
        else:
            logger.info('Institution SSO: new user "{}"'.format(username))

        # Both created and activated accounts need to be updated and registered
        if created or activation_required:

            if given_name:
                user.given_name = given_name
            if family_name:
                user.family_name = family_name
            if middle_names:
                user.middle_names = middle_names
            if suffix:
                user.suffix = suffix

            # Users claimed or confirmed via institution SSO should have their full name updated
            if activation_required:
                user.fullname = fullname

            user.update_date_last_login()

            # Relying on front-end validation until `accepted_tos` is added to the JWT payload
            user.accepted_terms_of_service = timezone.now()

            # Register and save user
            password = str(uuid.uuid4()) if new_password_required else None
            user.register(username, password=password)
            user.save()

            # Send confirmation email for all three: created, confirmed and claimed
            send_mail(
                to_addr=user.username,
                mail=WELCOME_OSF4I,
                mimetype='html',
                user=user,
                domain=DOMAIN,
                osf_support_email=OSF_SUPPORT_EMAIL,
                storage_flag_is_active=waffle.flag_is_active(request, flags['STORAGE_I18N']),
            )

        # Affiliate the user if not previously affiliated
        if not user.is_affiliated_with_institution(institution):
            user.affiliated_institutions.add(institution)
            user.save()

        return user, None
