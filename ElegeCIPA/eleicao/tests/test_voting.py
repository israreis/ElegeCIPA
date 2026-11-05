from django.urls import reverse

from ..models import Voto
from .helpers import BaseTestCase, criar_candidato, criar_eleicao, criar_eleitor


class AcessoDoEleitorTests(BaseTestCase):
    def test_lista_de_candidatos_exige_login(self):
        response = self.client.get(reverse("candidatos"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_visitante_nao_registra_voto(self):
        response = self.client.post(reverse("registrar_voto", args=[self.candidato.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertFalse(Voto.objects.exists())

    def test_visitante_nao_acessa_protocolo(self):
        voto = Voto.objects.create(eleitor=self.eleitor, eleicao=self.eleicao, candidato=self.candidato)
        response = self.client.get(reverse("protocolo_voto", args=[voto.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])


class ListaDeCandidatosTests(BaseTestCase):
    def test_lista_apenas_candidatos_da_eleicao_vigente(self):
        encerrada = criar_eleicao(vigente=False)
        criar_candidato(encerrada, "Candidato Antigo")
        self.login_eleitor()
        response = self.client.get(reverse("candidatos"))
        self.assertContains(response, self.candidato.nome_completo)
        self.assertNotContains(response, "Candidato Antigo")

    def test_exibe_opcao_de_voto_em_branco(self):
        self.login_eleitor()
        self.assertContains(self.client.get(reverse("candidatos")), reverse("confirmar_voto_branco"))

    def test_sem_eleicao_vigente_exibe_aviso(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_eleitor()
        self.assertContains(self.client.get(reverse("candidatos")), "Não há eleição em andamento")

    def test_candidatos_em_ordem_alfabetica(self):
        criar_candidato(self.eleicao, "Zuleica")
        criar_candidato(self.eleicao, "Beatriz")
        self.login_eleitor()
        nomes = [c.nome_completo for c in self.client.get(reverse("candidatos")).context["candidatos"]]
        self.assertEqual(nomes, sorted(nomes))


class ConfirmacaoDeVotoTests(BaseTestCase):
    def test_pagina_de_confirmacao_mostra_o_candidato(self):
        self.login_eleitor()
        response = self.client.get(reverse("confirmar_voto", args=[self.candidato.id]))
        self.assertContains(response, self.candidato.nome_completo)
        self.assertContains(response, reverse("registrar_voto", args=[self.candidato.id]))

    def test_confirmacao_nao_registra_voto(self):
        self.login_eleitor()
        self.client.get(reverse("confirmar_voto", args=[self.candidato.id]))
        self.client.get(reverse("confirmar_voto_branco"))
        self.assertFalse(Voto.objects.exists())

    def test_confirmacao_de_candidato_de_outra_eleicao_retorna_404(self):
        outra = criar_eleicao(vigente=False)
        estranho = criar_candidato(outra, "Estranho")
        self.login_eleitor()
        self.assertEqual(self.client.get(reverse("confirmar_voto", args=[estranho.id])).status_code, 404)

    def test_confirmacao_de_voto_em_branco(self):
        self.login_eleitor()
        self.assertEqual(self.client.get(reverse("confirmar_voto_branco")).status_code, 200)

    def test_sem_eleicao_vigente_confirmacao_volta_para_a_lista(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_eleitor()
        response = self.client.get(reverse("confirmar_voto", args=[self.candidato.id]))
        self.assertRedirects(response, reverse("candidatos"))


class RegistroDeVotoTests(BaseTestCase):
    def test_registrar_voto_nao_aceita_get(self):
        self.login_eleitor()
        response = self.client.get(reverse("registrar_voto", args=[self.candidato.id]))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(Voto.objects.exists())

    def test_registrar_voto_em_branco_nao_aceita_get(self):
        self.login_eleitor()
        self.assertEqual(self.client.get(reverse("registrar_voto_branco")).status_code, 405)
        self.assertFalse(Voto.objects.exists())

    def test_voto_em_candidato_gera_protocolo(self):
        self.login_eleitor()
        response = self.votar(self.candidato)
        voto = Voto.objects.get()
        self.assertRedirects(response, reverse("protocolo_voto", args=[voto.id]))
        self.assertEqual(voto.candidato, self.candidato)
        self.assertFalse(voto.voto_branco)
        self.assertEqual(voto.eleicao, self.eleicao)
        self.assertEqual(voto.eleitor, self.eleitor)
        self.assertContains(self.client.get(reverse("protocolo_voto", args=[voto.id])), voto.protocolo)

    def test_voto_em_branco(self):
        self.login_eleitor()
        self.votar()
        voto = Voto.objects.get()
        self.assertTrue(voto.voto_branco)
        self.assertIsNone(voto.candidato)

    def test_segundo_voto_e_recusado_e_encerra_a_sessao(self):
        self.login_eleitor()
        self.votar(self.candidato)
        response = self.votar()
        self.assertRedirects(response, reverse("landing"))
        self.assertEqual(Voto.objects.count(), 1)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_segundo_voto_no_mesmo_candidato_tambem_e_recusado(self):
        self.login_eleitor()
        self.votar(self.candidato)
        self.votar(self.candidato)
        self.assertEqual(Voto.objects.count(), 1)

    def test_nao_vota_em_candidato_de_outra_eleicao(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        outra = criar_eleicao()
        self.login_eleitor()
        response = self.votar(self.candidato)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(outra.votos.count(), 0)

    def test_sem_eleicao_vigente_nao_ha_votacao(self):
        self.eleicao.vigente = False
        self.eleicao.save()
        self.login_eleitor()
        self.assertRedirects(self.votar(), reverse("candidatos"))
        self.assertFalse(Voto.objects.exists())

    def test_candidato_inexistente_retorna_404(self):
        self.login_eleitor()
        self.assertEqual(self.client.post(reverse("registrar_voto", args=[999999])).status_code, 404)

    def test_voto_de_um_eleitor_nao_afeta_o_outro(self):
        criar_eleitor("999", "99999999999")
        self.login_eleitor()
        self.votar(self.candidato)
        self.client.post(reverse("logout"))
        self.login_eleitor("999", "99999999999")
        self.votar()
        self.assertEqual(Voto.objects.count(), 2)
        self.assertEqual(Voto.objects.filter(voto_branco=True).count(), 1)


class ProtocoloTests(BaseTestCase):
    def test_protocolo_de_outro_eleitor_nao_e_acessivel(self):
        outro = criar_eleitor("999", "99999999999")
        voto = Voto.objects.create(eleitor=outro, eleicao=self.eleicao, candidato=self.candidato)
        self.login_eleitor()
        self.assertEqual(self.client.get(reverse("protocolo_voto", args=[voto.id])).status_code, 404)

    def test_protocolo_inexistente_retorna_404(self):
        self.login_eleitor()
        self.assertEqual(self.client.get(reverse("protocolo_voto", args=[999999])).status_code, 404)

    def test_protocolo_exibe_o_candidato_votado(self):
        self.login_eleitor()
        self.votar(self.candidato)
        voto = Voto.objects.get()
        response = self.client.get(reverse("protocolo_voto", args=[voto.id]))
        self.assertContains(response, "Voto Registrado com Sucesso!")
        self.assertContains(response, self.candidato.nome_completo)

    def test_protocolo_de_voto_em_branco(self):
        self.login_eleitor()
        self.votar()
        voto = Voto.objects.get()
        response = self.client.get(reverse("protocolo_voto", args=[voto.id]))
        self.assertContains(response, "VOTO EM BRANCO")
        self.assertContains(response, voto.protocolo)
