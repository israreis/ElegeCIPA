from django.conf import settings
from django.utils.timezone import localtime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

LINE_HEIGHT = 0.5 * cm
COLUMNS = (("#", 1 * cm), ("Data / Hora", 2 * cm), ("Candidato", 7 * cm), ("Protocolo", 14 * cm))


def _draw_table_header(pdf, y):
    pdf.setFont("Helvetica-Bold", 11)
    for title, x in COLUMNS:
        pdf.drawString(x, y, title)
    pdf.setFont("Helvetica", 10)
    return y - LINE_HEIGHT


def periodo_texto(eleicao):
    return f"{eleicao.data_inicio:%d/%m/%Y} a {eleicao.data_fim:%d/%m/%Y}"


def nome_arquivo(eleicao):
    return f"Apuracao_CIPA_{eleicao.data_inicio:%d_%m_%Y}_{eleicao.data_fim:%d_%m_%Y}.pdf"


def escrever_extrato(destino, eleicao, votos, resumo, total_eleitores):
    pdf = canvas.Canvas(destino, pagesize=A4)
    _, altura = A4
    periodo = periodo_texto(eleicao)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2 * cm, altura - 2 * cm, f"Extrato de Votos - Eleições CIPA {periodo}")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(2 * cm, altura - 2.7 * cm, settings.ORGANIZATION_NAME)

    y = _draw_table_header(pdf, altura - 3.5 * cm)

    for numero, voto in enumerate(votos, start=1):
        if y < 2 * cm:
            pdf.showPage()
            y = _draw_table_header(pdf, altura - 2 * cm)

        linha = (
            f"{numero}.",
            f"{localtime(voto.data_hora):%d/%m/%Y %H:%M:%S}",
            voto.candidato_nome,
            voto.protocolo,
        )
        for (_, x), texto in zip(COLUMNS, linha):
            pdf.drawString(x, y, texto)
        y -= LINE_HEIGHT

    if y < 6 * cm:
        pdf.showPage()
        y = altura - 2 * cm

    participacao = (resumo["total"] / total_eleitores * 100) if total_eleitores else 0
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(2 * cm, y - 1 * cm, "RESUMO DA ELEIÇÃO")
    pdf.setFont("Helvetica-Bold", 11)
    linhas_resumo = (
        f"Total de votos: {resumo['total']}",
        f"Total de votos válidos: {resumo['validos']}",
        f"Total de votos em branco: {resumo['brancos']}",
        f"Participação dos eleitores: {participacao:.2f}%",
        f"Período da eleição: {periodo}",
    )
    for indice, texto in enumerate(linhas_resumo):
        pdf.drawString(2 * cm, y - (1.7 + 0.7 * indice) * cm, texto)

    pdf.save()
