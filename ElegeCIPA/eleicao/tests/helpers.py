import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from ..models import Candidato, Eleicao, Eleitor
from ..utils import hash_identificador

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


def criar_candidato(eleicao, nome="Ana", unidade="UN1"):
    return Candidato.objects.create(
        nome_completo=nome,
        cargo="Analista",
        setor="Operações",
        unidade=unidade,
        eleicao=eleicao,
    )


def criar_eleitor(matricula=MATRICULA, cpf=CPF):
    return Eleitor.objects.create(
        matricula_hash=hash_identificador(matricula),
        cpf_hash=hash_identificador(cpf),
    )


def imagem_png(nome="foto.png"):
    buffer = BytesIO()
    Image.new("RGB", (10, 10), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="image/png")


class BaseTestCase(TestCase):
    """Cenário padrão: uma eleição vigente, um candidato, um eleitor e um superusuário."""

    def setUp(self):
        cache.clear()
        self._isolar_media()
        self.eleicao = criar_eleicao()
        self.candidato = criar_candidato(self.eleicao)
        self.eleitor = criar_eleitor()
        self.admin = User.objects.create_superuser("admin", password=SENHA_ADMIN)

    def _isolar_media(self):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        configuracao = override_settings(MEDIA_ROOT=pasta)
        configuracao.enable()
        self.addCleanup(configuracao.disable)

    def login_eleitor(self, matricula=MATRICULA, cpf=CPF):
        from django.urls import reverse

        return self.client.post(reverse("login"), {"matricula": matricula, "cpf": cpf})

    def login_admin(self):
        self.client.force_login(self.admin)

    def votar(self, candidato=None):
        from django.urls import reverse

        if candidato is None:
            return self.client.post(reverse("registrar_voto_branco"))
        return self.client.post(reverse("registrar_voto", args=[candidato.id]))
