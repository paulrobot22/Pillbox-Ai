import sqlite3
from pathlib import Path

# O banco fica na mesma pasta do projeto, num arquivo chamado pillbox.db
CAMINHO_BANCO = Path(__file__).parent / "pillbox.db"


def conectar():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    conexao.row_factory = sqlite3.Row  # permite acessar as colunas pelo nome
    return conexao


def criar_tabela():
    with conectar() as conexao:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS remedios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                principio_ativo TEXT,
                dosagem TEXT,
                cartelas INTEGER DEFAULT 0,
                comprimidos INTEGER DEFAULT 0,
                validade TEXT
            )
            """
        )


def adicionar_remedio(nome, principio_ativo, dosagem, cartelas, comprimidos, validade):
    with conectar() as conexao:
        conexao.execute(
            """
            INSERT INTO remedios (nome, principio_ativo, dosagem, cartelas, comprimidos, validade)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nome, principio_ativo, dosagem, cartelas, comprimidos, validade),
        )


def listar_remedios():
    with conectar() as conexao:
        linhas = conexao.execute("SELECT * FROM remedios ORDER BY validade").fetchall()
    return [dict(linha) for linha in linhas]


def remover_remedio(id_remedio):
    with conectar() as conexao:
        conexao.execute("DELETE FROM remedios WHERE id = ?", (id_remedio,))
        