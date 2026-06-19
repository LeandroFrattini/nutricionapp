from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_paciente_actividad_fisica_frecuencia_and_more'),
    ]

    operations = [
        # ── Diametros oseos (cm) ──────────────────────────────────────────────
        migrations.AddField(
            model_name='medicion',
            name='diametro_biacromial',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Diametro biacromial (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='diametro_torax_transverso',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Diametro torax transverso (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='diametro_torax_ap',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Diametro torax anteroposterior (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='diametro_bi_iliocrestideo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Diametro bi-iliocrestideo (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='diametro_humeral',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Diametro humeral (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='diametro_femoral',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Diametro femoral (cm)'),
        ),
        # ── Perimetros completos (cm) ─────────────────────────────────────────
        migrations.AddField(
            model_name='medicion',
            name='perimetro_brazo_relajado',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Perimetro brazo relajado (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='perimetro_brazo_flexionado',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Perimetro brazo flexionado (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='perimetro_antebrazo',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Perimetro antebrazo (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='perimetro_torax',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Perimetro torax mesoesternal (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='perimetro_muslo_superior',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Perimetro muslo superior (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='perimetro_muslo_medial',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Perimetro muslo medial (cm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='perimetro_pantorrilla',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Perimetro pantorrilla maxima (cm)'),
        ),
        # ── Pliegues cutaneos (mm) ────────────────────────────────────────────
        migrations.AddField(
            model_name='medicion',
            name='pliegue_tricipital',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Pliegue tricipital (mm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='pliegue_subescapular',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Pliegue subescapular (mm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='pliegue_supraespinal',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Pliegue supraespinal (mm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='pliegue_abdominal',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Pliegue abdominal (mm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='pliegue_muslo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Pliegue muslo medial (mm)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='pliegue_pantorrilla',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Pliegue pantorrilla (mm)'),
        ),
        # ── Fraccionamiento 5 masas ───────────────────────────────────────────
        migrations.AddField(
            model_name='medicion',
            name='masa_adiposa_kg',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True, verbose_name='Masa adiposa (kg)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='masa_adiposa_pct',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Masa adiposa (%)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='masa_muscular_kg',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True, verbose_name='Masa muscular (kg)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='masa_muscular_pct',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Masa muscular (%)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='masa_residual_kg',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True, verbose_name='Masa residual (kg)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='masa_residual_pct',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Masa residual (%)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='masa_osea_kg',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True, verbose_name='Masa osea (kg)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='masa_osea_pct',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Masa osea (%)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='masa_piel_kg',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True, verbose_name='Masa piel (kg)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='masa_piel_pct',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Masa piel (%)'),
        ),
        # ── Somatotipo ────────────────────────────────────────────────────────
        migrations.AddField(
            model_name='medicion',
            name='soma_endo',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True, verbose_name='Endomorfia'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='soma_meso',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True, verbose_name='Mesomorfia'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='soma_ecto',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True, verbose_name='Ectomorfia'),
        ),
        # ── Metabolismo y peso ideal ──────────────────────────────────────────
        migrations.AddField(
            model_name='medicion',
            name='metabolismo_basal_kcal',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name='Metabolismo basal (kcal)'),
        ),
        migrations.AddField(
            model_name='medicion',
            name='peso_ideal_kg',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Peso ideal (kg)'),
        ),
    ]
