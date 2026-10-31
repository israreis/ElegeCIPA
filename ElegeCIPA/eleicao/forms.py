from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm

from .models import Candidato, Eleicao

INPUT_CLASSES = (
    "mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm "
    "focus:border-primary focus:ring-primary sm:text-sm"
)
FIELD_CLASSES = (
    "w-full px-4 py-2 border border-gray-300 rounded-xl "
    "focus:outline-none focus:ring-2 focus:ring-primary"
)


class EleitorLoginForm(forms.Form):
    matricula = forms.CharField(
        label="Matrícula",
        max_length=20,
        widget=forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "Digite sua matrícula"}),
    )
    cpf = forms.RegexField(
        label="CPF",
        regex=r"^\d{11}$",
        max_length=11,
        error_messages={"invalid": "Digite apenas números, com 11 dígitos."},
        widget=forms.PasswordInput(
            attrs={"class": INPUT_CLASSES, "placeholder": "Digite seu CPF", "inputmode": "numeric"}
        ),
    )


class AdminLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Usuário",
        widget=forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "Usuário"}),
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES, "placeholder": "Senha"}),
    )


class EscolherEleicaoForm(forms.Form):
    eleicao = forms.ModelChoiceField(queryset=Eleicao.objects.none())

    def __init__(self, *args, queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["eleicao"].queryset = queryset


class EleicaoForm(forms.ModelForm):
    class Meta:
        model = Eleicao
        fields = ["data_inicio", "data_fim", "vigente"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date", "class": FIELD_CLASSES}, format="%Y-%m-%d"),
            "data_fim": forms.DateInput(attrs={"type": "date", "class": FIELD_CLASSES}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, exibir_vigente=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not exibir_vigente:
            del self.fields["vigente"]


class CandidatoForm(forms.ModelForm):
    class Meta:
        model = Candidato
        fields = ["foto", "nome_completo", "cargo", "setor", "unidade", "eleicao"]
        widgets = {
            "nome_completo": forms.TextInput(attrs={"class": FIELD_CLASSES}),
            "cargo": forms.TextInput(attrs={"class": FIELD_CLASSES}),
            "setor": forms.TextInput(attrs={"class": FIELD_CLASSES}),
            "unidade": forms.Select(attrs={"class": FIELD_CLASSES}),
            "eleicao": forms.Select(attrs={"class": FIELD_CLASSES}),
            "foto": forms.FileInput(attrs={"accept": "image/*", "class": "hidden", "data-file-input": ""}),
        }

    def __init__(self, *args, apenas_vigentes=False, **kwargs):
        super().__init__(*args, **kwargs)
        if apenas_vigentes:
            self.fields["eleicao"].queryset = Eleicao.objects.filter(vigente=True)
        self.fields["eleicao"].empty_label = "Selecione a eleição"
        self.fields["unidade"].choices = [("", "Selecione uma unidade")] + list(Candidato.UNIDADES)

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        if foto and hasattr(foto, "size") and foto.size > settings.MAX_UPLOAD_IMAGE_BYTES:
            limite = settings.MAX_UPLOAD_IMAGE_BYTES // (1024 * 1024)
            raise forms.ValidationError(f"A imagem deve ter no máximo {limite} MB.")
        return foto

    def clean(self):
        cleaned = super().clean()
        eleicao = cleaned.get("eleicao")
        if self.instance.pk and eleicao and eleicao != self.instance.eleicao:
            if self.instance.votos.exists():
                self.add_error("eleicao", "Candidato com votos não pode mudar de eleição.")
        return cleaned
