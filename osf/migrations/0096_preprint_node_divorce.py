# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-03-12 18:25
from __future__ import unicode_literals

from django.contrib.auth.models import Group
from django.db import migrations
from django.db.models import F
from django.db.models import OuterRef, Subquery
from guardian.shortcuts import assign_perm, get_perms, remove_perm
from django.core.management.sql import emit_post_migrate_signal
from osf.models import OSFUser


from itertools import islice, chain

from itertools import islice, chain

def batch(iterable, size):
    sourceiter = iter(iterable)
    while True:
        batchiter = islice(sourceiter, size)
        yield chain([batchiter.next()], batchiter)


def divorce_preprints_from_nodes(apps, schema_editor):
    # this is to make sure that the permissions created earlier exist!
    emit_post_migrate_signal(2, False, 'default')

    Preprint = apps.get_model('osf', 'Preprint')
    AbstractNode = apps.get_model('osf', 'AbstractNode')
    PreprintContributor = apps.get_model('osf', 'PreprintContributor')

    node_subquery = AbstractNode.objects.filter(preprints=OuterRef('pk')).order_by('-created')
    Preprint.objects.annotate(
        node_title=Subquery(node_subquery.values('title')[:1])).annotate(
        node_description=Subquery(node_subquery.values('description')[:1])).annotate(
        node_creator=Subquery(node_subquery.values('creator')[:1])).update(
        title=F('node_title'),
        description=F('node_description'),
        creator=F('node_creator')
    )

    contributors = []

    for preprint in Preprint.objects.filter(node__isnull=False).select_related('node'):
        # use bulk create
        admin = []
        write = []
        read = []
        for contrib in preprint.node.contributor_set.all():
            # make a PreprintContributor that points to the pp instead of the node
            # because there's a throughtable, relations are designated
            # solely on the through model, and adds on the related models
            # are not required.

            new_contrib = PreprintContributor(
                preprint_id=preprint.id,
                user_id=contrib.user.id,
                visible=contrib.visible,
                _order=contrib._order
            )
            contributors.append(new_contrib)
            if contrib.admin:
                admin.append(contrib.user)
            elif contrib.write:
                write.append(contrib.user)
            else:
                read.append(contrib.user)

        update_group_permissions(preprint)

        add_users_to_group(Group.objects.get(name=format_group(preprint, 'admin')), admin)
        add_users_to_group(Group.objects.get(name=format_group(preprint, 'write')), write)
        add_users_to_group(Group.objects.get(name=format_group(preprint, 'read')), read)

        preprint.save()

    batch_size = 1000
    for batchiter in batch(contributors, batch_size):
        PreprintContributor.objects.bulk_create(batchiter)


group_format = 'preprint_{self.id}_{group}'

def format_group(self, name):
    return group_format.format(self=self, group=name)

def update_group_permissions(self):
    for group_name, group_permissions in groups.items():
        group, created = Group.objects.get_or_create(name=format_group(self, group_name))
        to_remove = set(get_perms(group, self)).difference(group_permissions)
        for p in to_remove:
            remove_perm(p, group, self)
        for p in group_permissions:
            assign_perm(p, group, self)

groups = {
    'read': ('read_preprint',),
    'write': ('read_preprint', 'write_preprint',),
    'admin': ('read_preprint', 'write_preprint', 'admin_preprint',)
}

def add_users_to_group(group, user_list):
    for user in user_list:
        group.user_set.add(OSFUser.objects.get(id=user.id))


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0095_update_preprint_model_for_divorce'),
    ]

    operations = [
        migrations.RunPython(divorce_preprints_from_nodes)
    ]
