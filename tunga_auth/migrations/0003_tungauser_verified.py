# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-04-30 14:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_auth', '0002_tungauser_last_activity'),
    ]

    operations = [
        migrations.AddField(
            model_name='tungauser',
            name='verified',
            field=models.BooleanField(default=False),
        ),
    ]