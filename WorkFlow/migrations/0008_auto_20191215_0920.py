# Generated by Django 2.2.6 on 2019-12-15 09:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("WorkFlow", "0007_job_stage_states"),
    ]

    operations = [
        migrations.AlterField(
            model_name="action",
            name="create_time",
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name="task",
            name="create_time",
            field=models.DateTimeField(null=True),
        ),
    ]