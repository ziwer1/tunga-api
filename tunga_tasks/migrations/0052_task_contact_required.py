# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-02-05 21:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0051_auto_20170205_0942'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='contact_required',
            field=models.BooleanField(default=False),
        ),
    ]
