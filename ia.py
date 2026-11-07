from io import BytesIO

from google import genai
from google.genai import errors, types
from PIL import Image, ImageOps
from pydantic import BaseModel

# Se um modelo estiver ocupado ou sem cota, o app tenta o próximo da lista
MODELOS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]

# Erros temporários: 429 = cota esgotada, 500/503 = servidor ocupado, 504 = demorou demais
ERROS_TEMPORARIOS = (429, 500, 503, 504)

# A busca no Google exige faturamento ativo no Google Cloud.
# No plano gratuito deixamos desligada; mude para True se ativar o faturamento.
USAR_BUSCA_WEB = False

# Os modelos "pensam" antes de responder. Para ler caixas e receitas, pensar pouco
# já basta e deixa a resposta bem mais rápida.
PENSAMENTO_RAPIDO = types.ThinkingConfig(thinking_level="LOW")


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


class ItemReceita(BaseModel):
    """Um remédio da receita, já comparado com o estoque."""

    nome_receitado: str
    dosagem_receitada: str
    id_estoque: int  # id do remédio equivalente no estoque, ou 0 se não houver
    observacao: str  # ex.: "mesma substância, nome comercial diferente"


class ResultadoReceita(BaseModel):
    itens: list[ItemReceita]


INSTRUCOES_RECEITA = """
As fotos mostram uma receita médica (pode ser escrita à mão).
1) Liste cada remédio receitado, com o nome e a dosagem como aparecem na receita.
2) Para cada um, procure no ESTOQUE abaixo um remédio equivalente:
   - mesmo nome, OU mesma substância ativa (ex.: Novalgina = Dipirona genérica).
   - Se encontrar, coloque o id dele em id_estoque. Se não, use 0.
   - Se a substância for a mesma mas a dosagem for diferente, ainda informe o id,
     e explique em observacao (ex.: "mesma substância, mas a dosagem é diferente").
   - Em observacao, explique em poucas palavras por que considerou equivalente
     (ou deixe vazio se não encontrou).
Não copie dados pessoais da receita (nome do paciente, do médico, CRM, endereço).
Se não conseguir ler algum remédio, escreva "ilegível" no nome. Não invente remédios.

ESTOQUE (id | nome | substância | dosagem):
"""


def _cliente(chave_api):
    """Cria a conexão com o Gemini sem repetições automáticas (nós mesmos trocamos de modelo)."""
    return genai.Client(
        api_key=chave_api,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1),
            timeout=30_000,  # desiste depois de 30 segundos e tenta o próximo modelo
        ),
    )


def _preparar_foto(conteudo):
    """Diminui a foto antes de enviar: fica mais rápido e gasta menos cota.

    Fotos de celular costumam ter mais de 3000 pixels; 1600 já é suficiente para ler a caixa.
    """
    imagem = Image.open(BytesIO(conteudo))
    imagem = ImageOps.exif_transpose(imagem)  # corrige fotos tiradas "deitadas"
    imagem = imagem.convert("RGB")
    imagem.thumbnail((1600, 1600))
    saida = BytesIO()
    imagem.save(saida, format="JPEG", quality=85)
    return types.Part.from_bytes(data=saida.getvalue(), mime_type="image/jpeg")


def _gerar(cliente, conteudo, configuracao):
    """Chama o Gemini tentando cada modelo da lista até um responder."""
    ultimo_erro = None
    for modelo in MODELOS:
        try:
            return cliente.models.generate_content(
                model=modelo, contents=conteudo, config=configuracao
            )
        except Exception as erro:
            if isinstance(erro, errors.APIError) and erro.code not in ERROS_TEMPORARIOS:
                raise  # erro "de verdade" (ex.: pedido inválido): não adianta tentar de novo
            ultimo_erro = erro  # cota, servidor ocupado ou demora: tenta o próximo modelo
    raise ultimo_erro


def ler_caixa(chave_api, imagens):
    """Envia as fotos da caixa para o Gemini e devolve os dados encontrados.

    imagens: lista de pares (conteudo_em_bytes, tipo_da_imagem)
    """
    cliente = _cliente(chave_api)
    fotos = [_preparar_foto(conteudo) for conteudo, _tipo in imagens]
    configuracao = types.GenerateContentConfig(
        response_mime_type="application/json",
        thinking_config=PENSAMENTO_RAPIDO,
        response_schema=DadosCaixa,
    )
    resposta = _gerar(cliente, [*fotos, INSTRUCOES], configuracao)
    return resposta.parsed


def ler_receita(chave_api, imagens, estoque):
    """Lê a receita e compara cada remédio com o estoque de casa.

    imagens: lista de pares (conteudo_em_bytes, tipo_da_imagem)
    estoque: lista de remédios vinda do banco (dicionários)
    """
    cliente = _cliente(chave_api)
    fotos = [_preparar_foto(conteudo) for conteudo, _tipo in imagens]
    lista_estoque = "\n".join(
        f'{r["id"]} | {r["nome"]} | {r["principio_ativo"]} | {r["dosagem"]}' for r in estoque
    ) or "(estoque vazio)"
    configuracao = types.GenerateContentConfig(
        response_mime_type="application/json",
        thinking_config=PENSAMENTO_RAPIDO,
        response_schema=ResultadoReceita,
    )
    resposta = _gerar(cliente, [*fotos, INSTRUCOES_RECEITA + lista_estoque], configuracao)
    return resposta.parsed.itens


def para_que_serve(chave_api, nome, substancia):
    """Diz para que serve o remédio.

    Devolve (resumo, lista de fontes, verificado).
    verificado = True quando a resposta veio de uma pesquisa na web com fontes.
    """
    cliente = _cliente(chave_api)
    remedio = f'"{nome}" (substância: {substancia or "não informada"})'
    formato = """
Responda em português simples, para uma pessoa leiga:
- Para que serve (as indicações), em até 4 tópicos curtos.
Não informe dose, posologia nem recomende o uso.
"""

    # 1) Pesquisa a bula na web, se a busca estiver ligada
    if USAR_BUSCA_WEB:
        try:
            resposta = _gerar(
                cliente,
                f"Pesquise a bula do remédio {remedio}, de preferência no Bulário Eletrônico "
                f"da Anvisa ou na bula do fabricante.{formato}"
                "Se não encontrar uma fonte confiável, diga apenas que não encontrou.",
                types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
            )
        except errors.APIError as erro:
            if erro.code != 429:
                raise
            # sem cota de busca: segue para a resposta sem pesquisa, abaixo
        else:
            fontes = []
            metadados = resposta.candidates[0].grounding_metadata if resposta.candidates else None
            if metadados and metadados.grounding_chunks:
                for trecho in metadados.grounding_chunks:
                    if trecho.web and trecho.web.uri:
                        fontes.append((trecho.web.title or trecho.web.uri, trecho.web.uri))
            return resposta.text, fontes, True

    # 2) Sem busca: usa o conhecimento da própria IA (sem fontes)
    resposta = _gerar(
        cliente,
        f"Com base no seu conhecimento, explique para que serve o remédio {remedio}.{formato}"
        "Se não conhecer este remédio, diga apenas que não sabe.",
        types.GenerateContentConfig(thinking_config=PENSAMENTO_RAPIDO),
    )
    return resposta.text, [], False