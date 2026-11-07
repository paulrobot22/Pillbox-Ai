import base64
from datetime import date
from pathlib import Path
from urllib.parse import quote

import streamlit as st

import banco
import ia

st.set_page_config(page_title="PillBox AI", page_icon="💊", layout="centered")
banco.criar_tabela()


def situacao_validade(validade_texto):
    """Diz se o remédio está vencido, perto de vencer ou dentro da validade."""
    dias_restantes = (date.fromisoformat(validade_texto) - date.today()).days
    if dias_restantes < 0:
        return "🔴 Vencido"
    if dias_restantes <= 30:
        return "🟡 Vence em breve"
    return "🟢 OK"


@st.cache_data(show_spinner=False)
def buscar_bula(nome, substancia):
    """Guarda o resultado na memória para não repetir a mesma pesquisa (economiza a cota gratuita)."""
    return ia.para_que_serve(st.secrets["GEMINI_API_KEY"], nome, substancia)


def mostrar_previa(fotos):
    """Mostra miniaturas das fotos enviadas."""
    if fotos:
        st.image(list(fotos), width=110)


# ---------- Visual: cartão central e cabeçalho com logo ----------
st.markdown(
    """
    <style>
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stMainBlockContainer"], .block-container {
        background: #FFFFFF;
        border-radius: 24px;
        box-shadow: 0 8px 30px rgba(0, 80, 50, 0.08);
        margin-top: 3.5rem;
        padding: 2rem 2rem 3rem 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

logo_base64 = base64.b64encode(Path(__file__).with_name("logo.svg").read_bytes()).decode()
st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, #007A4A 0%, #00995D 55%, #2DBE7E 100%);
                padding: 1.4rem 1.6rem; border-radius: 20px; margin-bottom: 1rem;
                display: flex; align-items: center; gap: 1rem;">
        <img src="data:image/svg+xml;base64,{logo_base64}" width="64" height="64"
             style="border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" alt="Logo PillBox AI">
        <div>
            <h1 style="color: white; margin: 0; padding: 0; font-size: 2.1rem;">PillBox AI</h1>
            <p style="color: #E8FFF3; margin: 0.2rem 0 0 0; font-size: 1.02rem;">
                Seus remédios de casa organizados, com uma ajudinha da IA.
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

aba_receita, aba_adicionar, aba_estoque = st.tabs(
    ["📝 Tenho em casa?", "➕ Adicionar remédio", "📦 Meu estoque"]
)


# ---------- Aba 1: Consultar receita ----------
with aba_receita:
    st.subheader("Tenho em casa?")
    st.caption("Fotografe a receita e descubra o que você já tem antes de ir à farmácia.")

    fotos_receita = st.file_uploader(
        "Fotos da receita",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="fotos_receita",
    )
    mostrar_previa(fotos_receita)

    if fotos_receita and st.button("Consultar receita", type="primary"):
        estoque = banco.listar_remedios()
        with st.spinner("Lendo a receita..."):
            try:
                imagens = [(foto.getvalue(), foto.type) for foto in fotos_receita]
                itens = ia.ler_receita(st.secrets["GEMINI_API_KEY"], imagens, estoque)
            except Exception as erro:
                st.error("Não consegui ler a receita agora. Tente de novo em instantes.")
                with st.expander("Detalhes técnicos"):
                    st.code(str(erro))
            else:
                por_id = {r["id"]: r for r in estoque}
                if not itens:
                    st.info("Não encontrei remédios nessa receita. Tente uma foto mais nítida.")
                for item in itens:
                    receitado = f"**{item.nome_receitado}** {item.dosagem_receitada}"
                    remedio = por_id.get(item.id_estoque)
                    if remedio is None:
                        st.error(f"❌ {receitado}: você não tem em casa. Precisa comprar.")
                    else:
                        validade = date.fromisoformat(remedio["validade"]).strftime("%d/%m/%Y")
                        detalhes = (
                            f'{remedio["nome"]} {remedio["dosagem"]}: {remedio["cartelas"]} cartela(s), '
                            f'{remedio["comprimidos"]} comprimido(s), validade {validade}'
                        )
                        if situacao_validade(remedio["validade"]).startswith("🔴"):
                            st.warning(f"⚠️ {receitado}: você tem ({detalhes}), mas está **vencido**. Precisa comprar.")
                        else:
                            st.success(f"✅ {receitado}: você tem em casa! {detalhes}.")
                    if item.observacao:
                        st.caption(f"ℹ️ {item.observacao}")
                st.caption("Na dúvida se o remédio de casa equivale ao receitado, confirme com o farmacêutico.")


# ---------- Aba 2: Adicionar remédio ----------
with aba_adicionar:
    st.subheader("Adicionar remédio")

    # 1) Leitura da caixa com IA: preenche o formulário automaticamente
    fotos = st.file_uploader(
        "📸 Fotos da caixa (opcional, até 6)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        help="Mínimo recomendado: a frente da caixa e a aba onde ficam o lote e a validade. Pode enviar até 6 fotos, uma de cada lado.",
    )
    mostrar_previa(fotos)

    if fotos and len(fotos) > 6:
        st.warning("Envie no máximo 6 fotos, uma de cada lado da caixa.")
    elif fotos and st.button("✨ Ler caixa com IA", type="primary"):
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

        enviado = st.form_submit_button("💾 Salvar", type="primary")

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


# ---------- Aba 3: Meu estoque ----------
with aba_estoque:
    remedios = banco.listar_remedios()

    # Resumo em números
    situacoes = [situacao_validade(r["validade"]) for r in remedios]
    total, em_breve, vencidos = st.columns(3)
    total.metric("💊 Remédios", len(remedios))
    em_breve.metric("🟡 Vencem em 30 dias", sum(s.startswith("🟡") for s in situacoes))
    vencidos.metric("🔴 Vencidos", sum(s.startswith("🔴") for s in situacoes))

    if not remedios:
        st.info("Nenhum remédio cadastrado ainda. Comece pela aba ➕ Adicionar remédio.")
    else:
        tabela = [
            {
                "Remédio": r["nome"],
                "Dosagem": r["dosagem"],
                "Situação": situacao,
                "Validade": date.fromisoformat(r["validade"]).strftime("%d/%m/%Y"),
                "Comprimidos": r["comprimidos"],
                "Cartelas": r["cartelas"],
                "Substância": r["principio_ativo"],
            }
            for r, situacao in zip(remedios, situacoes)
        ]
        st.dataframe(tabela, hide_index=True, width="stretch")

        # Para que serve? (pesquisa a bula na web)
        st.subheader("🔎 Para que serve?")
        por_rotulo = {f'#{r["id"]} – {r["nome"]} {r["dosagem"]}': r for r in remedios}
        rotulo = st.selectbox("Escolha um remédio", list(por_rotulo.keys()), key="escolha_bula")
        if st.button("Buscar na bula", type="primary"):
            remedio = por_rotulo[rotulo]
            with st.spinner("Pesquisando a bula..."):
                try:
                    texto, fontes, verificado = buscar_bula(remedio["nome"], remedio["principio_ativo"])
                except Exception as erro:
                    st.error("Não consegui pesquisar a bula agora. Tente de novo em instantes.")
                    with st.expander("Detalhes técnicos"):
                        st.code(str(erro))
                else:
                    if not verificado:
                        st.info("ℹ️ Resposta da IA sem consulta à bula. Confirme na bula oficial pelo link abaixo.")
                    st.markdown(texto)
                    if fontes:
                        st.caption("Fontes consultadas:")
                        for titulo, link in fontes:
                            st.markdown(f"- [{titulo}]({link})")
                    link_anvisa = "https://consultas.anvisa.gov.br/#/bulario/q/?nomeProduto=" + quote(remedio["nome"])
                    st.markdown(f"📄 [Ver a bula oficial no Bulário Eletrônico da Anvisa]({link_anvisa})")
                    st.warning("Informação de apoio. Não substitui a orientação de um médico ou farmacêutico nem a leitura da bula completa.")

        # Remover um remédio do estoque
        with st.expander("🗑️ Remover um remédio"):
            opcoes = {f'#{r["id"]} – {r["nome"]} {r["dosagem"]}': r["id"] for r in remedios}
            escolhido = st.selectbox("Qual remédio?", list(opcoes.keys()))
            if st.button("Remover"):
                banco.remover_remedio(opcoes[escolhido])
                st.rerun()
                