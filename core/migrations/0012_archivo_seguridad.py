import uuid

import core.models
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_archivopaciente'),
    ]

    operations = [
        migrations.AddField(
            model_name='archivopaciente',
            name='token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='archivopaciente',
            name='archivo',
            field=models.FileField(
                upload_to='archivos_pacientes/',
                validators=[
                    core.models.validar_tamano_archivo,
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
                    ),
                ],
                verbose_name='Archivo',
            ),
        ),
        migrations.AlterField(
            model_name='nutricionista',
            name='foto',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='nutricionistas/',
                validators=[
                    core.models.validar_tamano_archivo,
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=['jpg', 'jpeg', 'png', 'webp']
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name='laboratorio',
            name='archivo_pdf',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='laboratorios/',
                validators=[
                    core.models.validar_tamano_archivo,
                    django.core.validators.FileExtensionValidator(allowed_extensions=['pdf']),
                ],
                verbose_name='Archivo PDF',
            ),
        ),
        migrations.AlterField(
            model_name='planalimentario',
            name='archivo_pdf',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='planes/',
                validators=[
                    core.models.validar_tamano_archivo,
                    django.core.validators.FileExtensionValidator(allowed_extensions=['pdf']),
                ],
                verbose_name='Plan en PDF',
            ),
        ),
    ]
