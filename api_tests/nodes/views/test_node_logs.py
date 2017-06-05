import pytest
import urlparse
import pytz
import datetime

from dateutil.parser import parse as parse_date

from framework.auth.core import Auth
from osf.models import NodeLog
from website.util import disconnected_from_listeners
from website.project.signals import contributor_removed
from api.base.settings.defaults import API_BASE
from tests.json_api_test_app import JSONAPITestApp
from tests.base import ApiTestCase, assert_datetime_equal
from osf_tests.factories import (
    ProjectFactory,
    AuthUserFactory,
)

API_LATEST = 0
API_FIRST = -1

@pytest.fixture()
def user():
    return AuthUserFactory()

@pytest.mark.django_db
class TestNodeLogList:

    @pytest.fixture()
    def contrib(self):
        return AuthUserFactory()

    @pytest.fixture()
    def creator(self):
        return AuthUserFactory()

    @pytest.fixture()
    def user_auth(self, user):
        return Auth(user)

    @pytest.fixture()
    def NodeLogFactory(self):
        return ProjectFactory()

    @pytest.fixture()
    def pointer(self):
        return ProjectFactory()

    @pytest.fixture()
    def private_project(self, user):
        return ProjectFactory(is_public=False, creator=user)

    @pytest.fixture()
    def private_url(self, private_project):
        return '/{}nodes/{}/logs/?version=2.2'.format(API_BASE, private_project._id)

    @pytest.fixture()
    def public_project(self, user):
        return ProjectFactory(is_public=True, creator=user)

    @pytest.fixture()
    def public_url(self, public_project):
        return '/{}nodes/{}/logs/?version=2.2'.format(API_BASE, public_project._id)

    def test_add_tag(self, app, user, user_auth, public_project, public_url):
        public_project.add_tag('Rheisen', auth=user_auth)
        assert 'tag_added' == public_project.logs.latest().action
        res = app.get(public_url, auth=user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == public_project.logs.count()
        assert res.json['data'][API_LATEST]['attributes']['action'] == 'tag_added'
        assert 'Rheisen' == public_project.logs.latest().params['tag']

    def test_remove_tag(self, app, user, user_auth, public_project, public_url):
        public_project.add_tag('Rheisen', auth=user_auth)
        assert 'tag_added' == public_project.logs.latest().action
        public_project.remove_tag('Rheisen', auth=user_auth)
        assert 'tag_removed' == public_project.logs.latest().action
        res = app.get(public_url, auth=user)
        assert res.status_code == 200
        assert len(res.json['data']) == public_project.logs.count()
        assert res.json['data'][API_LATEST]['attributes']['action'] == 'tag_removed'
        assert 'Rheisen' == public_project.logs.latest().params['tag']

    def test_project_creation(self, app, user, public_project, private_project, public_url, private_url):

    #   test_project_created
        res = app.get(public_url)
        assert res.status_code == 200
        assert len(res.json['data']) == public_project.logs.count()
        assert public_project.logs.first().action == 'project_created'
        assert public_project.logs.first().action == res.json['data'][API_LATEST]['attributes']['action']

    #   test_log_create_on_public_project
        res = app.get(public_url)
        assert res.status_code == 200
        assert len(res.json['data']) == public_project.logs.count()
        assert_datetime_equal(parse_date(res.json['data'][API_FIRST]['attributes']['date']),
                              public_project.logs.first().date)
        assert res.json['data'][API_FIRST]['attributes']['action'] == public_project.logs.first().action

    #   test_log_create_on_private_project
        res = app.get(private_url, auth=user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == public_project.logs.count()
        assert_datetime_equal(parse_date(res.json['data'][API_FIRST]['attributes']['date']),
                              private_project.logs.first().date)
        assert res.json['data'][API_FIRST]['attributes']['action'] == private_project.logs.first().action

    def test_add_addon(self, app, user, user_auth, public_project, public_url):
        public_project.add_addon('github', auth=user_auth)
        assert 'addon_added' == public_project.logs.latest().action
        res = app.get(public_url, auth=user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == public_project.logs.count()
        assert res.json['data'][API_LATEST]['attributes']['action'] == 'addon_added'

    def test_project_add_remove_contributor(self, app, user, contrib, user_auth, public_project, public_url):
        public_project.add_contributor(contrib, auth=user_auth)
        assert 'contributor_added' == public_project.logs.latest().action
        # Disconnect contributor_removed so that we don't check in files
        # We can remove this when StoredFileNode is implemented in osf-models
        with disconnected_from_listeners(contributor_removed):
            public_project.remove_contributor(contrib, auth=user_auth)
        assert 'contributor_removed' == public_project.logs.latest().action
        res = app.get(public_url, auth=user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == public_project.logs.count()
        assert res.json['data'][API_LATEST]['attributes']['action'] == 'contributor_removed'
        assert res.json['data'][1]['attributes']['action'] == 'contributor_added'

    def test_remove_addon(self, app, user, user_auth, public_project, public_url):
        public_project.add_addon('github', auth=user_auth)
        assert 'addon_added' == public_project.logs.latest().action
        old_log_length = len(list(public_project.logs.all()))
        public_project.delete_addon('github', auth=user_auth)
        assert 'addon_removed' == public_project.logs.latest().action
        assert (public_project.logs.count() - 1) == old_log_length
        res = app.get(public_url, auth=user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == public_project.logs.count()
        assert res.json['data'][API_LATEST]['attributes']['action'] == 'addon_removed'

    def test_add_pointer(self, app, user_auth, public_project, pointer, public_url):
        public_project.add_pointer(pointer, auth=user_auth, save=True)
        assert 'pointer_created' == public_project.logs.latest().action
        res = app.get(public_url, auth=user_auth)
        assert res.status_code == 200
        assert len(res.json['data']) == public_project.logs.count()
        assert res.json['data'][API_LATEST]['attributes']['action'] == 'pointer_created'

@pytest.mark.django_db
class TestNodeLogFiltering(TestNodeLogList):

    def test_filter_action_not_equal(self, app, user, user_auth, public_project):
        public_project.add_tag('Rheisen', auth=user_auth)
        assert 'tag_added' == public_project.logs.latest().action
        url = '/{}nodes/{}/logs/?filter[action][ne]=tag_added'.format(API_BASE, public_project._id)
        res = app.get(url, auth=user.auth)
        assert len(res.json['data']) == 1
        assert res.json['data'][0]['attributes']['action'] == 'project_created'

    def test_filter_date_not_equal(self, app, user, public_project, pointer):
        public_project.add_pointer(pointer, auth=Auth(user), save=True)
        assert 'pointer_created' == public_project.logs.latest().action
        assert public_project.logs.count() == 2

        pointer_added_log = public_project.logs.get(action='pointer_created')
        date_pointer_added = str(pointer_added_log.date).split('+')[0].replace(' ', 'T')

        url = '/{}nodes/{}/logs/?filter[date][ne]={}'.format(API_BASE, public_project._id, date_pointer_added)
        res = app.get(url, auth=user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == 1
        assert res.json['data'][0]['attributes']['action'] == 'project_created'
