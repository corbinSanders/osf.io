# -*- coding: utf-8 -*-
# This is a management command, rather than a migration script, for two primary reasons:
#   1. It makes no changes to database structure (e.g. AlterField), only database content.
#   2. It takes a long time to run and the site doesn't need to be down that long.

from __future__ import unicode_literals
import logging

import django
django.setup()

from django.core.management.base import BaseCommand
from framework.celery_tasks import app as celery_app

from website import mails

from osf.models import OSFUser

logger = logging.getLogger(__name__)

@celery_app.task(name='management.commands.email_all_users')
def email_all_users(email_template, dry_run=False):

    active_users = OSFUser.objects.filter(date_confirmed__isnull=False).exclude(date_disabled__isnull=False).exclude(is_active=False).order_by('id')

    if dry_run:
        active_users = active_users.exclude(is_superuser=False)

    total_active_users = active_users.count()

    logger.info(f'About to send an email to {total_active_users} users.')

    template = getattr(mails, email_template, None)
    if not template:
        raise RuntimeError('Invalid email template specified!')

    total_sent = 0
    for user in active_users.iterator():
        mails.send_mail(
            to_addr=user.email,
            mail=template,
            fullname=user.fullname,
        )
        total_sent += 1

    logger.info(f'Emails sent to {total_sent}/{total_active_users} users')


class Command(BaseCommand):
    """
    Add subscription to all active users for given notification type.
    """
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--dry',
            action='store_true',
            dest='dry_run',
            help='Test - Only send to superusers',
        )

        parser.add_argument(
            '--t',
            action='store_true',
            dest='template',
            required=True,
            help='Specify which template to use',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        template = options.get('template')
        email_all_users(template, dry_run)
        if dry_run:
            raise RuntimeError('Dry run, only superusers emailed')
