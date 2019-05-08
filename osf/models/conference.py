# -*- coding: utf-8 -*-
import urlparse

from django.db import models
from django.contrib.contenttypes.models import ContentType
from addons.osfstorage.models import OsfStorageFile
from osf.models.base import BaseModel, ObjectIDMixin
from osf.models import Tag, AbstractNode
from osf.utils.datetime_aware_jsonfield import DateTimeAwareJSONField
from osf.utils.fields import NonNaiveDateTimeField

from website.conferences.exceptions import ConferenceError
from website import settings

# leaving this at module scope for any existing imports.
DEFAULT_FIELD_NAMES = {
    'submission1': 'poster',
    'submission2': 'talk',
    'submission1_plural': 'posters',
    'submission2_plural': 'talks',
    'meeting_title_type': 'Posters & Talks',
    'add_submission': 'poster or talk',
    'mail_subject': 'Presentation title',
    'mail_message_body': 'Presentation abstract (if any)',
    'mail_attachment': 'Your presentation file (e.g., PowerPoint, PDF, etc.)',
    'homepage_link_text': 'Conference homepage',
}

def get_default_field_names():
    return DEFAULT_FIELD_NAMES


class ConferenceManager(models.Manager):
    def get_by_endpoint(self, endpoint, active=True):
        try:
            if active:
                return self.get_queryset().get(endpoint__iexact=endpoint, active=True)
            else:
                return self.get_queryset().get(endpoint__iexact=endpoint)
        except Conference.DoesNotExist:
            raise ConferenceError('Endpoint {} not found'.format(endpoint))


class Conference(ObjectIDMixin, BaseModel):
    #: Determines the email address for submission and the OSF url
    # Example: If endpoint is spsp2014, then submission email will be
    # spsp2014-talk@osf.io or spsp2014-poster@osf.io and the OSF url will
    # be osf.io/view/spsp2014
    endpoint = models.CharField(max_length=255, unique=True, db_index=True)
    #: Full name, e.g. "SPSP 2014"
    name = models.CharField(max_length=255)
    info_url = models.URLField(blank=True)
    logo_url = models.URLField(blank=True)
    location = models.CharField(max_length=2048, null=True, blank=True)
    start_date = NonNaiveDateTimeField(blank=True, null=True)
    end_date = NonNaiveDateTimeField(blank=True, null=True)
    is_meeting = models.BooleanField(default=True)
    active = models.BooleanField()
    admins = models.ManyToManyField('OSFUser')
    #: Whether to make submitted projects public
    public_projects = models.BooleanField(default=True)
    poster = models.BooleanField(default=True)
    talk = models.BooleanField(default=True)
    # field_names are used to customize the text on the conference page, the categories
    # of submissions, and the email adress to send material to.
    field_names = DateTimeAwareJSONField(default=get_default_field_names)

    # Cached number of submissions
    num_submissions = models.IntegerField(default=0)

    objects = ConferenceManager()

    def __repr__(self):
        return (
            '<Conference(endpoint={self.endpoint!r}, active={self.active})>'.format(self=self)
        )

    @classmethod
    def get_by_endpoint(cls, endpoint, active):
        return cls.objects.get_by_endpoint(endpoint, active)

    @property
    def absolute_url(self):
        return urlparse.urljoin(settings.DOMAIN, '/view/{}'.format(self.endpoint))

    @property
    def submissions(self):
        """
        Returns the number of valid conference submissions with at least one file attached
        """
        tags = Tag.objects.filter(system=False, name__iexact=self.endpoint).values_list('pk', flat=True)
        files = OsfStorageFile.objects.filter(
            target_object_id=models.OuterRef('pk'),
            target_content_type_id=ContentType.objects.get_for_model(AbstractNode).id,
        )
        return AbstractNode.objects.filter(tags__in=tags, is_public=True, is_deleted=False).annotate(
            has_files=models.Exists(files)
        ).filter(
            has_files=True
        )

    class Meta:
        # custom permissions for use in the OSF Admin App
        permissions = (
            ('view_conference', 'Can view conference details in the admin app.'),
        )


class MailRecord(ObjectIDMixin, BaseModel):
    data = DateTimeAwareJSONField()
    nodes_created = models.ManyToManyField('Node')
    users_created = models.ManyToManyField('OSFUser')
