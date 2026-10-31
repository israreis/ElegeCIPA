import tempfile
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .forms import CandidatoForm
from .models import Candidato, Eleicao, Eleitor, Voto
from .utils import hash_identificador, normalizar_cpf

User = get_user_model()

MATRICULA = "12345"
CPF = "12345678901"
SENHA_ADMIN = "senha-forte-123"


def criar_eleicao(vigente=True, dias_inicio=-1, dias_fim=1):
    agora = timezone.now()
    return Eleicao.objects.create(
        data_inicio=agora + timedelta(days=dias_inicio),
        data_fim=agora + timedelta(days=dias_fim),
        vigente=vigente,
    )


def criar_candidato(eleicao, nome="Ana"):
    return Candidato.objects.create(
        nome_completo=nome, cargo="Analista", setor="Operações", unidade="UN1", eleicao=eleicao
    )


def criar_eleitor(matricula=MATRICULA, cpf=CPF):
    return Eleitor.objects.create(
        matricula_hash=hash_identificador(matricula), cpf_hash=hash_identificador(cpf)
    )


def imagem_png():
    buffer = BytesIO()
    Image.new("RGB", (10, 10), "white").save(buffer, format="PNG")
    return SimpleUploadedFile("foto.png", buffer.getvalue(), content_type="image/png")


class BaseTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.eleicao = criar_eleicao()
        self.candidato = criar_candidato(self.eleicao)
        self.eleitor = criar_eleitor()
        self.admin = User.objects.create_superuser("admin", password=SENHA_ADMIN)

    def login_eleitor(self, matricula=MATRICULA, cpf=CPF):
        return self.client.post(reverse("login"), {"matricula": matricula, "cpf": cpf})

    def login_admin(self):
        self.client.force_login(self.admin)


class UtilsTests(TestCase):
    def test_hash_e_deterministico_e_sensivel_ao_valor(self):
        self.assertEqual(hash_identificador("123"), hash_identificador(" 123 "))
        self.assertNotEqual(hash_identificador("123"), hash_identificador("124"))
        self.assertEqual(len(hash_identificador("123")), 64)

    def test_normalizar_cpf_recupera_zeros_a_esquerda(self):
        self.assertEqual(normalizar_cpf("1234567890"), "01234567890")
        self.assertEqual(normalizar_cpf("123.456.789-01"), "12345678901")
        self.assertEqual(normalizar_cpf(""), "")


class EleicaoModelTests(TestCase):
    def test_nova_eleicao_vigente_desmarca_a_anterior(self):
        primeira = criar_eleicao()
        segunda = criar_eleicao()
        primeira.refresh_from_db()
        self.assertFalse(primeira.vigente)
        self.assertTrue(segunda.vigente)

    def test_data_fim_anterior_ao_inicio_e_invalida(self):
        agora = timezone.now()
        eleicao = Eleicao(data_inicio=agora, data_fim=agora - timedelta(days=1))
        with self.assertRaises(ValidationError):
            eleicao.clean()

    def test_resumo_votos(self):
        eleicao = criar_eleicao()
        candidato = criar_candidato(eleicao)
        Voto.objects.create(eleitor=criar_eleitor("1", "11111111111"), eleicao=eleicao, candidato=candidato)
        Voto.objects.create(
            eleitor=criar_eleitor("2", "22222222222"), eleicao=eleicao, voto_branco=True
        )
        self.assertEqual(eleicao.resumo_votos(), {"total": 2, "brancos": 1, "validos": 1})


class VotoModelTests(BaseTestCase):
    def test_protocolo_gerado_automaticamente(self):
        voto = Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        self.assertRegex(voto.protocolo, rf"^CIPA{voto.data_hora.year}[A-Z0-9]{{6}}$")

    def test_eleitor_vota_uma_unica_vez_por_eleicao(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, voto_branco=True)

    def test_candidato_com_votos_nao_pode_ser_excluido(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        with self.assertRaises(ProtectedError):
            self.candidato.delete()


class LoginTests(BaseTestCase):
    def test_eleitor_valido_entra_e_recebe_usuario_sem_senha_utilizavel(self):
        response = self.login_eleitor()
        self.assertRedirects(response, reverse("candidatos"))
        self.eleitor.refresh_from_db()
        self.assertFalse(self.eleitor.user.has_usable_password())

    def test_credenciais_invalidas_nao_autenticam(self):
        response = self.login_eleitor(cpf="00000000000")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matrícula ou CPF inválidos.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_bloqueio_apos_tentativas_invalidas(self):
        for _ in range(5):
            self.login_eleitor(cpf="00000000000")
        response = self.login_eleitor()
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_superusuario_entra_no_painel(self):
        response = self.client.post(reverse("login"), {"username": "admin", "password": SENHA_ADMIN})
        self.assertRedirects(response, reverse("painel_admin"))

    def test_usuario_comum_nao_entra_como_administrador(self):
        User.objects.create_user("comum", password=SENHA_ADMIN)
        response = self.client.post(reverse("login"), {"username": "comum", "password": SENHA_ADMIN})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_exige_post(self):
        self.login_eleitor()
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("landing"))


