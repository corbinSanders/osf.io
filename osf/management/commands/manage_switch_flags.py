# -*- coding: utf-8 -*-
import logging

from django.core.management.base import BaseCommand

from osf.features import switches, flags
from waffle.models import Flag, Switch

logger = logging.getLogger(__name__)

def manage_waffle():
    file_switches = [switches[switch] for switch in switches]
    current_switches = Switch.objects.values_list('name', flat=True)

    add_switches = set(file_switches) - set(current_switches)
    for switch in add_switches:
        Switch.objects.get_or_create(name=switch, defaults={'active': False})
        logger.info('Adding switch: {}'.format(switch))

    delete_switches = set(current_switches) - set(file_switches)
    Switch.objects.filter(name__in=delete_switches).delete()
    logger.info('Deleting switches: {}'.format(delete_switches))

    file_flags = [flags[flag] for flag in flags]
    current_flags = Flag.objects.values_list('name', flat=True)

    add_flags = set(file_flags) - set(current_flags)
    for flag_name in add_flags:
        Flag.objects.get_or_create(name=flag_name, defaults={'everyone': False})
        logger.info('Adding flag: {}'.format(flag_name))

    delete_flags = set(current_flags) - set(file_flags)
    Flag.objects.filter(name__in=delete_flags).delete()
    logger.info('Deleting flags: {}'.format(delete_flags))

class Command(BaseCommand):
    """Ensure all features and switches are updated with the switch and flag files
    """

    def handle(self, *args, **options):
        manage_waffle()
