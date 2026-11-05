from io import BytesIO
from itertools import count
from types import SimpleNamespace

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from ..models import Voto
from ..pdf import escrever_extrato, nome_arquivo, periodo_texto
from .helpers import BaseTestCase, criar_candidato, criar_eleicao, criar_eleitor


_sequencia_cpf = count(1)


def registrar_votos(eleicao, candidato, quantidade, prefixo):
    for numero in range(quantidade):
        eleitor = criar_eleitor(f"{prefixo}{numero}", f"{next(_sequencia_cpf):011d}")
        Voto.objects.create(eleitor=eleitor, eleicao=eleicao, candidato=candidato)


@override_settings(VAGAS_TITULARES=1, VAGAS_SUPLENTES=1)
class ApuracaoTests(BaseTestCase):
    def apurar(self, eleicao=None):
        self.login_admin()
        eleicao = eleicao or self.eleicao
        return self.client.get(reverse("apuracao_votos_especifica", args=[eleicao.id]))

    def test_classifica_titulares_suplentes_e_nao_eleitos(self):
        segundo = criar_candidato(self.eleicao, "Bruno")
        terceiro = criar_candidato(self.eleicao, "Carla")
        sem_votos = criar_candidato(self.eleicao, "Diego")

        registrar_votos(self.eleicao, self.candidato, 1, "a")
        registrar_votos(self.eleicao, segundo, 3, "b")
        registrar_votos(self.eleicao, terceiro, 2, "c")
        Voto.objects.create(
            eleitor=criar_eleitor("branco", "99999999998"), eleicao=self.eleicao, voto_branco=True
        )

        response = self.apurar()

        self.assertEqual([c.id for c in response.context["eleitos"]], [segundo.id])
        self.assertEqual([c.id for c in response.context["suplentes"]], [terceiro.id])
        self.assertEqual([c.id for c in response.context["nao_eleitos"]], [self.candidato.id, sem_votos.id])
        self.assertEqual(response.context["total_votos"], 7)
        self.assertEqual(response.context["votos_brancos"], 1)
        self.assertEqual(response.context["votos_validos"], 6)

    def test_empate_e_resolvido_por_ordem_alfabetica(self):
        beatriz = criar_candidato(self.eleicao, "Beatriz")
        self.candidato.nome_completo = "Zélia"
        self.candidato.save()
        registrar_votos(self.eleicao, self.candidato, 2, "z")
        registrar_votos(self.eleicao, beatriz, 2, "b")

        response = self.apurar()

        self.assertEqual([c.id for c in response.context["eleitos"]], [beatriz.id])
        self.assertEqual([c.id for c in response.context["suplentes"]], [self.candidato.id])

    def test_candidato_sem_votos_nunca_e_eleito(self):
        response = self.apurar()
        self.assertEqual(response.context["eleitos"], [])
        self.assertEqual(response.context["suplentes"], [])
        self.assertEqual([c.id for c in response.context["nao_eleitos"]], [self.candidato.id])

    def test_apuracao_sem_votos(self):
        response = self.apurar()
        self.assertEqual(response.context["total_votos"], 0)
        self.assertEqual(response.context["votos_validos"], 0)
        self.assertEqual(response.context["votos_brancos"], 0)

    def test_apuracao_considera_somente_a_eleicao_escolhida(self):
        outra = criar_eleicao(vigente=False)
        candidato_outra = criar_candidato(outra, "Outra")
        registrar_votos(outra, candidato_outra, 3, "o")
        response = self.apurar()
        self.assertEqual(response.context["total_votos"], 0)
        self.assertNotIn(candidato_outra.id, [c.id for c in response.context["nao_eleitos"]])

    def test_apuracao_de_eleicao_encerrada(self):
        encerrada = criar_eleicao(vigente=False)
        candidato = criar_candidato(encerrada, "Encerrada")
        registrar_votos(encerrada, candidato, 2, "e")
        response = self.apurar(encerrada)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c.id for c in response.context["eleitos"]], [candidato.id])

    def test_apuracao_de_eleicao_inexistente(self):
        self.login_admin()
        self.assertEqual(self.client.get(reverse("apuracao_votos_especifica", args=[999999])).status_code, 404)

    def test_sem_eleicao_vigente_redireciona_ao_painel(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_admin()
        self.assertRedirects(self.client.get(reverse("apuracao_votos")), reverse("painel_admin"))

    @override_settings(VAGAS_TITULARES=3, VAGAS_SUPLENTES=0)
    def test_quantidade_de_vagas_e_configuravel(self):
        extras = [criar_candidato(self.eleicao, nome) for nome in ("Bia", "Caio")]
        registrar_votos(self.eleicao, self.candidato, 1, "a")
        for indice, candidato in enumerate(extras):
            registrar_votos(self.eleicao, candidato, 1, f"x{indice}")
        response = self.apurar()
        self.assertEqual(len(response.context["eleitos"]), 3)
        self.assertEqual(response.context["suplentes"], [])


class ExtratoPdfTests(BaseTestCase):
    def test_extrato_pdf(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        self.login_admin()
        response = self.client.get(reverse("gerar_extrato_pdf_especifico", args=[self.eleicao.id]))
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn(nome_arquivo(self.eleicao), response["Content-Disposition"])

    def test_extrato_da_eleicao_vigente_sem_informar_id(self):
        self.login_admin()
        response = self.client.get(reverse("gerar_extrato_pdf"))
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_extrato_sem_eleicao_vigente_redireciona(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_admin()
        self.assertRedirects(self.client.get(reverse("gerar_extrato_pdf")), reverse("painel_admin"))

    def test_extrato_de_eleicao_inexistente(self):
        self.login_admin()
        self.assertEqual(self.client.get(reverse("gerar_extrato_pdf_especifico", args=[999999])).status_code, 404)

    def test_extrato_exige_administrador(self):
        self.login_eleitor()
        response = self.client.get(reverse("gerar_extrato_pdf"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])


class GeradorDePdfTests(BaseTestCase):
    RESUMO_VAZIO = {"total": 0, "brancos": 0, "validos": 0}

    def votos_falsos(self, quantidade):
        return [
            SimpleNamespace(
                data_hora=timezone.now(),
                candidato_nome=f"Candidato {numero}",
                protocolo=f"CIPA2026{numero:06d}",
            )
            for numero in range(quantidade)
        ]

    def gerar(self, votos, resumo=None, total_eleitores=10):
        buffer = BytesIO()
        escrever_extrato(buffer, self.eleicao, votos, resumo or self.RESUMO_VAZIO, total_eleitores)
        return buffer.getvalue()

    def test_gera_pdf_valido_sem_votos(self):
        conteudo = self.gerar([])
        self.assertTrue(conteudo.startswith(b"%PDF"))
        self.assertIn(b"%%EOF", conteudo)

    def test_nao_divide_por_zero_sem_eleitores(self):
        self.assertTrue(self.gerar([], total_eleitores=0).startswith(b"%PDF"))

    def test_muitos_votos_geram_mais_paginas(self):
        resumo = {"total": 200, "brancos": 0, "validos": 200}
        poucas = self.gerar(self.votos_falsos(3), resumo).count(b"/Type /Page")
        muitas = self.gerar(self.votos_falsos(200), resumo).count(b"/Type /Page")
        self.assertGreater(muitas, poucas)

    def test_nome_do_arquivo_e_periodo(self):
        self.assertRegex(nome_arquivo(self.eleicao), r"^Apuracao_CIPA_\d{2}_\d{2}_\d{4}_\d{2}_\d{2}_\d{4}\.pdf$")
        self.assertRegex(periodo_texto(self.eleicao), r"^\d{2}/\d{2}/\d{4} a \d{2}/\d{2}/\d{4}$")
