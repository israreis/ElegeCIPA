from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from ..forms import CandidatoForm, EleicaoForm, EleitorLoginForm, EscolherEleicaoForm
from ..models import Eleicao, Voto
from .helpers import BaseTestCase, criar_eleicao, imagem_png


class EleitorLoginFormTests(TestCase):
    def test_dados_validos(self):
        self.assertTrue(EleitorLoginForm({"matricula": "123", "cpf": "12345678901"}).is_valid())

    def test_cpf_deve_ter_11_digitos(self):
        for cpf in ("", "1234567890", "123456789012", "abcdefghijk", "123.456.789-01"):
            with self.subTest(cpf=cpf):
                self.assertFalse(EleitorLoginForm({"matricula": "123", "cpf": cpf}).is_valid())

    def test_matricula_obrigatoria_e_limitada_a_20_caracteres(self):
        self.assertFalse(EleitorLoginForm({"matricula": "", "cpf": "12345678901"}).is_valid())
        self.assertFalse(EleitorLoginForm({"matricula": "1" * 21, "cpf": "12345678901"}).is_valid())

    def test_cpf_e_renderizado_como_campo_de_senha(self):
        self.assertIn('type="password"', str(EleitorLoginForm()["cpf"]))


class EleicaoFormTests(TestCase):
    def dados(self, inicio="2026-01-01", fim="2026-01-10"):
        return {"data_inicio": inicio, "data_fim": fim}

    def test_formulario_valido(self):
        self.assertTrue(EleicaoForm(self.dados()).is_valid())

    def test_fim_anterior_ao_inicio_e_invalido(self):
        form = EleicaoForm(self.dados("2026-01-10", "2026-01-01"))
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_campo_vigente_pode_ser_ocultado(self):
        self.assertNotIn("vigente", EleicaoForm(exibir_vigente=False).fields)
        self.assertIn("vigente", EleicaoForm().fields)

    def test_formulario_com_vigente_aceita_trocar_a_eleicao_atual(self):
        atual = criar_eleicao()
        dados = {**self.dados(), "vigente": "on"}
        form = EleicaoForm(dados)
        self.assertTrue(form.is_valid(), form.errors)
        nova = form.save()
        atual.refresh_from_db()
        self.assertTrue(nova.vigente)
        self.assertFalse(atual.vigente)

    def test_datas_invalidas(self):
        self.assertFalse(EleicaoForm(self.dados("31/02/2026", "texto")).is_valid())


class EscolherEleicaoFormTests(TestCase):
    def test_aceita_somente_eleicoes_do_queryset(self):
        agora = timezone.now()
        permitida = Eleicao.objects.create(data_inicio=agora, data_fim=agora + timedelta(days=1))
        proibida = Eleicao.objects.create(data_inicio=agora, data_fim=agora + timedelta(days=1))
        queryset = Eleicao.objects.filter(id=permitida.id)
        self.assertTrue(EscolherEleicaoForm({"eleicao": permitida.id}, queryset=queryset).is_valid())
        self.assertFalse(EscolherEleicaoForm({"eleicao": proibida.id}, queryset=queryset).is_valid())


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

    def test_foto_e_opcional(self):
        self.assertTrue(CandidatoForm(self.dados()).is_valid())

    @override_settings(MAX_UPLOAD_IMAGE_BYTES=10)
    def test_foto_acima_do_limite_e_rejeitada(self):
        form = CandidatoForm(self.dados(), {"foto": imagem_png()})
        self.assertFalse(form.is_valid())
        self.assertIn("foto", form.errors)

    def test_arquivo_html_e_rejeitado(self):
        arquivo = SimpleUploadedFile("script.html", b"<script>alert(1)</script>", content_type="text/html")
        form = CandidatoForm(self.dados(), {"foto": arquivo})
        self.assertFalse(form.is_valid())
        self.assertIn("foto", form.errors)

    def test_arquivo_com_extensao_de_imagem_mas_conteudo_falso_e_rejeitado(self):
        arquivo = SimpleUploadedFile("falsa.png", b"isto nao e uma imagem", content_type="image/png")
        form = CandidatoForm(self.dados(), {"foto": arquivo})
        self.assertFalse(form.is_valid())
        self.assertIn("foto", form.errors)

    def test_unidade_fora_da_lista_e_rejeitada(self):
        form = CandidatoForm(self.dados(unidade="XX"))
        self.assertFalse(form.is_valid())
        self.assertIn("unidade", form.errors)

    def test_campos_obrigatorios(self):
        form = CandidatoForm({})
        self.assertFalse(form.is_valid())
        for campo in ("nome_completo", "cargo", "setor", "unidade", "eleicao"):
            with self.subTest(campo=campo):
                self.assertIn(campo, form.errors)

    def test_candidato_com_votos_nao_muda_de_eleicao(self):
        Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        outra = criar_eleicao(vigente=False)
        dados = self.dados(nome_completo=self.candidato.nome_completo, eleicao=outra.id)
        form = CandidatoForm(dados, instance=self.candidato)
        self.assertFalse(form.is_valid())
        self.assertIn("eleicao", form.errors)

    def test_candidato_sem_votos_pode_mudar_de_eleicao(self):
        outra = criar_eleicao(vigente=False)
        form = CandidatoForm(self.dados(eleicao=outra.id), instance=self.candidato)
        self.assertTrue(form.is_valid(), form.errors)

    def test_cadastro_novo_so_lista_eleicoes_vigentes(self):
        encerrada = criar_eleicao(vigente=False)
        form = CandidatoForm(apenas_vigentes=True)
        ids = set(form.fields["eleicao"].queryset.values_list("id", flat=True))
        self.assertEqual(ids, {self.eleicao.id})
        self.assertNotIn(encerrada.id, ids)

    def test_edicao_lista_todas_as_eleicoes(self):
        encerrada = criar_eleicao(vigente=False)
        form = CandidatoForm(instance=self.candidato)
        ids = set(form.fields["eleicao"].queryset.values_list("id", flat=True))
        self.assertEqual(ids, {self.eleicao.id, encerrada.id})
