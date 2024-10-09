# Generated by Django 5.1 on 2024-10-09 14:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("boulange", "0007_deliverypoint_batch_target"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recipe",
            name="orig_recipe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="boulange.recipe",
            ),
        ),
    ]
