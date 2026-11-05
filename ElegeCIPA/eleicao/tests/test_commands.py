import tempfile
from io import StringIO
from pathlib import Path

import pandas as pd
from django.core.management import CommandError, call_command
from django.test import TestCase

from ..models import Eleitor
from ..utils import hash_identificador


class ImportMatriculasTests(TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)

    def importar(self, conteudo, **opcoes):
        caminho = self.pasta / "eleitores.csv"
        caminho.write_text(conteudo, encoding="utf-8")
        return self.executar(caminho, **opcoes)

    def executar(self, caminho, **opcoes):
        saida = StringIO()
        call_command("import_matriculas", str(caminho), stdout=saida, **opcoes)
        return saida.getvalue()

    def test_importa_apenas_hashes_e_recupera_zeros_do_cpf(self):
        saida = self.importar("matricula,CPF\n001,1234567890\n002,\n")
        self.assertIn("2 criados", saida)
        eleitor = Eleitor.objects.get(matricula_hash=hash_identificador("001"))
        self.assertEqual(eleitor.cpf_hash, hash_identificador("01234567890"))
        self.assertIsNone(Eleitor.objects.get(matricula_hash=hash_identificador("002")).cpf_hash)

    def test_dados_originais_nao_sao_armazenados(self):
        self.importar("matricula,CPF\n001,12345678901\n")
        eleitor = Eleitor.objects.get()
        for valor in (eleitor.matricula_hash, eleitor.cpf_hash):
            self.assertEqual(len(valor), 64)
            self.assertNotIn("12345678901", valor)

    def test_reimportar_nao_duplica(self):
        self.importar("matricula,CPF\n001,12345678901\n")
        saida = self.importar("matricula,CPF\n001,12345678901\n")
        self.assertEqual(Eleitor.objects.count(), 1)
        self.assertIn("0 criados", saida)

    def test_reimportar_completa_cpf_que_estava_ausente(self):
        Eleitor.objects.create(matricula_hash=hash_identificador("001"))
        self.importar("matricula,CPF\n001,12345678901\n")
        eleitor = Eleitor.objects.get()
        self.assertEqual(eleitor.cpf_hash, hash_identificador("12345678901"))

    def test_reimportar_nao_sobrescreve_cpf_existente(self):
        original = hash_identificador("12345678901")
        Eleitor.objects.create(matricula_hash=hash_identificador("001"), cpf_hash=original)
        self.importar("matricula,CPF\n001,99999999999\n")
        self.assertEqual(Eleitor.objects.get().cpf_hash, original)

    def test_cpf_com_pontuacao_e_normalizado(self):
        self.importar("matricula,CPF\n001,123.456.789-01\n")
        self.assertEqual(Eleitor.objects.get().cpf_hash, hash_identificador("12345678901"))

    def test_linhas_sem_matricula_sao_ignoradas(self):
        self.importar("matricula,CPF\n,12345678901\n001,98765432100\n")
        self.assertEqual(Eleitor.objects.count(), 1)

    def test_nomes_de_colunas_personalizados(self):
        self.importar("registro,documento\n001,12345678901\n", mat_col="registro", cpf_col="documento")
        self.assertTrue(Eleitor.objects.filter(matricula_hash=hash_identificador("001")).exists())

    def test_espacos_nos_nomes_das_colunas_sao_tolerados(self):
        self.importar(" matricula , CPF \n001,12345678901\n")
        self.assertEqual(Eleitor.objects.count(), 1)

    def test_coluna_inexistente(self):
        with self.assertRaisesMessage(CommandError, "Coluna 'matricula' não encontrada"):
            self.importar("registro,CPF\n001,12345678901\n")
        self.assertFalse(Eleitor.objects.exists())

    def test_arquivo_inexistente(self):
        with self.assertRaisesMessage(CommandError, "Erro ao ler o arquivo"):
            self.executar(self.pasta / "nao_existe.csv")

    def test_importa_planilha_excel(self):
        caminho = self.pasta / "eleitores.xlsx"
        pd.DataFrame({"matricula": ["001", "002"], "CPF": ["12345678901", "98765432100"]}).to_excel(
            caminho, index=False
        )
        saida = self.executar(caminho)
        self.assertIn("2 criados", saida)
        self.assertEqual(Eleitor.objects.count(), 2)

    def test_matricula_com_zeros_a_esquerda_e_preservada(self):
        self.importar("matricula,CPF\n000123,12345678901\n")
        self.assertTrue(Eleitor.objects.filter(matricula_hash=hash_identificador("000123")).exists())
        self.assertFalse(Eleitor.objects.filter(matricula_hash=hash_identificador("123")).exists())
