# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-10-31 01:41
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0136_task_includes_pm_fee'),
    ]

    operations = [
        migrations.AddField(
            model_name='sprint',
            name='task_invoice',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tunga_tasks.TaskInvoice'),
        ),
    ]
