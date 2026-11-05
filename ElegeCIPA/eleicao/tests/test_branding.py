from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone


class IdentidadeVisualTests(TestCase):
    def test_nome_do_site_vem_da_configuracao(self):
        with override_settings(SITE_NAME="Minha Votação"):
            response = self.client.get(reverse("landing"))
        self.assertContains(response, "<title>Início - Minha Votação</title>")

    def test_organizacao_aparece_no_rodape(self):
        with override_settings(ORGANIZATION_NAME="Acme Ltda"):
            response = self.client.get(reverse("landing"))
        self.assertContains(response, "Acme Ltda")
        self.assertContains(response, str(timezone.localdate().year))

    def test_nome_do_site_aparece_nas_demais_paginas(self):
        with override_settings(SITE_NAME="Minha Votação"):
            response = self.client.get(reverse("login"))
        self.assertContains(response, "Minha Votação")

    def test_imagens_substituiveis_existem(self):
        for caminho in (
            "eleicao/img/logo.svg",
            "eleicao/img/favicon.svg",
            "eleicao/img/avatar-placeholder.svg",
            "eleicao/css/styles.css",
            "eleicao/js/menu.js",
            "eleicao/js/login.js",
            "eleicao/js/file-input.js",
        ):
            with self.subTest(arquivo=caminho):
                self.assertIsNotNone(finders.find(caminho))
