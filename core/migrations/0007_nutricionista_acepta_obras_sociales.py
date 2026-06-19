from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_medicion_isak_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='nutricionista',
            name='acepta_obras_sociales',
            field=models.BooleanField(default=False, verbose_name='Acepta obras sociales'),
        ),
        migrations.AddField(
            model_name='nutricionista',
            name='obras_sociales_detalle',
            field=models.TextField(blank=True, verbose_name='Detalle de obras sociales'),
        ),
    ]
