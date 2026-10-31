from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError, transaction
from django.db.models import Count, ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AdminLoginForm,
    CandidatoForm,
    EleicaoForm,
    EleitorLoginForm,
    EscolherEleicaoForm,
)
from .models import Candidato, Eleicao, Eleitor, Voto
from .pdf import escrever_extrato, nome_arquivo
from .utils import (
    hash_identificador,
    limpar_falhas_login,
    login_bloqueado,
    registrar_falha_login,
)

User = get_user_model()

superadmin_required = user_passes_test(lambda user: user.is_superuser)

MSG_LOGIN_BLOQUEADO = "Muitas tentativas inválidas. Aguarde alguns minutos e tente novamente."


def _eleicao_vigente():
    return Eleicao.objects.filter(vigente=True).first()


def _eleicao_aberta(request):
    eleicao = _eleicao_vigente()
    if eleicao is None:
        messages.error(request, "Não há eleição vigente no momento.")
    return eleicao


def _usuario_do_eleitor(eleitor):
    if eleitor.user_id is None:
        user = User(username=f"eleitor_{eleitor.pk}")
        user.set_unusable_password()
        user.save()
        eleitor.user = user
        eleitor.save(update_fields=["user"])
    return eleitor.user


def home(request):
    return render(request, "eleicao/landing.html")


def login_view(request):
    context = {
        "eleitor_form": EleitorLoginForm(),
        "admin_form": AdminLoginForm(request),
        "error_eleitor": None,
        "error_admin": None,
        "active_tab": "eleitor",
    }
    if request.method != "POST":
        return render(request, "eleicao/login.html", context)

    if login_bloqueado(request):
        context["error_eleitor"] = context["error_admin"] = MSG_LOGIN_BLOQUEADO
        return render(request, "eleicao/login.html", context, status=429)

    if "username" in request.POST:
        context["active_tab"] = "admin"
        form = context["admin_form"] = AdminLoginForm(request, data=request.POST)
        if form.is_valid() and form.get_user().is_superuser:
            limpar_falhas_login(request)
            login(request, form.get_user())
            return redirect("painel_admin")
        registrar_falha_login(request)
        context["error_admin"] = "Usuário ou senha incorretos, ou sem permissão."
    else:
        form = context["eleitor_form"] = EleitorLoginForm(request.POST)
        if form.is_valid():
            eleitor = (
                Eleitor.objects.select_related("user")
                .filter(
                    matricula_hash=hash_identificador(form.cleaned_data["matricula"]),
                    cpf_hash=hash_identificador(form.cleaned_data["cpf"]),
                )
                .first()
            )
            if eleitor:
                limpar_falhas_login(request)
                login(request, _usuario_do_eleitor(eleitor))
                return redirect("candidatos")
            registrar_falha_login(request)
            context["error_eleitor"] = "Matrícula ou CPF inválidos."

    return render(request, "eleicao/login.html", context)


@require_POST
def logout_view(request):
    logout(request)
    return redirect("landing")


@login_required
def candidatos(request):
    eleicao = _eleicao_vigente()
    lista = Candidato.objects.filter(eleicao=eleicao).order_by("nome_completo") if eleicao else []
    return render(request, "eleicao/candidatos.html", {"candidatos": lista, "eleicao_vigente": eleicao})


@login_required
def confirmar_voto(request, candidato_id):
    eleicao = _eleicao_aberta(request)
    if eleicao is None:
        return redirect("candidatos")
    candidato = get_object_or_404(Candidato, id=candidato_id, eleicao=eleicao)
    return render(request, "eleicao/confirmar_voto.html", {"candidato": candidato})


@login_required
def confirmar_voto_branco(request):
    if _eleicao_aberta(request) is None:
        return redirect("candidatos")
    return render(request, "eleicao/confirmar_voto_branco.html")


