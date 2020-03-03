# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations

from osf.features import flags
from osf.utils.migrations import AddWaffleFlags


class Migration(migrations.Migration):
    dependencies = [
        ('osf', '0156_create_cache_table'),
    ]

    operations = [
        AddWaffleFlags([flags['STORAGE_USAGE']]),
    ]
