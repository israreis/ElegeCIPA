import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from ...models import Eleitor
from ...utils import hash_identificador, normalizar_cpf


class Command(BaseCommand):
    help = "Importa matrículas e CPFs de um arquivo Excel ou CSV, armazenando apenas os hashes."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Caminho do arquivo xlsx/xls/csv")
        parser.add_argument("--sheet", default="0", help="Nome ou índice da planilha (Excel)")
        parser.add_argument("--mat-col", default="matricula", help="Coluna com as matrículas")
        parser.add_argument("--cpf-col", default="CPF", help="Coluna com os CPFs")

    def handle(self, *args, **options):
        dados = self._ler_arquivo(options["file"], options["sheet"])
        dados.columns = [coluna.strip() for coluna in dados.columns]

        for coluna in (options["mat_col"], options["cpf_col"]):
            if coluna not in dados.columns:
                raise CommandError(f"Coluna '{coluna}' não encontrada no arquivo.")

        dados = dados[[options["mat_col"], options["cpf_col"]]].dropna(subset=[options["mat_col"]])

        criados = pulados = 0
        for matricula, cpf in dados.itertuples(index=False, name=None):
            matricula = str(matricula).strip()
            if not matricula:
                pulados += 1
                continue

            cpf = normalizar_cpf(cpf) if pd.notna(cpf) else ""
            cpf_hash = hash_identificador(cpf) if cpf else None

            eleitor, criado = Eleitor.objects.get_or_create(
                matricula_hash=hash_identificador(matricula),
                defaults={"cpf_hash": cpf_hash},
            )
            if criado:
                criados += 1
            elif cpf_hash and not eleitor.cpf_hash:
                eleitor.cpf_hash = cpf_hash
                eleitor.save(update_fields=["cpf_hash"])

        self.stdout.write(
            self.style.SUCCESS(f"Importação concluída: {criados} criados, {pulados} ignorados.")
        )

    def _ler_arquivo(self, caminho, planilha):
        try:
            if caminho.lower().endswith(".csv"):
                return pd.read_csv(caminho, dtype=str)
            return pd.read_excel(caminho, sheet_name=int(planilha) if planilha.isdigit() else planilha, dtype=str)
        except Exception as erro:
            raise CommandError(f"Erro ao ler o arquivo: {erro}") from erro
