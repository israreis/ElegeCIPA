from django.contrib import admin

from .models import Candidato, Eleicao, Voto


@admin.register(Eleicao)
class EleicaoAdmin(admin.ModelAdmin):
    list_display = ("id", "data_inicio", "data_fim", "vigente")
    list_filter = ("vigente",)


@admin.register(Candidato)
class CandidatoAdmin(admin.ModelAdmin):
    list_display = ("nome_completo", "cargo", "setor", "unidade", "eleicao")
    list_filter = ("eleicao", "unidade")
    search_fields = ("nome_completo", "cargo", "setor")


@admin.register(Voto)
class VotoAdmin(admin.ModelAdmin):
    list_display = ("protocolo", "eleicao", "candidato", "voto_branco", "data_hora")
    list_filter = ("eleicao", "voto_branco")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
