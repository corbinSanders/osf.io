# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from osf.features import switches
from osf.utils.migrations import AddWaffleSwitches


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0143_merge_20181115_1458'),
    ]

    operations = [
        AddWaffleSwitches([switches['OSF_PREREGISTRATION']], active=False),
    ]
