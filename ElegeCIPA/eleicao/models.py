import secrets
import string

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone


class Eleicao(models.Model):
    data_inicio = models.DateTimeField("Data de Início")
    data_fim = models.DateTimeField("Data de Fim")
    criada_em = models.DateTimeField(auto_now_add=True)
    vigente = models.BooleanField("Eleição Vigente", default=False)

    class Meta:
        verbose_name = "Eleição"
        verbose_name_plural = "Eleições"
        ordering = ["-data_inicio"]
        constraints = [
            models.UniqueConstraint(
                fields=["vigente"],
                condition=Q(vigente=True),
                name="uma_eleicao_vigente",
            )
        ]

    def __str__(self):
        return f"Eleição {self.pk} ({self.data_inicio:%d/%m/%Y} - {self.data_fim:%d/%m/%Y})"

    def clean(self):
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError("A data de fim não pode ser anterior à data de início.")

    def validate_constraints(self, exclude=None):
        # save() já desmarca a eleição vigente anterior; a constraint só protege o banco.
        super().validate_constraints(exclude={*(exclude or ()), "vigente"})

    def save(self, *args, **kwargs):
        if self.vigente:
            Eleicao.objects.exclude(pk=self.pk).filter(vigente=True).update(vigente=False)
        super().save(*args, **kwargs)

    def resumo_votos(self):
        totais = self.votos.aggregate(
            total=Count("id"),
            brancos=Count("id", filter=Q(voto_branco=True)),
        )
        return {
            "total": totais["total"],
            "brancos": totais["brancos"],
            "validos": totais["total"] - totais["brancos"],
        }


class Eleitor(models.Model):
    matricula_hash = models.CharField("Hash da Matrícula", max_length=64, unique=True)
    cpf_hash = models.CharField("Hash do CPF", max_length=64, unique=True, null=True, blank=True)
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Eleitores"

    def __str__(self):
        return self.matricula_hash[:8]


class Candidato(models.Model):
    UNIDADES = [
        ("UN1", "Unidade 1"),
        ("UN2", "Unidade 2"),
        ("UN3", "Unidade 3"),
        ("UN4", "Unidade 4"),
        ("UN5", "Unidade 5"),
        ("UN6", "Unidade 6"),
        ("UN7", "Unidade 7"),
    ]

    nome_completo = models.CharField(max_length=120)
    cargo = models.CharField(max_length=100)
    setor = models.CharField(max_length=100)
    unidade = models.CharField(max_length=10, choices=UNIDADES)
    foto = models.ImageField(upload_to="candidatos/", blank=True, null=True)
    eleicao = models.ForeignKey(Eleicao, on_delete=models.CASCADE, related_name="candidatos")
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome_completo} ({self.eleicao})"


def gerar_protocolo(ano):
    alfabeto = string.ascii_uppercase + string.digits
    while True:
        sufixo = "".join(secrets.choice(alfabeto) for _ in range(6))
        protocolo = f"CIPA{ano}{sufixo}"
        if not Voto.objects.filter(protocolo=protocolo).exists():
            return protocolo


class Voto(models.Model):
    eleitor = models.ForeignKey(Eleitor, on_delete=models.CASCADE, related_name="votos")
    candidato = models.ForeignKey(
        Candidato,
        on_delete=models.PROTECT,
        related_name="votos",
        null=True,
        blank=True,
    )
    eleicao = models.ForeignKey(Eleicao, on_delete=models.CASCADE, related_name="votos")
    data_hora = models.DateTimeField(default=timezone.now)
    protocolo = models.CharField("Protocolo do Voto", max_length=20, unique=True, editable=False)
    voto_branco = models.BooleanField("Voto em Branco", default=False)

    class Meta:
        verbose_name = "Voto"
        verbose_name_plural = "Votos"
        ordering = ["-data_hora"]
        constraints = [
            models.UniqueConstraint(fields=["eleitor", "eleicao"], name="voto_unico_por_eleicao")
        ]

    def __str__(self):
        return f"{self.eleitor} -> {self.candidato_nome} - {self.eleicao} ({self.protocolo})"

    def save(self, *args, **kwargs):
        if not self.protocolo:
            self.protocolo = gerar_protocolo(self.data_hora.year)
        super().save(*args, **kwargs)

    @property
    def candidato_nome(self):
        if self.voto_branco:
            return "Voto em Branco"
        return self.candidato.nome_completo if self.candidato else "Candidato não encontrado"
