import hashlib
import hmac

from django.conf import settings
from django.core.cache import cache


def hash_identificador(valor):
    chave = settings.MATRICULA_HASH_KEY.encode("utf-8")
    texto = "" if valor is None else str(valor).strip()
    return hmac.new(chave, texto.encode("utf-8"), hashlib.sha256).hexdigest()


def normalizar_cpf(cpf):
    digitos = "".join(caractere for caractere in str(cpf) if caractere.isdigit())
    return digitos.zfill(11) if digitos else ""


def _chave_falhas(request):
    return f"login-falhas:{request.META.get('REMOTE_ADDR', 'desconhecido')}"


def login_bloqueado(request):
    return cache.get(_chave_falhas(request), 0) >= settings.LOGIN_MAX_ATTEMPTS


def registrar_falha_login(request):
    chave = _chave_falhas(request)
    cache.add(chave, 0, settings.LOGIN_LOCKOUT_SECONDS)
    try:
        cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, settings.LOGIN_LOCKOUT_SECONDS)


def limpar_falhas_login(request):
    cache.delete(_chave_falhas(request))
