from django.test import Client
from django.urls import reverse

from ..models import Candidato, Voto
from .helpers import CPF, MATRICULA, SENHA_ADMIN, BaseTestCase, criar_candidato


class CabecalhosDeSegurancaTests(BaseTestCase):
    def test_pagina_nao_pode_ser_exibida_em_iframe(self):
        self.assertEqual(self.client.get(reverse("landing"))["X-Frame-Options"], "DENY")

    def test_bloqueia_mime_sniffing(self):
        self.assertEqual(self.client.get(reverse("landing"))["X-Content-Type-Options"], "nosniff")

    def test_politica_de_referrer(self):
        self.assertEqual(self.client.get(reverse("landing"))["Referrer-Policy"], "same-origin")


class ProtecaoCsrfTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)

    def test_login_sem_token_e_recusado(self):
        response = self.client.post(reverse("login"), {"matricula": MATRICULA, "cpf": CPF})
        self.assertEqual(response.status_code, 403)

    def test_formularios_de_login_incluem_token(self):
        self.assertContains(self.client.get(reverse("login")), "csrfmiddlewaretoken", count=2)

    def test_voto_sem_token_e_recusado(self):
        self.client.force_login(self.usuario_do_eleitor())
        response = self.client.post(reverse("registrar_voto", args=[self.candidato.id]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Voto.objects.exists())

    def test_exclusao_sem_token_e_recusada(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("deletar_candidato", args=[self.candidato.id]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Candidato.objects.filter(id=self.candidato.id).exists())

    def test_logout_sem_token_e_recusado(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse("logout")).status_code, 403)

    def usuario_do_eleitor(self):
        Client().post(reverse("login"), {"matricula": MATRICULA, "cpf": CPF})
        self.eleitor.refresh_from_db()
        return self.eleitor.user


class MetodosHttpTests(BaseTestCase):
    def test_acoes_que_alteram_dados_rejeitam_get(self):
        self.login_eleitor()
        for nome, args in (("registrar_voto", [self.candidato.id]), ("registrar_voto_branco", []), ("logout", [])):
            with self.subTest(url=nome):
                self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 405)

    def test_exclusao_de_candidato_rejeita_get_e_put(self):
        self.login_admin()
        url = reverse("deletar_candidato", args=[self.candidato.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.put(url).status_code, 405)


class ProtecaoContraXssTests(BaseTestCase):
    CARGA = "<script>alert('xss')</script>"

    def test_nome_do_candidato_e_escapado_na_votacao(self):
        criar_candidato(self.eleicao, self.CARGA)
        self.login_eleitor()
        response = self.client.get(reverse("candidatos"))
        self.assertNotContains(response, self.CARGA)
        self.assertContains(response, "&lt;script&gt;")

    def test_nome_do_candidato_e_escapado_no_painel(self):
        criar_candidato(self.eleicao, self.CARGA)
        self.login_admin()
        self.assertNotContains(self.client.get(reverse("painel_admin")), self.CARGA)

    def test_nome_do_candidato_e_escapado_na_apuracao(self):
        criar_candidato(self.eleicao, self.CARGA)
        self.login_admin()
        self.assertNotContains(self.client.get(reverse("apuracao_votos")), self.CARGA)


class SigiloDosDadosTests(BaseTestCase):
    def test_banco_nao_guarda_matricula_nem_cpf_em_texto_puro(self):
        self.assertNotIn(MATRICULA, self.eleitor.matricula_hash)
        self.assertNotIn(CPF, self.eleitor.cpf_hash)
        self.assertEqual(len(self.eleitor.matricula_hash), 64)

    def test_usuario_do_eleitor_nao_tem_senha_utilizavel(self):
        self.login_eleitor()
        self.eleitor.refresh_from_db()
        self.assertFalse(self.eleitor.user.has_usable_password())
        self.assertFalse(self.eleitor.user.is_staff)
        self.assertFalse(self.eleitor.user.is_superuser)

    def test_eleitor_nao_consegue_entrar_como_administrador_com_matricula(self):
        self.login_eleitor()
        self.eleitor.refresh_from_db()
        self.client.post(reverse("logout"))
        response = self.client.post(
            reverse("login"), {"username": self.eleitor.user.username, "password": SENHA_ADMIN}
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response.status_code, 200)


class AdminDjangoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.voto = Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        self.login_admin()

    def test_votos_podem_ser_consultados(self):
        self.assertEqual(self.client.get(reverse("admin:eleicao_voto_changelist")).status_code, 200)

    def test_votos_nao_podem_ser_adicionados(self):
        self.assertEqual(self.client.get(reverse("admin:eleicao_voto_add")).status_code, 403)

    def test_votos_nao_podem_ser_alterados(self):
        url = reverse("admin:eleicao_voto_change", args=[self.voto.pk])
        response = self.client.post(url, {"protocolo": "ALTERADO", "voto_branco": "on"})
        self.assertEqual(response.status_code, 403)
        self.voto.refresh_from_db()
        self.assertNotEqual(self.voto.protocolo, "ALTERADO")
        self.assertFalse(self.voto.voto_branco)

    def test_votos_nao_podem_ser_excluidos(self):
        response = self.client.post(reverse("admin:eleicao_voto_delete", args=[self.voto.pk]), {"post": "yes"})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Voto.objects.filter(pk=self.voto.pk).exists())

    def test_eleitores_nao_sao_expostos_no_admin(self):
        self.assertEqual(self.client.get("/admin/eleicao/eleitor/").status_code, 404)
