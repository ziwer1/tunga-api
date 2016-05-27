# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-27 06:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0010_auto_20160527_0612'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='update_interval_units',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Hour'), (2, 'Day'), (3, 'Week'), (4, 'Month'), (5, 'Quarter'), (6, 'Annual')], null=True),
        ),
    ]
