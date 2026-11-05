from importlib import import_module

from django.apps import apps
from django.test import TestCase

from ..models import Candidato
from .helpers import criar_eleicao

MIGRACAO = "ElegeCIPA.eleicao.migrations.0011_protege_votos_unidades_genericas"


class MigracaoUnidadesGenericasTests(TestCase):
    def setUp(self):
        self.migracao = import_module(MIGRACAO)
        self.eleicao = criar_eleicao()

    def criar(self, nome, unidade):
        return Candidato.objects.create(
            nome_completo=nome, cargo="Cargo", setor="Setor", unidade=unidade, eleicao=self.eleicao
        )

    def test_codigos_novos_correspondem_as_unidades_do_modelo(self):
        novos = set(self.migracao.CODIGOS_UNIDADES.values())
        self.assertEqual(novos, {codigo for codigo, _ in Candidato.UNIDADES})

    def test_converte_codigos_antigos(self):
        candidatos = {
            antigo: self.criar(f"Candidato {antigo}", antigo) for antigo in self.migracao.CODIGOS_UNIDADES
        }
        self.migracao.usar_unidades_genericas(apps, None)
        for antigo, novo in self.migracao.CODIGOS_UNIDADES.items():
            candidatos[antigo].refresh_from_db()
            self.assertEqual(candidatos[antigo].unidade, novo)

    def test_conversao_e_reversivel(self):
        candidato = self.criar("Ana", "HE")
        self.migracao.usar_unidades_genericas(apps, None)
        self.migracao.restaurar_unidades_originais(apps, None)
        candidato.refresh_from_db()
        self.assertEqual(candidato.unidade, "HE")

    def test_conversao_nao_altera_codigos_ja_genericos(self):
        candidato = self.criar("Ana", "UN3")
        self.migracao.usar_unidades_genericas(apps, None)
        candidato.refresh_from_db()
        self.assertEqual(candidato.unidade, "UN3")
