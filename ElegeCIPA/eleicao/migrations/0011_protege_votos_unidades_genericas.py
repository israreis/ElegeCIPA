import django.db.models.deletion
from django.db import migrations, models

CODIGOS_UNIDADES = {
    "HE": "UN1",
    "LAB": "UN2",
    "CORP": "UN3",
    "CNBH": "UN4",
    "CNVN": "UN5",
    "CNCT": "UN6",
    "CESP": "UN7",
}


def _renomear_unidades(apps, mapa):
    Candidato = apps.get_model("eleicao", "Candidato")
    for antigo, novo in mapa.items():
        Candidato.objects.filter(unidade=antigo).update(unidade=novo)


def usar_unidades_genericas(apps, schema_editor):
    _renomear_unidades(apps, CODIGOS_UNIDADES)


def restaurar_unidades_originais(apps, schema_editor):
    _renomear_unidades(apps, {novo: antigo for antigo, novo in CODIGOS_UNIDADES.items()})


class Migration(migrations.Migration):

    dependencies = [
        ("eleicao", "0010_alter_voto_eleicao"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="eleitor",
            options={"verbose_name_plural": "Eleitores"},
        ),
        migrations.RunPython(usar_unidades_genericas, restaurar_unidades_originais),
        migrations.AlterField(
            model_name="candidato",
            name="unidade",
            field=models.CharField(
                choices=[
                    ("UN1", "Unidade 1"),
                    ("UN2", "Unidade 2"),
                    ("UN3", "Unidade 3"),
                    ("UN4", "Unidade 4"),
                    ("UN5", "Unidade 5"),
                    ("UN6", "Unidade 6"),
                    ("UN7", "Unidade 7"),
                ],
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="voto",
            name="candidato",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="votos",
                to="eleicao.candidato",
            ),
        ),
        migrations.AddConstraint(
            model_name="eleicao",
            constraint=models.UniqueConstraint(
                condition=models.Q(("vigente", True)),
                fields=("vigente",),
                name="uma_eleicao_vigente",
            ),
        ),
    ]
