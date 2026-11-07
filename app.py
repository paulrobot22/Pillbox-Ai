from datetime import date

import streamlit as st

import banco
import ia

st.set_page_config(page_title="PillBox AI", page_icon="💊")
banco.criar_tabela()

st.title("💊 PillBox AI")
st.write("Controle os remédios que você tem em casa e descubra, antes de ir à farmácia, se já tem o que o médico receitou.")


def situacao_validade(validade_texto):
    """Diz se o remédio está vencido, perto de vencer ou dentro da validade."""
    dias_restantes = (date.fromisoformat(validade_texto) - date.today()).days
    if dias_restantes < 0:
        return "🔴 Vencido"
    if dias_restantes <= 30:
        return "🟡 Vence em breve"
    return "🟢 OK"


# ---------- Cadastro ----------
st.subheader("Adicionar remédio")

# 1) Leitura da caixa com IA: preenche o formulário automaticamente
fotos = st.file_uploader(
    "📸 Fotos da caixa (opcional, até 6)",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help="Mínimo recomendado: a frente da caixa e a aba onde ficam o lote e a validade. Pode enviar até 6 fotos, uma de cada lado.",
)

if fotos and len(fotos) > 6:
    st.warning("Envie no máximo 6 fotos, uma de cada lado da caixa.")
elif fotos and st.button("Ler caixa com IA"):
    with st.spinner("Lendo a caixa..."):
        try:
            imagens = [(foto.getvalue(), foto.type) for foto in fotos]
            dados = ia.ler_caixa(st.secrets["GEMINI_API_KEY"], imagens)
        except Exception as erro:
            st.error("Não consegui ler a foto agora. Tente de novo em instantes ou preencha à mão.")
            with st.expander("Detalhes técnicos"):
                st.code(str(erro))

        else:
            st.session_state["campo_nome"] = dados.nome
            st.session_state["campo_substancia"] = dados.principio_ativo
            st.session_state["campo_dosagem"] = dados.dosagem
            st.session_state["campo_comprimidos"] = max(dados.comprimidos, 0)
            try:
                st.session_state["campo_validade"] = date.fromisoformat(dados.validade)
            except ValueError:
                pass  # validade não encontrada na foto: o usuário preenche
            st.success("Pronto! Confira os dados abaixo, ajuste se precisar e clique em Salvar.")

# 2) Formulário (preenchido pela IA ou à mão)
with st.form("cadastro", clear_on_submit=True):
    nome = st.text_input("Nome do remédio *", placeholder="Ex.: Dipirona", key="campo_nome")
    principio_ativo = st.text_input(
        "Substância (opcional)",
        placeholder="Ex.: Dipirona monoidratada",
        help="É o nome da substância que vem escrito na caixa, geralmente embaixo do nome do remédio. Ajuda o app a reconhecer genéricos.",
        key="campo_substancia",
    )
    dosagem = st.text_input("Dosagem", placeholder="Ex.: 500 mg", key="campo_dosagem")

    coluna1, coluna2 = st.columns(2)
    cartelas = coluna1.number_input("Cartelas", min_value=0, step=1, key="campo_cartelas")
    comprimidos = coluna2.number_input("Comprimidos no total", min_value=0, step=1, key="campo_comprimidos")

    validade = st.date_input("Validade", format="DD/MM/YYYY", key="campo_validade")

    enviado = st.form_submit_button("Salvar")

if enviado:
    if not nome.strip():
        st.error("Informe pelo menos o nome do remédio.")
    else:
        banco.adicionar_remedio(
            nome.strip(),
            principio_ativo.strip(),
            dosagem.strip(),
            int(cartelas),
            int(comprimidos),
            validade.isoformat(),
        )
        st.success(f"{nome.strip()} adicionado ao estoque!")


# ---------- Estoque ----------
st.subheader("Meu estoque")

remedios = banco.listar_remedios()

if not remedios:
    st.info("Nenhum remédio cadastrado ainda.")
else:
    tabela = [
        {
            "Remédio": r["nome"],
            "Substância": r["principio_ativo"],
            "Dosagem": r["dosagem"],
            "Cartelas": r["cartelas"],
            "Comprimidos": r["comprimidos"],
            "Validade": date.fromisoformat(r["validade"]).strftime("%d/%m/%Y"),
            "Situação": situacao_validade(r["validade"]),
        }
        for r in remedios
    ]
    st.dataframe(tabela, hide_index=True, width="stretch")

    # Remover um remédio do estoque
    opcoes = {f'#{r["id"]} – {r["nome"]} {r["dosagem"]}': r["id"] for r in remedios}
    escolhido = st.selectbox("Remover do estoque", list(opcoes.keys()))
    if st.button("Remover"):
        banco.remover_remedio(opcoes[escolhido])
        st.rerun()
        