class VotacaoTests(BaseTestCase):
    def test_lista_de_candidatos_exige_login(self):
        response = self.client.get(reverse("candidatos"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_registrar_voto_nao_aceita_get(self):
        self.login_eleitor()
        response = self.client.get(reverse("registrar_voto", args=[self.candidato.id]))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(Voto.objects.exists())

    def test_voto_em_candidato_gera_protocolo(self):
        self.login_eleitor()
        response = self.client.post(reverse("registrar_voto", args=[self.candidato.id]))
        voto = Voto.objects.get()
        self.assertRedirects(response, reverse("protocolo_voto", args=[voto.id]))
        self.assertEqual(voto.candidato, self.candidato)
        self.assertContains(self.client.get(reverse("protocolo_voto", args=[voto.id])), voto.protocolo)

    def test_voto_em_branco(self):
        self.login_eleitor()
        self.client.post(reverse("registrar_voto_branco"))
        voto = Voto.objects.get()
        self.assertTrue(voto.voto_branco)
        self.assertIsNone(voto.candidato)

    def test_segundo_voto_e_recusado_e_encerra_a_sessao(self):
        self.login_eleitor()
        self.client.post(reverse("registrar_voto", args=[self.candidato.id]))
        response = self.client.post(reverse("registrar_voto_branco"))
        self.assertRedirects(response, reverse("landing"))
        self.assertEqual(Voto.objects.count(), 1)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_nao_vota_em_candidato_de_outra_eleicao(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        outra = criar_eleicao()
        self.login_eleitor()
        response = self.client.post(reverse("registrar_voto", args=[self.candidato.id]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(outra.votos.count(), 0)

    def test_sem_eleicao_vigente_nao_ha_votacao(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_eleitor()
        response = self.client.post(reverse("registrar_voto_branco"))
        self.assertRedirects(response, reverse("candidatos"))
        self.assertFalse(Voto.objects.exists())

    def test_protocolo_de_outro_eleitor_nao_e_acessivel(self):
        outro = criar_eleitor("999", "99999999999")
        voto = Voto.objects.create(eleitor=outro, eleicao=self.eleicao, candidato=self.candidato)
        self.login_eleitor()
        self.assertEqual(self.client.get(reverse("protocolo_voto", args=[voto.id])).status_code, 404)


class AcessoAdministrativoTests(BaseTestCase):
    URLS_PROTEGIDAS = (
        "painel_admin",
        "apuracao_votos",
        "gerar_extrato_pdf",
        "criar_eleicao",
        "criar_candidato",
        "eleicoes_anteriores",
        "escolher_eleicao_apurar",
        "escolher_eleicao_encerrar",
    )

    def test_eleitor_nao_acessa_area_administrativa(self):
        self.login_eleitor()
        for nome in self.URLS_PROTEGIDAS:
            with self.subTest(url=nome):
                response = self.client.get(reverse(nome))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response["Location"])

    def test_administrador_acessa_paginas(self):
        self.login_admin()
        for nome in ("painel_admin", "apuracao_votos", "criar_candidato", "eleicoes_anteriores"):
            with self.subTest(url=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)

    def test_extrato_pdf(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        self.login_admin()
        response = self.client.get(reverse("gerar_extrato_pdf_especifico", args=[self.eleicao.id]))
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_exclusao_de_candidato_exige_post(self):
        self.login_admin()
        url = reverse("deletar_candidato", args=[self.candidato.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(Candidato.objects.filter(id=self.candidato.id).exists())
        self.client.post(url)
        self.assertFalse(Candidato.objects.filter(id=self.candidato.id).exists())

    def test_candidato_com_votos_nao_e_removido(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        self.login_admin()
        response = self.client.post(reverse("deletar_candidato", args=[self.candidato.id]))
        self.assertRedirects(response, reverse("painel_admin"))
        self.assertTrue(Candidato.objects.filter(id=self.candidato.id).exists())
        mensagens = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("não podem ser removidos" in m for m in mensagens))

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

    def test_eleicao_com_fim_anterior_ao_inicio_e_rejeitada(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_admin()
        response = self.client.post(
            reverse("criar_eleicao"), {"data_inicio": "2026-01-10", "data_fim": "2026-01-01"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Eleicao.objects.count(), 1)

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

    def test_encerrar_eleicao(self):
        self.login_admin()
        url = reverse("encerrar_eleicao", args=[self.eleicao.id])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url)
        self.assertRedirects(response, reverse("apuracao_votos_especifica", args=[self.eleicao.id]))
        self.eleicao.refresh_from_db()
        self.assertFalse(self.eleicao.vigente)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_seletor_rejeita_eleicao_inexistente(self):
        self.login_admin()
        response = self.client.post(reverse("escolher_eleicao_apurar"), {"eleicao": "abc"})
        self.assertEqual(response.status_code, 200)


@override_settings(VAGAS_TITULARES=1, VAGAS_SUPLENTES=1)
class ApuracaoTests(BaseTestCase):
    def test_classifica_titulares_suplentes_e_nao_eleitos(self):
        segundo = criar_candidato(self.eleicao, "Bruno")
        terceiro = criar_candidato(self.eleicao, "Carla")
        sem_votos = criar_candidato(self.eleicao, "Diego")

        votos = [(self.candidato, 1), (segundo, 3), (terceiro, 2)]
        numero = 0
        for candidato, quantidade in votos:
            for _ in range(quantidade):
                numero += 1
                eleitor = criar_eleitor(f"mat{numero}", f"{numero:011d}")
                Voto.objects.create(eleitor=eleitor, eleicao=self.eleicao, candidato=candidato)
        Voto.objects.create(
            eleitor=criar_eleitor("branco", "99999999998"), eleicao=self.eleicao, voto_branco=True
        )

        self.login_admin()
        response = self.client.get(reverse("apuracao_votos_especifica", args=[self.eleicao.id]))

        self.assertEqual([c.id for c in response.context["eleitos"]], [segundo.id])
        self.assertEqual([c.id for c in response.context["suplentes"]], [terceiro.id])
        self.assertEqual([c.id for c in response.context["nao_eleitos"]], [self.candidato.id, sem_votos.id])
        self.assertEqual(response.context["total_votos"], 7)
        self.assertEqual(response.context["votos_brancos"], 1)
        self.assertEqual(response.context["votos_validos"], 6)

    def test_sem_eleicao_vigente_redireciona_ao_painel(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_admin()
        self.assertRedirects(self.client.get(reverse("apuracao_votos")), reverse("painel_admin"))


class CandidatoFormTests(BaseTestCase):
    def dados(self, **extra):
        return {
            "nome_completo": "Maria",
            "cargo": "Técnica",
            "setor": "Qualidade",
            "unidade": "UN2",
            "eleicao": self.eleicao.id,
            **extra,
        }

    def test_formulario_valido_com_foto(self):
        form = CandidatoForm(self.dados(), {"foto": imagem_png()})
        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(MAX_UPLOAD_IMAGE_BYTES=10)
    def test_foto_acima_do_limite_e_rejeitada(self):
        form = CandidatoForm(self.dados(), {"foto": imagem_png()})
        self.assertFalse(form.is_valid())
        self.assertIn("foto", form.errors)

    def test_arquivo_que_nao_e_imagem_e_rejeitado(self):
        arquivo = SimpleUploadedFile("script.html", b"<script>alert(1)</script>", content_type="text/html")
        form = CandidatoForm(self.dados(), {"foto": arquivo})
        self.assertFalse(form.is_valid())
        self.assertIn("foto", form.errors)

    def test_unidade_fora_da_lista_e_rejeitada(self):
        form = CandidatoForm(self.dados(unidade="XX"))
        self.assertFalse(form.is_valid())
        self.assertIn("unidade", form.errors)

    def test_candidato_com_votos_nao_muda_de_eleicao(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        outra = criar_eleicao(vigente=False)
        dados = self.dados(nome_completo=self.candidato.nome_completo, eleicao=outra.id)
        form = CandidatoForm(dados, instance=self.candidato)
        self.assertFalse(form.is_valid())
        self.assertIn("eleicao", form.errors)

    def test_cadastro_novo_so_lista_eleicoes_vigentes(self):
        encerrada = criar_eleicao(vigente=False)
        form = CandidatoForm(apenas_vigentes=True)
        ids = set(form.fields["eleicao"].queryset.values_list("id", flat=True))
        self.assertEqual(ids, {self.eleicao.id})
        self.assertNotIn(encerrada.id, ids)


class ImportMatriculasTests(TestCase):
    def importar(self, conteudo):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "eleitores.csv"
            caminho.write_text(conteudo, encoding="utf-8")
            saida = StringIO()
            call_command("import_matriculas", str(caminho), stdout=saida)
        return saida.getvalue()

    def test_importa_apenas_hashes_e_recupera_zeros_do_cpf(self):
        saida = self.importar("matricula,CPF\n001,1234567890\n002,\n")
        self.assertIn("2 criados", saida)
        eleitor = Eleitor.objects.get(matricula_hash=hash_identificador("001"))
        self.assertEqual(eleitor.cpf_hash, hash_identificador("01234567890"))
        self.assertIsNone(Eleitor.objects.get(matricula_hash=hash_identificador("002")).cpf_hash)

    def test_reimportar_nao_duplica(self):
        self.importar("matricula,CPF\n001,12345678901\n")
        self.importar("matricula,CPF\n001,12345678901\n")
        self.assertEqual(Eleitor.objects.count(), 1)
