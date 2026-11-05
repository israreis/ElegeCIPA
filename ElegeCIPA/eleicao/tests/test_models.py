from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from ..models import Candidato, Eleicao, Eleitor, Voto
from ..utils import hash_identificador
from .helpers import BaseTestCase, criar_candidato, criar_eleicao, criar_eleitor


class EleicaoModelTests(TestCase):
    def test_nova_eleicao_vigente_desmarca_a_anterior(self):
        primeira = criar_eleicao()
        segunda = criar_eleicao()
        primeira.refresh_from_db()
        self.assertFalse(primeira.vigente)
        self.assertTrue(segunda.vigente)

    def test_eleicoes_nao_vigentes_podem_coexistir(self):
        criar_eleicao(vigente=False)
        criar_eleicao(vigente=False)
        self.assertEqual(Eleicao.objects.filter(vigente=False).count(), 2)

    def test_banco_impede_duas_eleicoes_vigentes(self):
        agora = timezone.now()
        eleicoes = [
            Eleicao(data_inicio=agora, data_fim=agora + timedelta(days=1), vigente=True)
            for _ in range(2)
        ]
        with self.assertRaises(IntegrityError), transaction.atomic():
            Eleicao.objects.bulk_create(eleicoes)

    def test_data_fim_anterior_ao_inicio_e_invalida(self):
        agora = timezone.now()
        eleicao = Eleicao(data_inicio=agora, data_fim=agora - timedelta(days=1))
        with self.assertRaises(ValidationError):
            eleicao.clean()

    def test_data_fim_igual_ao_inicio_e_valida(self):
        agora = timezone.now()
        Eleicao(data_inicio=agora, data_fim=agora).clean()

    def test_resumo_votos(self):
        eleicao = criar_eleicao()
        candidato = criar_candidato(eleicao)
        Voto.objects.create(eleitor=criar_eleitor("1", "11111111111"), eleicao=eleicao, candidato=candidato)
        Voto.objects.create(eleitor=criar_eleitor("2", "22222222222"), eleicao=eleicao, voto_branco=True)
        self.assertEqual(eleicao.resumo_votos(), {"total": 2, "brancos": 1, "validos": 1})

    def test_resumo_sem_votos(self):
        self.assertEqual(criar_eleicao().resumo_votos(), {"total": 0, "brancos": 0, "validos": 0})

    def test_ordenacao_mais_recente_primeiro(self):
        antiga = criar_eleicao(vigente=False, dias_inicio=-30, dias_fim=-20)
        recente = criar_eleicao(vigente=False, dias_inicio=-5, dias_fim=-1)
        self.assertEqual(list(Eleicao.objects.all()), [recente, antiga])

    def test_representacao_textual(self):
        eleicao = criar_eleicao()
        self.assertIn(f"Eleição {eleicao.pk}", str(eleicao))


class EleitorModelTests(TestCase):
    def test_matricula_hash_e_unico(self):
        criar_eleitor("1", "11111111111")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Eleitor.objects.create(matricula_hash=hash_identificador("1"))

    def test_cpf_hash_e_unico_quando_informado(self):
        criar_eleitor("1", "11111111111")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Eleitor.objects.create(
                matricula_hash=hash_identificador("2"),
                cpf_hash=hash_identificador("11111111111"),
            )

    def test_varios_eleitores_sem_cpf_sao_permitidos(self):
        Eleitor.objects.create(matricula_hash=hash_identificador("1"))
        Eleitor.objects.create(matricula_hash=hash_identificador("2"))
        self.assertEqual(Eleitor.objects.filter(cpf_hash__isnull=True).count(), 2)

    def test_representacao_nao_expoe_hash_completo(self):
        eleitor = criar_eleitor()
        self.assertEqual(len(str(eleitor)), 8)


class CandidatoModelTests(BaseTestCase):
    def test_unidades_genericas(self):
        codigos = [codigo for codigo, _ in Candidato.UNIDADES]
        self.assertEqual(codigos, [f"UN{numero}" for numero in range(1, 8)])

    def test_exclusao_da_eleicao_remove_candidatos(self):
        outra = criar_eleicao(vigente=False)
        criar_candidato(outra, "Bruno")
        outra.delete()
        self.assertFalse(Candidato.objects.filter(nome_completo="Bruno").exists())

    def test_representacao_textual(self):
        self.assertIn(self.candidato.nome_completo, str(self.candidato))


class VotoModelTests(BaseTestCase):
    def test_protocolo_gerado_automaticamente(self):
        voto = Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        self.assertRegex(voto.protocolo, rf"^CIPA{voto.data_hora.year}[A-Z0-9]{{6}}$")

    def test_protocolos_sao_unicos(self):
        protocolos = set()
        for numero in range(10):
            eleitor = criar_eleitor(f"mat{numero}", f"{numero:011d}")
            voto = Voto.objects.create(eleitor=eleitor, eleicao=self.eleicao, voto_branco=True)
            protocolos.add(voto.protocolo)
        self.assertEqual(len(protocolos), 10)

    def test_protocolo_nao_muda_ao_salvar_novamente(self):
        voto = Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        original = voto.protocolo
        voto.save()
        voto.refresh_from_db()
        self.assertEqual(voto.protocolo, original)

    def test_eleitor_vota_uma_unica_vez_por_eleicao(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, voto_branco=True)

    def test_eleitor_pode_votar_em_eleicoes_diferentes(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        outra = criar_eleicao(vigente=False)
        Voto.objects.create(eleitor=self.eleitor, eleicao=outra, voto_branco=True)
        self.assertEqual(self.eleitor.votos.count(), 2)

    def test_candidato_com_votos_nao_pode_ser_excluido(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        with self.assertRaises(ProtectedError):
            self.candidato.delete()

    def test_nome_do_candidato_no_voto(self):
        valido = Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        branco = Voto.objects.create(
            eleitor=criar_eleitor("2", "22222222222"), eleicao=self.eleicao, voto_branco=True
        )
        self.assertEqual(valido.candidato_nome, self.candidato.nome_completo)
        self.assertEqual(branco.candidato_nome, "Voto em Branco")
