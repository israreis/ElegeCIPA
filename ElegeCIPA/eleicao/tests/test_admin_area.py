from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from ..models import Candidato, Eleicao, Voto
from .helpers import BaseTestCase, criar_candidato, criar_eleicao, imagem_png


def mensagens(response):
    return [str(mensagem) for mensagem in get_messages(response.wsgi_request)]


class AcessoAdministrativoTests(BaseTestCase):
    URLS_PROTEGIDAS = (
        ("painel_admin", []),
        ("apuracao_votos", []),
        ("gerar_extrato_pdf", []),
        ("criar_eleicao", []),
        ("criar_candidato", []),
        ("eleicoes_anteriores", []),
        ("escolher_eleicao_apurar", []),
        ("escolher_eleicao_encerrar", []),
    )

    def test_visitante_e_redirecionado_para_o_login(self):
        for nome, args in self.URLS_PROTEGIDAS:
            with self.subTest(url=nome):
                response = self.client.get(reverse(nome, args=args))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response["Location"])

    def test_eleitor_nao_acessa_area_administrativa(self):
        self.login_eleitor()
        for nome, args in self.URLS_PROTEGIDAS:
            with self.subTest(url=nome):
                response = self.client.get(reverse(nome, args=args))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response["Location"])

    def test_eleitor_nao_edita_nem_exclui(self):
        self.login_eleitor()
        rotas = (
            reverse("editar_candidato", args=[self.candidato.id]),
            reverse("editar_eleicao", args=[self.eleicao.id]),
            reverse("encerrar_eleicao", args=[self.eleicao.id]),
        )
        for url in rotas:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {}).status_code, 302)
        response = self.client.post(reverse("deletar_candidato", args=[self.candidato.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Candidato.objects.filter(id=self.candidato.id).exists())
        self.eleicao.refresh_from_db()
        self.assertTrue(self.eleicao.vigente)

    def test_administrador_acessa_paginas(self):
        self.login_admin()
        for nome in ("painel_admin", "apuracao_votos", "criar_candidato", "eleicoes_anteriores",
                     "escolher_eleicao_apurar", "escolher_eleicao_encerrar"):
            with self.subTest(url=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)


class PainelTests(BaseTestCase):
    def test_painel_lista_candidatos_da_eleicao_vigente(self):
        outra = criar_eleicao(vigente=False)
        criar_candidato(outra, "Candidato Antigo")
        self.login_admin()
        response = self.client.get(reverse("painel_admin"))
        self.assertContains(response, self.candidato.nome_completo)
        self.assertNotContains(response, "Candidato Antigo")

    def test_painel_sem_eleicao_vigente(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_admin()
        response = self.client.get(reverse("painel_admin"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["eleicao_atual"])


class EleicaoAdminTests(BaseTestCase):
    def test_nao_cria_eleicao_com_outra_vigente(self):
        self.login_admin()
        response = self.client.post(
            reverse("criar_eleicao"), {"data_inicio": "2026-01-01", "data_fim": "2026-01-10"}
        )
        self.assertRedirects(response, reverse("painel_admin"))
        self.assertEqual(Eleicao.objects.count(), 1)

    def test_cria_eleicao_vigente_quando_nao_ha_outra(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_admin()
        self.client.post(reverse("criar_eleicao"), {"data_inicio": "2026-01-01", "data_fim": "2026-01-10"})
        self.assertTrue(Eleicao.objects.exclude(id=self.eleicao.id).get().vigente)

    def test_formulario_de_criacao_nao_exibe_campo_vigente(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_admin()
        self.assertNotIn("vigente", self.client.get(reverse("criar_eleicao")).context["form"].fields)

    def test_eleicao_com_fim_anterior_ao_inicio_e_rejeitada(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_admin()
        response = self.client.post(
            reverse("criar_eleicao"), {"data_inicio": "2026-01-10", "data_fim": "2026-01-01"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Eleicao.objects.count(), 1)

    def test_datas_obrigatorias(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_admin()
        response = self.client.post(reverse("criar_eleicao"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Eleicao.objects.count(), 1)

    def test_editar_eleicao_atualiza_as_datas(self):
        self.login_admin()
        response = self.client.post(
            reverse("editar_eleicao", args=[self.eleicao.id]),
            {"data_inicio": "2026-02-01", "data_fim": "2026-02-20", "vigente": "on"},
        )
        self.assertRedirects(response, reverse("painel_admin"))
        self.eleicao.refresh_from_db()
        self.assertEqual(self.eleicao.data_inicio.date().isoformat(), "2026-02-01")
        self.assertEqual(self.eleicao.data_fim.date().isoformat(), "2026-02-20")

    def test_editar_eleicao_pode_trocar_a_vigente(self):
        outra = criar_eleicao(vigente=False, dias_inicio=-10, dias_fim=-5)
        self.login_admin()
        response = self.client.post(
            reverse("editar_eleicao", args=[outra.id]),
            {"data_inicio": "2026-01-01", "data_fim": "2026-01-10", "vigente": "on"},
        )
        self.assertRedirects(response, reverse("painel_admin"))
        outra.refresh_from_db()
        self.eleicao.refresh_from_db()
        self.assertTrue(outra.vigente)
        self.assertFalse(self.eleicao.vigente)

    def test_editar_eleicao_inexistente(self):
        self.login_admin()
        self.assertEqual(self.client.get(reverse("editar_eleicao", args=[999999])).status_code, 404)

    def test_eleicoes_anteriores_lista_somente_encerradas(self):
        encerrada = criar_eleicao(vigente=False, dias_inicio=-30, dias_fim=-20)
        self.login_admin()
        ids = [e.id for e in self.client.get(reverse("eleicoes_anteriores")).context["eleicoes"]]
        self.assertEqual(ids, [encerrada.id])


class EncerramentoTests(BaseTestCase):
    def test_confirmacao_nao_encerra_no_get(self):
        self.login_admin()
        self.assertEqual(self.client.get(reverse("encerrar_eleicao", args=[self.eleicao.id])).status_code, 200)
        self.eleicao.refresh_from_db()
        self.assertTrue(self.eleicao.vigente)

    def test_encerrar_eleicao(self):
        self.login_admin()
        url = reverse("encerrar_eleicao", args=[self.eleicao.id])
        fim_anterior = self.eleicao.data_fim
        response = self.client.post(url)
        self.assertRedirects(response, reverse("apuracao_votos_especifica", args=[self.eleicao.id]))
        self.eleicao.refresh_from_db()
        self.assertFalse(self.eleicao.vigente)
        self.assertLessEqual(self.eleicao.data_fim, timezone.now())
        self.assertLess(self.eleicao.data_fim, fim_anterior)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_encerrar_eleicao_ja_encerrada_retorna_404(self):
        encerrada = criar_eleicao(vigente=False)
        self.login_admin()
        self.assertEqual(self.client.post(reverse("encerrar_eleicao", args=[encerrada.id])).status_code, 404)

    def test_eleitor_nao_vota_depois_do_encerramento(self):
        self.login_admin()
        self.client.post(reverse("encerrar_eleicao", args=[self.eleicao.id]))
        self.client.logout()
        self.login_eleitor()
        self.assertRedirects(self.votar(self.candidato), reverse("candidatos"))
        self.assertFalse(Voto.objects.exists())

    def test_seletor_de_encerramento_aceita_eleicao_vigente(self):
        self.login_admin()
        response = self.client.post(reverse("escolher_eleicao_encerrar"), {"eleicao": self.eleicao.id})
        self.assertRedirects(response, reverse("encerrar_eleicao", args=[self.eleicao.id]))

    def test_seletor_de_encerramento_rejeita_eleicao_encerrada(self):
        encerrada = criar_eleicao(vigente=False)
        self.login_admin()
        response = self.client.post(reverse("escolher_eleicao_encerrar"), {"eleicao": encerrada.id})
        self.assertEqual(response.status_code, 200)

    def test_seletor_de_apuracao_aceita_qualquer_eleicao(self):
        encerrada = criar_eleicao(vigente=False)
        self.login_admin()
        response = self.client.post(reverse("escolher_eleicao_apurar"), {"eleicao": encerrada.id})
        self.assertRedirects(
            response,
            reverse("apuracao_votos_especifica", args=[encerrada.id]),
            fetch_redirect_response=False,
        )

    def test_seletor_rejeita_valor_invalido(self):
        self.login_admin()
        for valor in ("abc", "999999", ""):
            with self.subTest(valor=valor):
                response = self.client.post(reverse("escolher_eleicao_apurar"), {"eleicao": valor})
                self.assertEqual(response.status_code, 200)


class CandidatoAdminTests(BaseTestCase):
    def dados(self, **extra):
        return {
            "nome_completo": "Maria Souza",
            "cargo": "Técnica",
            "setor": "Qualidade",
            "unidade": "UN2",
            "eleicao": self.eleicao.id,
            **extra,
        }

    def test_cadastro_com_foto(self):
        self.login_admin()
        response = self.client.post(reverse("criar_candidato"), {**self.dados(), "foto": imagem_png()})
        self.assertRedirects(response, reverse("painel_admin"))
        candidato = Candidato.objects.get(nome_completo="Maria Souza")
        self.assertTrue(candidato.foto.name.startswith("candidatos/"))
        self.assertEqual(candidato.eleicao, self.eleicao)

    def test_cadastro_sem_foto(self):
        self.login_admin()
        self.client.post(reverse("criar_candidato"), self.dados())
        self.assertFalse(Candidato.objects.get(nome_completo="Maria Souza").foto)

    def test_cadastro_exibe_mensagem_de_sucesso(self):
        self.login_admin()
        response = self.client.post(reverse("criar_candidato"), self.dados())
        self.assertTrue(any("cadastrado com sucesso" in m for m in mensagens(response)))

    def test_cadastro_so_aceita_eleicao_vigente(self):
        encerrada = criar_eleicao(vigente=False)
        self.login_admin()
        response = self.client.post(reverse("criar_candidato"), self.dados(eleicao=encerrada.id))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Candidato.objects.filter(nome_completo="Maria Souza").exists())

    def test_cadastro_com_campos_obrigatorios_vazios(self):
        self.login_admin()
        response = self.client.post(reverse("criar_candidato"), self.dados(nome_completo="", cargo=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Candidato.objects.filter(cargo="").exists())

    def test_edicao_atualiza_os_dados(self):
        self.login_admin()
        response = self.client.post(
            reverse("editar_candidato", args=[self.candidato.id]),
            self.dados(nome_completo="Ana Atualizada", cargo="Coordenadora"),
        )
        self.assertRedirects(response, reverse("painel_admin"))
        self.candidato.refresh_from_db()
        self.assertEqual(self.candidato.nome_completo, "Ana Atualizada")
        self.assertEqual(self.candidato.cargo, "Coordenadora")

    def test_edicao_mantem_a_foto_quando_nao_enviada(self):
        self.login_admin()
        self.client.post(reverse("criar_candidato"), {**self.dados(), "foto": imagem_png()})
        candidato = Candidato.objects.get(nome_completo="Maria Souza")
        foto_original = candidato.foto.name
        self.client.post(reverse("editar_candidato", args=[candidato.id]), self.dados(cargo="Gerente"))
        candidato.refresh_from_db()
        self.assertEqual(candidato.foto.name, foto_original)
        self.assertEqual(candidato.cargo, "Gerente")

    def test_edicao_de_candidato_inexistente(self):
        self.login_admin()
        self.assertEqual(self.client.get(reverse("editar_candidato", args=[999999])).status_code, 404)

    def test_exclusao_exige_post(self):
        self.login_admin()
        url = reverse("deletar_candidato", args=[self.candidato.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(Candidato.objects.filter(id=self.candidato.id).exists())

    def test_exclusao_de_candidato_sem_votos(self):
        self.login_admin()
        response = self.client.post(reverse("deletar_candidato", args=[self.candidato.id]))
        self.assertRedirects(response, reverse("painel_admin"))
        self.assertFalse(Candidato.objects.filter(id=self.candidato.id).exists())

    def test_candidato_com_votos_nao_e_removido(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        self.login_admin()
        response = self.client.post(reverse("deletar_candidato", args=[self.candidato.id]))
        self.assertRedirects(response, reverse("painel_admin"))
        self.assertTrue(Candidato.objects.filter(id=self.candidato.id).exists())
        self.assertTrue(any("não podem ser removidos" in m for m in mensagens(response)))
        self.assertEqual(Voto.objects.count(), 1)
