# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-09-18 04:35
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tunga_tasks', '0128_auto_20170904_0512'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='participantpayment',
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterModelOptions(
            name='taskpayment',
            options={'ordering': ['-created_at']},
        ),
        migrations.AddField(
            model_name='task',
            name='payment_approved',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='task',
            name='payment_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='payment_approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='tasks_payments_approved', to=settings.AUTH_USER_MODEL),
        ),
    ]
