from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from ..utils import (
    hash_identificador,
    limpar_falhas_login,
    login_bloqueado,
    normalizar_cpf,
    registrar_falha_login,
)


class HashTests(TestCase):
    def test_hash_e_deterministico_e_ignora_espacos_nas_pontas(self):
        self.assertEqual(hash_identificador("123"), hash_identificador(" 123 "))

    def test_valores_diferentes_geram_hashes_diferentes(self):
        self.assertNotEqual(hash_identificador("123"), hash_identificador("124"))

    def test_hash_tem_64_caracteres_hexadecimais(self):
        self.assertRegex(hash_identificador("123"), r"^[0-9a-f]{64}$")

    def test_hash_depende_da_chave_secreta(self):
        with override_settings(MATRICULA_HASH_KEY="chave-a"):
            a = hash_identificador("123")
        with override_settings(MATRICULA_HASH_KEY="chave-b"):
            b = hash_identificador("123")
        self.assertNotEqual(a, b)

    def test_hash_nao_contem_o_valor_original(self):
        self.assertNotIn("12345678901", hash_identificador("12345678901"))

    def test_valor_nulo_nao_quebra(self):
        self.assertEqual(hash_identificador(None), hash_identificador(""))


class NormalizarCpfTests(TestCase):
    def test_recupera_zeros_a_esquerda(self):
        self.assertEqual(normalizar_cpf("1234567890"), "01234567890")

    def test_remove_pontuacao(self):
        self.assertEqual(normalizar_cpf("123.456.789-01"), "12345678901")

    def test_vazio_permanece_vazio(self):
        self.assertEqual(normalizar_cpf(""), "")

    def test_aceita_numero_inteiro(self):
        self.assertEqual(normalizar_cpf(1234567890), "01234567890")


class LimitadorDeLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def requisicao(self, ip="10.0.0.1"):
        return self.factory.post("/login/", REMOTE_ADDR=ip)

    def test_bloqueia_somente_ao_atingir_o_limite(self):
        request = self.requisicao()
        for _ in range(4):
            registrar_falha_login(request)
        self.assertFalse(login_bloqueado(request))
        registrar_falha_login(request)
        self.assertTrue(login_bloqueado(request))

    def test_limpar_falhas_libera_o_acesso(self):
        request = self.requisicao()
        for _ in range(5):
            registrar_falha_login(request)
        limpar_falhas_login(request)
        self.assertFalse(login_bloqueado(request))

    def test_enderecos_diferentes_sao_independentes(self):
        for _ in range(5):
            registrar_falha_login(self.requisicao("10.0.0.1"))
        self.assertTrue(login_bloqueado(self.requisicao("10.0.0.1")))
        self.assertFalse(login_bloqueado(self.requisicao("10.0.0.2")))

    @override_settings(LOGIN_MAX_ATTEMPTS=2)
    def test_respeita_o_limite_configurado(self):
        request = self.requisicao()
        registrar_falha_login(request)
        registrar_falha_login(request)
        self.assertTrue(login_bloqueado(request))
