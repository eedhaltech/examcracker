from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_razorpaysettings_subscription_amount_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RazorpayWebhookEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.CharField(blank=True, db_index=True, max_length=255)),
                ('event_type', models.CharField(db_index=True, max_length=100)),
                ('payload', models.JSONField(default=dict)),
                ('processed', models.BooleanField(default=False)),
                ('error_message', models.TextField(blank=True)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-received_at'],
            },
        ),
    ]
