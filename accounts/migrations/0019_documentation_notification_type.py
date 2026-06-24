from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_whatsapptemplate_whatsapprecipientpreference'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsapprecipientpreference',
            name='notify_documentation_notification',
            field=models.BooleanField(default=False, verbose_name='Documentação (notificação)'),
        ),
        migrations.AlterField(
            model_name='whatsapprecipientpreference',
            name='notify_documentation',
            field=models.BooleanField(default=False, verbose_name='Documentação (cobrança)'),
        ),
        migrations.AlterField(
            model_name='whatsapptemplate',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('registrations', 'Inscrições'),
                    ('financial', 'Financeiro'),
                    ('documentation', 'Documentação (cobrança)'),
                    ('documentation_notification', 'Documentação (notificação)'),
                    ('general', 'Geral'),
                    ('test', 'Teste'),
                ],
                max_length=32,
                unique=True,
                verbose_name='Tipo de notificação',
            ),
        ),
    ]
