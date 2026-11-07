import tomllib
from google import genai

# Lê a chave guardada no arquivo secreto (nunca escreva a chave direto no código)
with open(".streamlit/secrets.toml", "rb") as arquivo:
    chave = tomllib.load(arquivo)["GEMINI_API_KEY"]

# Conecta ao Gemini e faz uma pergunta simples
cliente = genai.Client(api_key=chave)
resposta = cliente.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="Responda em uma frase curta: você está funcionando?",
)

print(resposta.text)
