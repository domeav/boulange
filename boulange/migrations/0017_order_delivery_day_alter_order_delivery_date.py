# Generated by Django 5.1.4 on 2024-12-22 07:41

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("boulange", "0016_deliveryday_active_alter_order_delivery_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_day",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="boulange.deliveryday",
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="delivery_date",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="boulange.deliverydate",
            ),
        ),
    ]
