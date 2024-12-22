# Generated by Django 5.1.4 on 2024-12-18 16:02

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("boulange", "0012_remove_deliverypoint_boulange_de_name_e978e2_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="deliverydate",
            name="delivery_point",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="boulange.customer"
            ),
        ),
        migrations.RemoveField(
            model_name="customer",
            name="delivery_point",
        ),
        migrations.AddField(
            model_name="customer",
            name="address",
            field=models.CharField(blank=True, max_length=400, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="batch_target",
            field=models.CharField(
                choices=[("SAME_DAY", "same day"), ("PREVIOUS_DAY", "previous day")],
                default="SAME_DAY",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="can_order_here_from_website",
            field=models.BooleanField(default=True),
        ),
        migrations.DeleteModel(
            name="DeliveryPoint",
        ),
    ]