def _registrar_voto(request, eleicao, candidato=None):
    eleitor = get_object_or_404(Eleitor, user=request.user)
    try:
        with transaction.atomic():
            voto = Voto.objects.create(
                eleitor=eleitor,
                eleicao=eleicao,
                candidato=candidato,
                voto_branco=candidato is None,
            )
    except IntegrityError:
        logout(request)
        messages.error(request, "Você já votou nesta eleição. Sua sessão foi encerrada.")
        return redirect("landing")
    return redirect("protocolo_voto", voto_id=voto.id)


@login_required
@require_POST
def registrar_voto(request, candidato_id):
    eleicao = _eleicao_aberta(request)
    if eleicao is None:
        return redirect("candidatos")
    candidato = get_object_or_404(Candidato, id=candidato_id, eleicao=eleicao)
    return _registrar_voto(request, eleicao, candidato)


@login_required
@require_POST
def registrar_voto_branco(request):
    eleicao = _eleicao_aberta(request)
    if eleicao is None:
        return redirect("candidatos")
    return _registrar_voto(request, eleicao)


@login_required
def protocolo_voto(request, voto_id):
    voto = get_object_or_404(Voto, id=voto_id, eleitor__user=request.user)
    return render(request, "eleicao/protocolo_voto.html", {"voto": voto})


@superadmin_required
def painel_admin(request):
    eleicao = _eleicao_vigente()
    lista = Candidato.objects.filter(eleicao=eleicao).order_by("nome_completo") if eleicao else []
    return render(
        request,
        "eleicao/painel_admin.html",
        {"candidatos": lista, "eleicao_atual": eleicao, "eleicao_vigente": eleicao},
    )


@superadmin_required
def criar_candidato(request):
    form = CandidatoForm(request.POST or None, request.FILES or None, apenas_vigentes=True)
    if request.method == "POST" and form.is_valid():
        candidato = form.save()
        messages.success(request, f"Candidato {candidato.nome_completo} cadastrado com sucesso!")
        return redirect("painel_admin")
    return render(
        request,
        "eleicao/candidato_form.html",
        {"form": form, "titulo": "Cadastrar Candidato", "icone": "fa-user-plus", "botao": "Salvar Candidato"},
    )


@superadmin_required
def editar_candidato(request, candidato_id):
    candidato = get_object_or_404(Candidato, id=candidato_id)
    form = CandidatoForm(request.POST or None, request.FILES or None, instance=candidato)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Candidato atualizado com sucesso!")
        return redirect("painel_admin")
    return render(
        request,
        "eleicao/candidato_form.html",
        {"form": form, "titulo": "Editar Candidato", "icone": "fa-user-edit", "botao": "Salvar Alterações"},
    )


@superadmin_required
@require_POST
def deletar_candidato(request, candidato_id):
    candidato = get_object_or_404(Candidato, id=candidato_id)
    try:
        candidato.delete()
    except ProtectedError:
        messages.error(request, "Candidatos que já receberam votos não podem ser removidos.")
    else:
        messages.success(request, "Candidato removido com sucesso!")
    return redirect("painel_admin")


@superadmin_required
def criar_eleicao(request):
    if _eleicao_vigente():
        messages.error(request, "Existe eleição em andamento. Encerre-a antes de criar uma nova.")
        return redirect("painel_admin")

    form = EleicaoForm(request.POST or None, exibir_vigente=False)
    if request.method == "POST" and form.is_valid():
        eleicao = form.save(commit=False)
        eleicao.vigente = True
        eleicao.save()
        messages.success(request, f"Eleição criada com sucesso! ID: {eleicao.id}")
        return redirect("painel_admin")
    return render(
        request,
        "eleicao/eleicao_form.html",
        {"form": form, "titulo": "Criar Eleição", "icone": "fa-plus-circle", "botao": "Salvar Eleição"},
    )


@superadmin_required
def editar_eleicao(request, eleicao_id):
    eleicao = get_object_or_404(Eleicao, id=eleicao_id)
    form = EleicaoForm(request.POST or None, instance=eleicao)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Eleição atualizada com sucesso!")
        return redirect("painel_admin")
    return render(
        request,
        "eleicao/eleicao_form.html",
        {"form": form, "titulo": "Editar Eleição", "icone": "fa-edit", "botao": "Salvar"},
    )


