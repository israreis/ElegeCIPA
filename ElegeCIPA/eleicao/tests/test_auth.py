from django.contrib.auth import get_user_model
from django.urls import reverse

from ..models import Eleitor
from ..utils import hash_identificador
from .helpers import CPF, MATRICULA, SENHA_ADMIN, BaseTestCase

User = get_user_model()


class PaginasPublicasTests(BaseTestCase):
    def test_landing_page(self):
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("login"))

    def test_pagina_de_login_tem_as_duas_abas(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Eleitor")
        self.assertContains(response, "Administrador")


class LoginEleitorTests(BaseTestCase):
    def test_eleitor_valido_entra_e_recebe_usuario_sem_senha_utilizavel(self):
        response = self.login_eleitor()
        self.assertRedirects(response, reverse("candidatos"))
        self.eleitor.refresh_from_db()
        self.assertFalse(self.eleitor.user.has_usable_password())

    def test_segundo_login_reutiliza_o_mesmo_usuario(self):
        self.login_eleitor()
        self.client.post(reverse("logout"))
        self.login_eleitor()
        self.assertEqual(User.objects.filter(username__startswith="eleitor_").count(), 1)

    def test_cpf_incorreto_nao_autentica(self):
        response = self.login_eleitor(cpf="00000000000")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matrícula ou CPF inválidos.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_matricula_incorreta_nao_autentica(self):
        response = self.login_eleitor(matricula="99999")
        self.assertContains(response, "Matrícula ou CPF inválidos.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cpf_com_menos_de_11_digitos_e_recusado_pelo_formulario(self):
        response = self.login_eleitor(cpf="123")
        self.assertContains(response, "Digite apenas números, com 11 dígitos.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cpf_com_letras_e_recusado(self):
        response = self.login_eleitor(cpf="1234567890a")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response.status_code, 200)

    def test_cpf_com_pontuacao_e_recusado(self):
        response = self.login_eleitor(cpf="123.456.789-01")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response.status_code, 200)

    def test_eleitor_sem_cpf_cadastrado_nao_consegue_entrar(self):
        Eleitor.objects.create(matricula_hash=hash_identificador("777"))
        response = self.login_eleitor(matricula="777", cpf=CPF)
        self.assertContains(response, "Matrícula ou CPF inválidos.")

    def test_campos_vazios_nao_autenticam(self):
        response = self.client.post(reverse("login"), {"matricula": "", "cpf": ""})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_com_get_apenas_exibe_o_formulario(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class LoginAdministradorTests(BaseTestCase):
    def test_superusuario_entra_no_painel(self):
        response = self.client.post(reverse("login"), {"username": "admin", "password": SENHA_ADMIN})
        self.assertRedirects(response, reverse("painel_admin"))

    def test_senha_incorreta(self):
        response = self.client.post(reverse("login"), {"username": "admin", "password": "errada"})
        self.assertContains(response, "Usuário ou senha incorretos, ou sem permissão.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_usuario_comum_nao_entra_como_administrador(self):
        User.objects.create_user("comum", password=SENHA_ADMIN)
        response = self.client.post(reverse("login"), {"username": "comum", "password": SENHA_ADMIN})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_usuario_staff_sem_superusuario_nao_entra(self):
        User.objects.create_user("staff", password=SENHA_ADMIN, is_staff=True)
        self.client.post(reverse("login"), {"username": "staff", "password": SENHA_ADMIN})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_usuario_inativo_nao_entra(self):
        User.objects.create_superuser("inativo", password=SENHA_ADMIN, is_active=False)
        self.client.post(reverse("login"), {"username": "inativo", "password": SENHA_ADMIN})
        self.assertNotIn("_auth_user_id", self.client.session)


class BloqueioPorTentativasTests(BaseTestCase):
    def test_bloqueio_apos_tentativas_invalidas_do_eleitor(self):
        for _ in range(5):
            self.login_eleitor(cpf="00000000000")
        response = self.login_eleitor()
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_quatro_falhas_ainda_permitem_entrar(self):
        for _ in range(4):
            self.login_eleitor(cpf="00000000000")
        self.assertRedirects(self.login_eleitor(), reverse("candidatos"))

    def test_login_bem_sucedido_zera_o_contador(self):
        for _ in range(4):
            self.login_eleitor(cpf="00000000000")
        self.login_eleitor()
        self.client.post(reverse("logout"))
        for _ in range(4):
            self.login_eleitor(cpf="00000000000")
        self.assertRedirects(self.login_eleitor(), reverse("candidatos"))

    def test_bloqueio_tambem_vale_para_o_administrador(self):
        for _ in range(5):
            self.login_eleitor(cpf="00000000000")
        response = self.client.post(reverse("login"), {"username": "admin", "password": SENHA_ADMIN})
        self.assertEqual(response.status_code, 429)

    def test_falhas_de_administrador_tambem_contam(self):
        for _ in range(5):
            self.client.post(reverse("login"), {"username": "admin", "password": "errada"})
        response = self.login_eleitor()
        self.assertEqual(response.status_code, 429)


class LogoutTests(BaseTestCase):
    def test_logout_exige_post(self):
        self.login_eleitor()
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_encerra_a_sessao(self):
        self.login_eleitor()
        self.assertRedirects(self.client.post(reverse("logout")), reverse("landing"))
        self.assertNotIn("_auth_user_id", self.client.session)
