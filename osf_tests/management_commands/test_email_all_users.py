import mock
import pytest

from osf_tests.factories import UserFactory
from website import mails

from osf.management.commands.email_all_users import email_all_users

@pytest.mark.django_db
class TestEmailAllUsers:

    @pytest.fixture()
    def superuser(self):
        user = UserFactory()
        user.is_superuser = True
        user.save()
        return user

    @mock.patch('website.mails.send_mail')
    def test_email_all_users(self, mock_email, superuser):
        email_all_users('TOU_NOTIF', dry_run=True)

        mock_email.assert_called_with(
            to_addr=superuser.email,
            mail=mails.TOU_NOTIF,
            fullname=superuser.fullname
        )