@superadmin_required
def eleicoes_anteriores(request):
    eleicoes = Eleicao.objects.filter(vigente=False).order_by("-data_inicio")
    return render(request, "eleicao/eleicoes_anteriores.html", {"eleicoes": eleicoes})


@superadmin_required
def escolher_eleicao_encerrar(request):
    vigentes = Eleicao.objects.filter(vigente=True).order_by("data_inicio")
    if request.method == "POST":
        form = EscolherEleicaoForm(request.POST, queryset=vigentes)
        if form.is_valid():
            return redirect("encerrar_eleicao", eleicao_id=form.cleaned_data["eleicao"].id)
        messages.error(request, "Selecione uma eleição válida.")
    return render(request, "eleicao/escolher_eleicao_encerrar.html", {"eleicoes_ativas": vigentes})


@superadmin_required
def encerrar_eleicao(request, eleicao_id):
    eleicao = get_object_or_404(Eleicao, id=eleicao_id, vigente=True)
    if request.method == "POST":
        eleicao.vigente = False
        eleicao.data_fim = timezone.now()
        eleicao.save()
        messages.success(request, f"Eleição ID {eleicao.id} encerrada com sucesso!")
        return redirect("apuracao_votos_especifica", eleicao_id=eleicao.id)
    return render(request, "eleicao/confirmar_encerramento.html", {"eleicao": eleicao})


@superadmin_required
def escolher_eleicao_apurar(request):
    eleicoes = Eleicao.objects.order_by("-data_inicio")
    if request.method == "POST":
        form = EscolherEleicaoForm(request.POST, queryset=eleicoes)
        if form.is_valid():
            return redirect("apuracao_votos_especifica", eleicao_id=form.cleaned_data["eleicao"].id)
        messages.error(request, "Selecione uma eleição para apurar.")
    return render(request, "eleicao/escolher_eleicao_apurar.html", {"eleicoes": eleicoes})


def _eleicao_ou_vigente(eleicao_id):
    if eleicao_id:
        return get_object_or_404(Eleicao, id=eleicao_id)
    return _eleicao_vigente()


@superadmin_required
def apuracao_votos(request, eleicao_id=None):
    eleicao = _eleicao_ou_vigente(eleicao_id)
    if eleicao is None:
        messages.info(request, "Não há eleição vigente para apurar.")
        return redirect("painel_admin")

    candidatos = list(
        Candidato.objects.filter(eleicao=eleicao)
        .annotate(total_votos=Count("votos"))
        .order_by("-total_votos", "nome_completo")
    )
    com_votos = [candidato for candidato in candidatos if candidato.total_votos > 0]
    sem_votos = [candidato for candidato in candidatos if candidato.total_votos == 0]

    titulares = settings.VAGAS_TITULARES
    limite_suplentes = titulares + settings.VAGAS_SUPLENTES
    resumo = eleicao.resumo_votos()

    return render(
        request,
        "eleicao/apuracao_votos.html",
        {
            "eleitos": com_votos[:titulares],
            "suplentes": com_votos[titulares:limite_suplentes],
            "nao_eleitos": com_votos[limite_suplentes:] + sem_votos,
            "votos_brancos": resumo["brancos"],
            "votos_validos": resumo["validos"],
            "total_votos": resumo["total"],
            "eleicao_atual": eleicao,
        },
    )


@superadmin_required
def gerar_extrato_pdf(request, eleicao_id=None):
    eleicao = _eleicao_ou_vigente(eleicao_id)
    if eleicao is None:
        messages.info(request, "Não há eleição vigente para gerar o extrato.")
        return redirect("painel_admin")

    votos = eleicao.votos.select_related("candidato").order_by("data_hora")
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{nome_arquivo(eleicao)}"'
    escrever_extrato(response, eleicao, votos, eleicao.resumo_votos(), Eleitor.objects.count())
    return response
