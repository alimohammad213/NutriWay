# Generated by Django 5.2 on 2025-04-24 10:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0005_alter_certificate_created_at_alter_certificate_image_and_more'),
        ('specialists', '0004_mealcheck_subscribermeal_subscriberplan'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgressReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('weight', models.FloatField()),
                ('note', models.TextField()),
                ('specialist_comment', models.TextField(blank=True)),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='specialists.subscriptionplan')),
            ],
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('status', models.CharField(choices=[('active', 'Active'), ('expired', 'Expired'), ('cancelled', 'Cancelled')], max_length=15)),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.person')),
                ('subscriber_plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='specialists.subscriberplan')),
                ('subscription_plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='specialists.subscriptionplan')),
            ],
        ),
    ]
