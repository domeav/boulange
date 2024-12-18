# Generated by Django 5.1.4 on 2024-12-16 08:32

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("boulange", "0009_brioches_too_big"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="customer",
            name="boulange_cu_name_f6a126_idx",
        ),
        migrations.RemoveIndex(
            model_name="customer",
            name="boulange_cu_email_a59615_idx",
        ),
        migrations.RemoveField(
            model_name="customer",
            name="active",
        ),
        migrations.RemoveField(
            model_name="customer",
            name="email",
        ),
        migrations.RemoveField(
            model_name="customer",
            name="name",
        ),
        migrations.AddField(
            model_name="customer",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
