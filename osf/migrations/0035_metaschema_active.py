# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-06-05 18:58
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0034_rename_email_user_relation'),
    ]

    operations = [
        migrations.AddField(
            model_name='metaschema',
            name='active',
            field=models.BooleanField(default=True),
        ),
    ]
