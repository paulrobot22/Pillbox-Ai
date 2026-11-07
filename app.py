from datetime import date

import streamlit as st

import banco

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


# ---------- Cadastro manual ----------
st.subheader("Adicionar remédio")

with st.form("cadastro", clear_on_submit=True):
    nome = st.text_input("Nome do remédio *", placeholder="Ex.: Dipirona")
    principio_ativo = st.text_input("Princípio ativo", placeholder="Ex.: Dipirona monoidratada")
    dosagem = st.text_input("Dosagem", placeholder="Ex.: 500 mg")

    coluna1, coluna2 = st.columns(2)
    cartelas = coluna1.number_input("Cartelas", min_value=0, step=1)
    comprimidos = coluna2.number_input("Comprimidos no total", min_value=0, step=1)

    validade = st.date_input("Validade", format="DD/MM/YYYY")

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
            "Princípio ativo": r["principio_ativo"],
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
        
