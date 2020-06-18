import os
import json
import logging
import sys

from django.db import transaction
from django.apps import apps

from scripts import utils as script_utils
from scripts.populate_preprint_providers import update_or_create
from osf.models import PreprintProvider, Subject
from website.app import init_app
from website import settings


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def add_subjects_to_bodorxiv():
    bodoarxiv = PreprintProvider.objects.get(_id='bodoarxiv')

    bepress_subject = Subject.objects.get(text='Digital Humanities', provider___id='osf')
    digital_scholarship = Subject(text='Digital Scholarship', provider=bodoarxiv, bepress_subject=bepress_subject)
    digital_scholarship.save()

    bodoarxiv.save()

def main():
    init_app(set_backends=True, routes=False)
    dry_run = '--dry' in sys.argv
    if not dry_run:
        script_utils.add_file_logger(logger, __file__)
    with transaction.atomic():
        add_subjects_to_bodorxiv()
        if dry_run:
            raise RuntimeError('Dry run, transaction rolled back')

if __name__ == '__main__':
    main()
