# Generated by Django 5.1.4 on 2024-12-21 15:20

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("boulange", "0015_deliverydate_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliveryday",
            name="active",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="order",
            name="delivery_date",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="boulange.deliverydate"
            ),
        ),
    ]
