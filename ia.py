from google import genai
from google.genai import errors, types
from pydantic import BaseModel

# Se o primeiro modelo estiver sobrecarregado, o app tenta o próximo da lista
MODELOS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]


class DadosCaixa(BaseModel):
    """Formato exato que pedimos para a IA devolver."""

    nome: str
    principio_ativo: str
    dosagem: str
    comprimidos: int
    validade: str  # no formato AAAA-MM-DD, ou vazio se não estiver visível


INSTRUCOES = """
As fotos mostram partes diferentes da MESMA caixa de remédio (frente, laterais, abas).
Junte as informações de todas as fotos e extraia:
- nome: o nome comercial do remédio (ex.: Novalgina). Se for genérico, use o nome da substância.
- principio_ativo: a substância ativa (ex.: Dipirona monoidratada). Se houver mais de uma,
  junte com " + " (ex.: Butilbrometo de escopolamina + Paracetamol).
- dosagem: a concentração (ex.: 500 mg). Se houver mais de uma substância, siga a mesma
  ordem com " + " (ex.: 10 mg + 500 mg).
- comprimidos: a quantidade total de comprimidos da caixa (ex.: "Contém 20 comprimidos" = 20).
  Use 0 se não aparecer.
- validade: a data de VALIDADE no formato AAAA-MM-DD. Na caixa ela costuma vir impressa
  numa aba, junto do lote e da fabricação:
    "V", "VAL" ou "VAL.:" = validade  -> use esta
    "F", "FAB" ou "FAB.:" = fabricação -> nunca use esta
    "L" ou "LOTE" = número do lote     -> ignore
  Se houver só mês e ano (ex.: V12/27), use o último dia desse mês (2027-12-31).
  Use texto vazio se a validade não estiver visível.
Ignore anotações feitas à mão na caixa (ex.: horários escritos com caneta).
Se alguma informação não estiver legível, deixe o campo vazio. Não invente dados.
"""


def ler_caixa(chave_api, imagens):
    """Envia as fotos da caixa para o Gemini e devolve os dados encontrados.

    imagens: lista de pares (conteudo_em_bytes, tipo_da_imagem)
    """
    cliente = genai.Client(api_key=chave_api)
    fotos = [types.Part.from_bytes(data=conteudo, mime_type=tipo) for conteudo, tipo in imagens]
    configuracao = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=DadosCaixa,
    )

    ultimo_erro = None
    for modelo in MODELOS:
        try:
            resposta = cliente.models.generate_content(
                model=modelo,
                contents=[*fotos, INSTRUCOES],
                config=configuracao,
            )
            return resposta.parsed
        except errors.ServerError as erro:  # modelo ocupado: tenta o próximo
            ultimo_erro = erro

    raise ultimo_erro

