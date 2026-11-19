"""
Camada de acesso ao banco SQLite.

Por que SQLite?
    • É um arquivo só: copiar o arquivo = copiar toda a memória do assistente.
    • Já vem embutido no Python: zero instalação, zero servidor.
    • Tem busca textual nativa (FTS5) com ranking BM25 — usamos isso no
      algoritmo de busca padrão.
    • Aguenta bases de vários gigabytes, muito além do que uma pessoa ensina.

Esta classe só sabe LER e GRAVAR. Ela não entende linguagem: quem calcula o
texto de busca (radicais) é o Assistente, que então chama `salvar_conhecimento`
já com esse texto pronto. Essa separação deixa cada parte simples e testável.

Contadores de versão
    `versao_conhecimento` e `versao_linguagem` aumentam a cada alteração.
    Os algoritmos que montam índices em memória (TF-IDF, fuzzy) comparam
    esses números para saber quando o índice ficou desatualizado — um jeito
    barato de invalidar cache.
"""

from __future__ import annotations

import json
import random
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aprendiz.memoria import sementes

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

-- Tudo o que o assistente sabe. Quatro tipos:
--   pergunta → par pergunta/resposta  ("horário da farmácia" → "8h às 20h")
--   nota     → informação solta       ("levar o carro na revisão em março")
--   trecho   → pedaço de um arquivo importado
--   verbete  → entrada de dicionário (addons): só responde quando a pergunta
--              é a palavra sozinha ou "o que significa <palavra>"
CREATE TABLE IF NOT EXISTS conhecimentos (
    id            TEXT PRIMARY KEY,
    tipo          TEXT NOT NULL CHECK (tipo IN ('pergunta', 'nota', 'trecho', 'verbete')),
    pergunta      TEXT,
    conteudo      TEXT NOT NULL,
    origem        TEXT NOT NULL DEFAULT 'manual',
    texto_busca   TEXT NOT NULL DEFAULT '',   -- radicais, gerados pelo pipeline
    addon_id      TEXT,                       -- NULL = ensinado pelo dono
    criado_em     TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    -- Listas em JSON, preenchidas por addons (NULL no que o dono ensina):
    --   variacoes → outras formas de fazer a mesma pergunta (ou de escrever o
    --               termo de um verbete): "busao", "buzao"
    --   traducoes → só em verbetes: o equivalente em português padrão, para
    --               a busca inversa ("como se diz ônibus em Portugal?")
    variacoes     TEXT,
    traducoes     TEXT,
    -- Só em verbetes (0.8+): a variedade regional ou a língua do termo
    -- ("nordeste", "kriol"), declarada no manifesto do addon.
    variedade     TEXT,
    -- Teia de porquês (2.0), em JSON: {ref, assuntos, porques, raiz}.
    teia          TEXT
);

-- Índice de busca textual (FTS5). Guarda só o id e o texto de busca.
CREATE VIRTUAL TABLE IF NOT EXISTS conhecimentos_fts
    USING fts5(id UNINDEXED, texto, tokenize = 'unicode61');

-- Banco de linguagem (editável pela interface).
CREATE TABLE IF NOT EXISTS abreviacoes (termo TEXT PRIMARY KEY, expansao TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sinonimos   (termo TEXT PRIMARY KEY, canonico TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stopwords   (palavra TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS intencoes_exemplos (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    intencao TEXT NOT NULL,
    frase    TEXT NOT NULL,
    UNIQUE (intencao, frase)
);
CREATE TABLE IF NOT EXISTS respostas_padrao (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    intencao TEXT NOT NULL,
    texto    TEXT NOT NULL
);

-- Addons: pacotes de conhecimento instalados a partir de arquivos .aprendiz.
-- Os conhecimentos de um addon ficam na tabela "conhecimentos" com addon_id
-- preenchido. Desativar um addon só o esconde da busca; nada é apagado.
CREATE TABLE IF NOT EXISTS addons (
    id           TEXT PRIMARY KEY,
    nome         TEXT NOT NULL,
    versao       TEXT NOT NULL,
    autor        TEXT,
    descricao    TEXT,
    licenca      TEXT,
    site         TEXT,
    ativo        INTEGER NOT NULL DEFAULT 1,
    instalado_em TEXT NOT NULL,
    hash         TEXT,
    manifesto    TEXT              -- manifesto completo em JSON (origem, classificação…)
);

-- Configurações (parâmetros e personalização). addon_id vazio = definida pelo
-- dono; preenchido = trazida por um addon (vale só com ele ativo).
-- Precedência: dono > addon ativo mais recente > padrão (ver configuracoes.py).
CREATE TABLE IF NOT EXISTS configuracoes (
    chave    TEXT NOT NULL,
    valor    TEXT NOT NULL,        -- JSON
    addon_id TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (chave, addon_id)
);

-- Sinônimos e abreviações trazidos por addons. Valem só com o addon ativo,
-- e as entradas do próprio dono têm prioridade sobre elas.
CREATE TABLE IF NOT EXISTS addon_linguagem (
    addon_id TEXT NOT NULL REFERENCES addons(id) ON DELETE CASCADE,
    -- abreviacoes/sinonimos: termo → valor | stopwords: termo = palavra, valor = ''
    -- intencoes: termo = frase de exemplo, valor = nome da intenção
    tipo     TEXT NOT NULL CHECK (tipo IN ('abreviacoes', 'sinonimos', 'stopwords', 'intencoes')),
    termo    TEXT NOT NULL,
    valor    TEXT NOT NULL,
    PRIMARY KEY (addon_id, tipo, termo)
);

-- Recursos de compreensão (Aprendiz 0.7+), trazidos pelos addons
-- "compreensao" e "vetores" (formato em aprendiz/recursos.py):
--   compreensao.json → JSON já validado e normalizado
--   vetores.info     → {"dimensoes": D, "quantidade": V} em JSON
--   vetores.dados    → os vetores (int8 × V × D)
-- e normas da língua (Aprendiz 0.8+, formato em aprendiz/normas.py):
--   norma.json       → JSON já validado (grafias, equivalências, regras)
--   vocabulario      → as formas da norma, ordenadas, uma por linha
CREATE TABLE IF NOT EXISTS addon_recursos (
    addon_id TEXT NOT NULL REFERENCES addons(id) ON DELETE CASCADE,
    nome     TEXT NOT NULL,
    dados    BLOB NOT NULL,
    PRIMARY KEY (addon_id, nome)
);

-- Léxico: as palavras que os addons de compreensão e de vetores conhecem.
-- Fica no SQLite (e não na memória) porque são centenas de milhares de
-- palavras: o app consulta só as palavras de cada mensagem.
--   lema  → '' = palavra conhecida sem lema diferente; NULL = sem informação
--   vetor → número do vetor no recurso "vetores.dados" do mesmo addon;
--           negativo = -(número + 1) para palavras que só emprestam o vetor
--           de outra (apelidos, menos confiáveis)
CREATE TABLE IF NOT EXISTS addon_lexico (
    palavra  TEXT NOT NULL,
    addon_id TEXT NOT NULL REFERENCES addons(id) ON DELETE CASCADE,
    lema     TEXT,
    vetor    INTEGER,
    PRIMARY KEY (palavra, addon_id)
) WITHOUT ROWID;

-- Histórico de conversas.
CREATE TABLE IF NOT EXISTS conversas (
    id            TEXT PRIMARY KEY,
    titulo        TEXT NOT NULL,
    criada_em     TEXT NOT NULL,
    atualizada_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mensagens (
    id          TEXT PRIMARY KEY,
    conversa_id TEXT NOT NULL REFERENCES conversas(id) ON DELETE CASCADE,
    papel       TEXT NOT NULL CHECK (papel IN ('usuario', 'assistente')),
    texto       TEXT NOT NULL,
    meta        TEXT,              -- JSON com a "explicação" da resposta
    criada_em   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mensagens_conversa ON mensagens (conversa_id, criada_em);
"""


def agora() -> str:
    """Data/hora atual em UTC, no formato ISO 8601 (ordena bem como texto)."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def lista_json(doc: dict[str, Any], campo: str) -> list[str]:
    """Lê uma coluna-lista em JSON (variacoes, traducoes); vazia se não houver."""
    valor = doc.get(campo)
    if not valor:
        return []
    try:
        dados = json.loads(valor)
    except (TypeError, ValueError):
        return []
    return [str(v) for v in dados] if isinstance(dados, list) else []


def teia_de(doc: dict[str, Any]) -> dict[str, Any] | None:
    """Lê a coluna teia (JSON) de um conhecimento; None se não houver."""
    try:
        dados = json.loads(doc.get("teia") or "null")
    except (TypeError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def novo_id() -> str:
    """IDs aleatórios (UUID4): dois bancos diferentes nunca geram o mesmo id,
    então registros de bases distintas podem ser juntados sem colisão."""
    return uuid.uuid4().hex


class Banco:
    """Acesso ao SQLite. Uma instância por processo; é segura entre threads."""

    def __init__(self, caminho: str | Path):
        self.caminho = str(caminho)
        # check_same_thread=False: o servidor web usa várias threads.
        # Para não haver escrita simultânea, toda operação passa pelo _trava.
        self._con = sqlite3.connect(self.caminho, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.execute("PRAGMA journal_mode = WAL")  # leituras não bloqueiam escritas
        self._trava = threading.RLock()
        self.versao_conhecimento = 0
        self.versao_linguagem = 0

        with self._trava:
            self._con.executescript(ESQUEMA)
            self._con.commit()
            self._migrar()
        if self.obter_meta("semeado") is None:
            self.semear()

    def _migrar(self) -> None:
        """
        Atualiza bancos criados por versões anteriores do Aprendiz.

        "CREATE TABLE IF NOT EXISTS" não acrescenta colunas novas a tabelas
        que já existem; então cada mudança de estrutura ganha um passo aqui.
        Os passos são idempotentes: rodar de novo não estraga nada.
        """
        c = self._con
        colunas = {linha["name"] for linha in c.execute("PRAGMA table_info(conhecimentos)")}
        if "addon_id" not in colunas:               # versão 0.1 → 0.2 (addons)
            c.execute("ALTER TABLE conhecimentos ADD COLUMN addon_id TEXT")
        c.execute("CREATE INDEX IF NOT EXISTS idx_conhecimentos_addon ON conhecimentos (addon_id)")

        versao = c.execute("SELECT valor FROM meta WHERE chave = 'versao_esquema'").fetchone()
        versao = int(versao["valor"]) if versao else 0
        semeado = c.execute("SELECT 1 FROM meta WHERE chave = 'semeado'").fetchone()
        if semeado and versao < 3:                  # 0.2 → 0.3: sinônimos novos
            c.executemany("INSERT OR IGNORE INTO sinonimos VALUES (?, ?)",
                          sementes.SINONIMOS_V3.items())
        colunas_addons = {linha["name"] for linha in c.execute("PRAGMA table_info(addons)")}
        if "manifesto" not in colunas_addons:       # 0.3 → 0.4: addons formato 2
            c.execute("ALTER TABLE addons ADD COLUMN manifesto TEXT")

        # 0.4 → 0.4.1: addon_linguagem aceita stopwords e intenções, e
        # conhecimentos aceita o tipo "verbete".
        self._ampliar_check("addon_linguagem", "'stopwords'",
                            ["addon_id", "tipo", "termo", "valor"])
        self._ampliar_check("conhecimentos", "'verbete'",
                            ["id", "tipo", "pergunta", "conteudo", "origem", "texto_busca",
                             "addon_id", "criado_em", "atualizado_em"])
        c.execute("CREATE INDEX IF NOT EXISTS idx_conhecimentos_addon ON conhecimentos (addon_id)")

        # 0.5 → 0.6: variações de pergunta e traduções (verbetes).
        colunas = {l["name"] for l in c.execute("PRAGMA table_info(conhecimentos)")}
        for coluna in ("variacoes", "traducoes"):
            if coluna not in colunas:
                c.execute(f"ALTER TABLE conhecimentos ADD COLUMN {coluna} TEXT")
        # 0.6 → 0.7: addon_recursos e addon_lexico são tabelas novas (o
        # ESQUEMA as cria); nada a converter.
        # 0.7 → 0.8: variedade dos verbetes. As normas ficam em addon_recursos.
        if "variedade" not in colunas:
            c.execute("ALTER TABLE conhecimentos ADD COLUMN variedade TEXT")
        # 1.0 → 2.0: a teia de porquês dos conhecimentos de addons.
        if "teia" not in colunas:
            c.execute("ALTER TABLE conhecimentos ADD COLUMN teia TEXT")
        c.execute("INSERT OR REPLACE INTO meta VALUES ('versao_esquema', '9')")
        c.commit()

    def _ampliar_check(self, tabela: str, marca: str, colunas: list[str]) -> None:
        """
        O SQLite não altera o CHECK de uma tabela existente. Para aceitar um
        valor novo, a tabela é renomeada, recriada pelo ESQUEMA atual e os
        dados são copiados (pelos nomes das colunas, não pela posição).
        `marca` é um trecho que só existe no CHECK novo.
        """
        c = self._con
        sql = c.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (tabela,)).fetchone()
        if not sql or marca in sql["sql"]:
            return
        lista = ", ".join(colunas)
        c.execute(f"ALTER TABLE {tabela} RENAME TO {tabela}_antiga")
        c.executescript(ESQUEMA)  # cria a tabela de novo, já com o CHECK novo
        c.execute(f"INSERT INTO {tabela} ({lista}) SELECT {lista} FROM {tabela}_antiga")
        c.execute(f"DROP TABLE {tabela}_antiga")

    # ------------------------------------------------------------------ utilidades
    def _executar(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        with self._trava:
            cur = self._con.execute(sql, params)
            self._con.commit()
            return cur

    def _consultar(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        with self._trava:
            return [dict(l) for l in self._con.execute(sql, params).fetchall()]

    def fechar(self) -> None:
        with self._trava:
            self._con.close()

    def obter_meta(self, chave: str) -> str | None:
        linhas = self._consultar("SELECT valor FROM meta WHERE chave = ?", (chave,))
        return linhas[0]["valor"] if linhas else None

    def definir_meta(self, chave: str, valor: str) -> None:
        self._executar(
            "INSERT INTO meta (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
            (chave, valor),
        )

    # ------------------------------------------------------------------ sementes
    def semear(self) -> None:
        """Grava o banco de linguagem inicial (só na primeira execução)."""
        with self._trava:
            c = self._con
            c.executemany("INSERT OR IGNORE INTO abreviacoes VALUES (?, ?)",
                          sementes.ABREVIACOES.items())
            c.executemany("INSERT OR IGNORE INTO sinonimos VALUES (?, ?)",
                          sementes.SINONIMOS.items())
            c.executemany("INSERT OR IGNORE INTO stopwords VALUES (?)",
                          [(p,) for p in set(sementes.STOPWORDS)])
            c.executemany(
                "INSERT OR IGNORE INTO intencoes_exemplos (intencao, frase) VALUES (?, ?)",
                [(i, f) for i, frases in sementes.INTENCOES.items() for f in frases],
            )
            c.executemany(
                "INSERT INTO respostas_padrao (intencao, texto) VALUES (?, ?)",
                [(i, t) for i, textos in sementes.RESPOSTAS_PADRAO.items() for t in textos],
            )
            c.execute("INSERT OR REPLACE INTO meta VALUES ('semeado', ?)", (agora(),))
            c.commit()
        self.versao_linguagem += 1

    # ------------------------------------------------------------------ backup e reset
    def fazer_backup(self, destino: str | Path) -> Path:
        """
        Copia o banco inteiro para outro arquivo, com segurança, mesmo com o
        app em uso. A API de backup do SQLite copia página por página de
        forma consistente (diferente de copiar o arquivo "na mão").
        """
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        with self._trava:
            copia = sqlite3.connect(destino)
            try:
                self._con.backup(copia)
            finally:
                copia.close()
        return destino

    def resetar(self, conhecimentos: bool = True, linguagem: bool = True,
                conversas: bool = True, addons: bool = True,
                configuracoes: bool = True) -> dict[str, int]:
        """
        Volta o assistente ao estado inicial ("modelo de fábrica").

            conhecimentos → apaga tudo o que foi ensinado
            linguagem     → restaura abreviações, sinônimos, stopwords,
                            intenções e respostas prontas às sementes
            conversas     → apaga o histórico de conversas
            addons        → desinstala todos os addons
            configuracoes → volta parâmetros e personalização do dono ao padrão

        Devolve quantos registros foram apagados de cada parte.
        Quem chama (a API) faz um backup antes. Aqui só apagamos.
        """
        apagados = {"conhecimentos": 0, "conversas": 0, "linguagem": 0, "addons": 0,
                    "configuracoes": 0}
        with self._trava:
            c = self._con
            if conhecimentos:  # só o que o dono ensinou; addons têm opção própria
                c.execute("DELETE FROM conhecimentos_fts WHERE id IN "
                          "(SELECT id FROM conhecimentos WHERE addon_id IS NULL)")
                apagados["conhecimentos"] = c.execute(
                    "DELETE FROM conhecimentos WHERE addon_id IS NULL").rowcount
            if addons:
                c.execute("DELETE FROM conhecimentos_fts WHERE id IN "
                          "(SELECT id FROM conhecimentos WHERE addon_id IS NOT NULL)")
                c.execute("DELETE FROM conhecimentos WHERE addon_id IS NOT NULL")
                c.execute("DELETE FROM addon_linguagem")
                c.execute("DELETE FROM addon_lexico")
                c.execute("DELETE FROM addon_recursos")
                c.execute("DELETE FROM configuracoes WHERE addon_id != ''")
                apagados["addons"] = c.execute("DELETE FROM addons").rowcount
            if configuracoes:
                apagados["configuracoes"] = c.execute(
                    "DELETE FROM configuracoes WHERE addon_id = ''").rowcount
            if conversas:
                c.execute("DELETE FROM mensagens")
                apagados["conversas"] = c.execute("DELETE FROM conversas").rowcount
            if linguagem:
                for tabela in ("abreviacoes", "sinonimos", "stopwords",
                               "intencoes_exemplos", "respostas_padrao"):
                    apagados["linguagem"] += c.execute(f"DELETE FROM {tabela}").rowcount
            c.commit()
            if conhecimentos or conversas or addons:
                c.execute("VACUUM")  # devolve ao disco o espaço liberado
        if conhecimentos or addons:
            self.versao_conhecimento += 1
        if addons:
            self.versao_linguagem += 1
        if linguagem:
            self.semear()  # regrava o banco de linguagem inicial
        return apagados

    # ------------------------------------------------------------------ conhecimento
    def salvar_conhecimento(
        self,
        conteudo: str,
        tipo: str = "nota",
        pergunta: str | None = None,
        origem: str = "manual",
        texto_busca: str = "",
        id: str | None = None,
        addon_id: str | None = None,
    ) -> dict[str, Any]:
        """Cria (ou substitui, se o id já existir) um conhecimento."""
        id = id or novo_id()
        momento = agora()
        with self._trava:
            existente = self._con.execute(
                "SELECT criado_em FROM conhecimentos WHERE id = ?", (id,)
            ).fetchone()
            criado = existente["criado_em"] if existente else momento
            self._con.execute(
                "INSERT OR REPLACE INTO conhecimentos "
                "(id, tipo, pergunta, conteudo, origem, texto_busca, criado_em, atualizado_em, addon_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (id, tipo, pergunta, conteudo, origem, texto_busca, criado, momento, addon_id),
            )
            # O índice FTS é mantido "na mão": apaga a linha antiga e insere a nova.
            self._con.execute("DELETE FROM conhecimentos_fts WHERE id = ?", (id,))
            self._con.execute("INSERT INTO conhecimentos_fts (id, texto) VALUES (?, ?)",
                              (id, texto_busca))
            self._con.commit()
        self.versao_conhecimento += 1
        return self.obter_conhecimento(id)  # type: ignore[return-value]

    def atualizar_texto_busca(self, id: str, texto_busca: str) -> None:
        """Usado na reindexação (quando sinônimos/abreviações mudam)."""
        with self._trava:
            self._con.execute("UPDATE conhecimentos SET texto_busca = ? WHERE id = ?",
                              (texto_busca, id))
            self._con.execute("DELETE FROM conhecimentos_fts WHERE id = ?", (id,))
            self._con.execute("INSERT INTO conhecimentos_fts (id, texto) VALUES (?, ?)",
                              (id, texto_busca))
            self._con.commit()
        self.versao_conhecimento += 1

    def atualizar_textos_busca(self, pares: list[tuple[str, str]]) -> None:
        """Versão em lote de atualizar_texto_busca: uma transação só (rápido)."""
        with self._trava:
            c = self._con
            c.executemany("UPDATE conhecimentos SET texto_busca = ? WHERE id = ?",
                          [(texto, id) for id, texto in pares])
            c.execute("DELETE FROM conhecimentos_fts")
            c.execute("INSERT INTO conhecimentos_fts (id, texto) "
                      "SELECT id, texto_busca FROM conhecimentos")
            c.commit()
        self.versao_conhecimento += 1

    def obter_conhecimento(self, id: str) -> dict[str, Any] | None:
        linhas = self._consultar("SELECT * FROM conhecimentos WHERE id = ?", (id,))
        return linhas[0] if linhas else None

    def remover_conhecimento(self, id: str) -> bool:
        with self._trava:
            cur = self._con.execute("DELETE FROM conhecimentos WHERE id = ?", (id,))
            self._con.execute("DELETE FROM conhecimentos_fts WHERE id = ?", (id,))
            self._con.commit()
        self.versao_conhecimento += 1
        return cur.rowcount > 0

    def listar_conhecimentos(self, filtro: str = "", limite: int = 200,
                             deslocamento: int = 0,
                             addon_id: str | None = None) -> list[dict[str, Any]]:
        """
        Listagem para a tela "Base de conhecimento" (filtro simples com LIKE).
        Sem addon_id, lista só o que o DONO ensinou; com addon_id, os
        conhecimentos daquele addon.
        """
        dono = "addon_id IS NULL" if addon_id is None else "addon_id = :addon"
        texto = "AND (pergunta LIKE :f OR conteudo LIKE :f)" if filtro else ""
        return self._consultar(
            f"SELECT * FROM conhecimentos WHERE {dono} {texto} "
            "ORDER BY atualizado_em DESC LIMIT :limite OFFSET :desloc",
            {"addon": addon_id, "f": f"%{filtro}%", "limite": limite, "desloc": deslocamento},
        )

    def todos_conhecimentos(self) -> list[dict[str, Any]]:
        """Todos os registros, inclusive de addons desativados (usado na reindexação)."""
        return self._consultar("SELECT * FROM conhecimentos")

    def conhecimentos_ativos(self) -> list[dict[str, Any]]:
        """O que a busca pode usar: o que o dono ensinou + addons ATIVOS."""
        return self._consultar(
            "SELECT c.* FROM conhecimentos c LEFT JOIN addons a ON a.id = c.addon_id "
            "WHERE c.addon_id IS NULL OR a.ativo = 1"
        )

    def contar_conhecimentos(self, de_addons: bool = False) -> int:
        condicao = "addon_id IS NOT NULL" if de_addons else "addon_id IS NULL"
        return self._consultar(f"SELECT COUNT(*) AS n FROM conhecimentos WHERE {condicao}")[0]["n"]

    def buscar_fts(self, consulta: str, limite: int = 10) -> list[dict[str, Any]]:
        """
        Busca no índice FTS5 ordenando por BM25.

        A função bm25() do SQLite devolve números NEGATIVOS: quanto menor,
        mais relevante. Por isso ordenamos de forma crescente.
        """
        # O JOIN filtra, dentro do próprio SQLite, conhecimentos de addons
        # desativados — assim eles nunca "empurram" resultados válidos para fora.
        return self._consultar(
            "SELECT f.id, bm25(conhecimentos_fts) AS score FROM conhecimentos_fts f "
            "JOIN conhecimentos c ON c.id = f.id "
            "LEFT JOIN addons a ON a.id = c.addon_id "
            "WHERE conhecimentos_fts MATCH ? AND (c.addon_id IS NULL OR a.ativo = 1) "
            "ORDER BY score LIMIT ?",
            (consulta, limite),
        )

    # ------------------------------------------------------------------ linguagem
    def _linguagem_de_addons(self, tipo: str) -> dict[str, str]:
        return {l["termo"]: l["valor"] for l in self._consultar(
            "SELECT l.termo, l.valor FROM addon_linguagem l JOIN addons a ON a.id = l.addon_id "
            "WHERE a.ativo = 1 AND l.tipo = ? ORDER BY a.instalado_em", (tipo,))}

    def _entradas_de_addons(self, tipo: str) -> list[tuple[str, str, str]]:
        """(termo, valor, nome do addon) de cada addon ATIVO, na ordem de instalação."""
        return [(l["termo"], l["valor"], l["nome"]) for l in self._consultar(
            "SELECT l.termo, l.valor, a.nome FROM addon_linguagem l JOIN addons a "
            "ON a.id = l.addon_id WHERE a.ativo = 1 AND l.tipo = ? ORDER BY a.instalado_em",
            (tipo,))]

    def _resolvido(self, tipo: str) -> tuple[dict[str, str], list[dict]]:
        """Mapa final + conflitos (ver linguagem/resolucao.py). Fica em cache por versão."""
        from aprendiz.linguagem.resolucao import resolver
        cache = getattr(self, "_cache_resolucao", {})
        if cache.get("versao") != self.versao_linguagem:
            cache = {"versao": self.versao_linguagem}
            self._cache_resolucao = cache
        if tipo not in cache:
            coluna = "canonico" if tipo == "sinonimos" else "expansao"
            dono = {l["termo"]: l[coluna] for l in self._consultar(
                f"SELECT * FROM {tipo} ORDER BY termo")}
            cache[tipo] = resolver(self._entradas_de_addons(tipo), dono,
                                   encadear=(tipo == "sinonimos"))
        return cache[tipo]

    def mapa_abreviacoes(self, incluir_addons: bool = True) -> dict[str, str]:
        """Abreviações em uso. As do dono vencem; conflitos entre addons ficam de fora."""
        if not incluir_addons:
            return {l["termo"]: l["expansao"]
                    for l in self._consultar("SELECT * FROM abreviacoes ORDER BY termo")}
        return dict(self._resolvido("abreviacoes")[0])

    def mapa_sinonimos(self, incluir_addons: bool = True) -> dict[str, str]:
        """Sinônimos em uso, já encadeados (a → b → c vira a → c). O dono vence."""
        if not incluir_addons:
            return {l["termo"]: l["canonico"]
                    for l in self._consultar("SELECT * FROM sinonimos ORDER BY termo")}
        return dict(self._resolvido("sinonimos")[0])

    def conflitos_linguagem(self) -> dict[str, list[dict]]:
        """Termos com valores diferentes em addons diferentes (o dono escolhe)."""
        return {t: self._resolvido(t)[1] for t in ("abreviacoes", "sinonimos")}

    def linguagem_de_addons(self, tipo: str) -> list[dict[str, str]]:
        """Entradas dos addons ativos com a origem (só leitura, para a tela Linguagem)."""
        return [{"termo": t, "valor": v, "addon": a} for t, v, a in self._entradas_de_addons(tipo)]

    def lista_stopwords(self, incluir_addons: bool = True) -> set[str]:
        """Stopwords em uso: as do dono + as de addons ATIVOS."""
        palavras = {l["palavra"] for l in self._consultar("SELECT palavra FROM stopwords")}
        if incluir_addons:
            palavras |= set(self._linguagem_de_addons("stopwords"))
        return palavras

    def salvar_abreviacao(self, termo: str, expansao: str) -> None:
        self._executar("INSERT OR REPLACE INTO abreviacoes VALUES (?, ?)", (termo, expansao))
        self.versao_linguagem += 1

    def remover_abreviacao(self, termo: str) -> None:
        self._executar("DELETE FROM abreviacoes WHERE termo = ?", (termo,))
        self.versao_linguagem += 1

    def salvar_sinonimo(self, termo: str, canonico: str) -> None:
        self._executar("INSERT OR REPLACE INTO sinonimos VALUES (?, ?)", (termo, canonico))
        self.versao_linguagem += 1

    def remover_sinonimo(self, termo: str) -> None:
        self._executar("DELETE FROM sinonimos WHERE termo = ?", (termo,))
        self.versao_linguagem += 1

    def exemplos_intencoes(self, incluir_addons: bool = False) -> list[dict[str, Any]]:
        """
        Frases de treino do classificador. Por padrão só as do dono (é o que a
        tela de Linguagem edita); com incluir_addons=True, também as de addons
        ATIVOS (sem "id", porque não podem ser apagadas uma a uma).
        """
        exemplos = self._consultar("SELECT * FROM intencoes_exemplos ORDER BY intencao, frase")
        if incluir_addons:
            exemplos += [{"id": None, "intencao": intencao, "frase": frase}
                         for frase, intencao in self._linguagem_de_addons("intencoes").items()]
        return exemplos

    def salvar_exemplo_intencao(self, intencao: str, frase: str) -> None:
        self._executar(
            "INSERT OR IGNORE INTO intencoes_exemplos (intencao, frase) VALUES (?, ?)",
            (intencao, frase),
        )
        self.versao_linguagem += 1

    def remover_exemplo_intencao(self, id: int) -> None:
        self._executar("DELETE FROM intencoes_exemplos WHERE id = ?", (id,))
        self.versao_linguagem += 1

    def resposta_padrao(self, intencao: str) -> str | None:
        linhas = self._consultar("SELECT texto FROM respostas_padrao WHERE intencao = ?",
                                 (intencao,))
        return random.choice(linhas)["texto"] if linhas else None

    # ------------------------------------------------------------------ addons
    def listar_addons(self) -> list[dict[str, Any]]:
        addons = self._consultar(
            "SELECT a.*, "
            "(SELECT COUNT(*) FROM conhecimentos c WHERE c.addon_id = a.id) AS total_conhecimentos, "
            "(SELECT COUNT(*) FROM addon_linguagem l WHERE l.addon_id = a.id) AS total_linguagem, "
            "(SELECT COUNT(*) FROM configuracoes g WHERE g.addon_id = a.id) AS total_configuracoes, "
            "(SELECT COUNT(*) FROM addon_recursos r WHERE r.addon_id = a.id "
            "  AND r.nome NOT IN ('norma.json', 'vocabulario')) AS total_recursos, "
            "(SELECT COUNT(*) FROM addon_recursos r WHERE r.addon_id = a.id "
            "  AND r.nome = 'norma.json') AS total_norma "
            "FROM addons a ORDER BY a.nome COLLATE NOCASE"
        )
        for a in addons:
            a["manifesto"] = json.loads(a["manifesto"]) if a["manifesto"] else {}
        return addons

    def obter_addon(self, id: str) -> dict[str, Any] | None:
        linhas = [a for a in self.listar_addons() if a["id"] == id]
        return linhas[0] if linhas else None

    def instalar_addon(self, manifesto: dict[str, Any], conhecimentos: list[dict[str, Any]],
                       linguagem: dict[str, dict[str, str]], hash_arquivo: str,
                       configuracoes: dict[str, Any] | None = None,
                       recursos: dict[str, Any] | None = None) -> None:
        """
        Grava um addon inteiro numa única transação: ou entra tudo, ou nada.
        Se o addon já existia (mesmo id), a versão antiga é substituída,
        mas a escolha de ativo/desativado do dono é mantida.

        `conhecimentos` já chega com o texto de busca calculado (o Assistente
        cuida disso), no formato: {pergunta, conteudo, tipo, texto_busca}.
        `configuracoes` junta parâmetros e personalização, já validados.
        `recursos` (0.7+): {"compreensao": dict, "lemas": [(palavra, lema)],
        "vetores": recursos.Vetores, "norma": dict, "vocabulario": bytes},
        todos opcionais e já validados.
        """
        recursos = recursos or {}
        momento = agora()
        with self._trava:
            c = self._con
            try:
                anterior = c.execute("SELECT ativo FROM addons WHERE id = ?",
                                     (manifesto["id"],)).fetchone()
                ativo = anterior["ativo"] if anterior else 1
                self._apagar_addon(manifesto["id"])
                c.execute(
                    "INSERT INTO addons (id, nome, versao, autor, descricao, licenca, site, "
                    "ativo, instalado_em, hash, manifesto) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (manifesto["id"], manifesto["nome"], manifesto["versao"],
                     manifesto.get("autor"), manifesto.get("descricao"),
                     manifesto.get("licenca"), manifesto.get("site"),
                     ativo, momento, hash_arquivo, json.dumps(manifesto, ensure_ascii=False)),
                )
                origem = f"addon:{manifesto['id']}"
                def lista(valor):
                    return json.dumps(valor, ensure_ascii=False) if valor else None
                linhas = [(novo_id(), k["tipo"], k.get("pergunta"), k["conteudo"], origem,
                           k["texto_busca"], momento, momento, manifesto["id"],
                           lista(k.get("variacoes")), lista(k.get("traducoes")),
                           k.get("variedade"),
                           json.dumps(k["teia"], ensure_ascii=False) if k.get("teia") else None)
                          for k in conhecimentos]
                c.executemany(
                    "INSERT INTO conhecimentos (id, tipo, pergunta, conteudo, origem, "
                    "texto_busca, criado_em, atualizado_em, addon_id, variacoes, traducoes, "
                    "variedade, teia) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", linhas)
                c.executemany("INSERT INTO conhecimentos_fts (id, texto) VALUES (?, ?)",
                              [(l[0], l[5]) for l in linhas])
                c.executemany(
                    "INSERT OR REPLACE INTO addon_linguagem VALUES (?, ?, ?, ?)",
                    [(manifesto["id"], tipo, termo, valor)
                     for tipo, mapa in linguagem.items() for termo, valor in mapa.items()])
                c.executemany(
                    "INSERT OR REPLACE INTO configuracoes (chave, valor, addon_id) VALUES (?, ?, ?)",
                    [(chave, json.dumps(valor), manifesto["id"])
                     for chave, valor in (configuracoes or {}).items()])
                self._gravar_recursos(manifesto["id"], recursos)
                c.commit()
            except Exception:
                c.rollback()
                raise
        self.versao_conhecimento += 1
        self.versao_linguagem += 1

    def _gravar_recursos(self, addon_id: str, recursos: dict[str, Any]) -> None:
        """Compreensão, lemas e vetores de um addon (sem commit)."""
        c = self._con
        if recursos.get("compreensao"):
            c.execute("INSERT INTO addon_recursos VALUES (?, ?, ?)",
                      (addon_id, "compreensao.json",
                       json.dumps(recursos["compreensao"], ensure_ascii=False).encode("utf-8")))
        lexico: dict[str, list] = {}
        for palavra, lema in recursos.get("lemas") or []:
            lexico[palavra] = [lema, None]
        vetores = recursos.get("vetores")
        if vetores:
            c.execute("INSERT INTO addon_recursos VALUES (?, ?, ?)",
                      (addon_id, "vetores.info", json.dumps(
                          {"dimensoes": vetores.dimensoes, "quantidade": vetores.quantidade}
                      ).encode("utf-8")))
            c.execute("INSERT INTO addon_recursos VALUES (?, ?, ?)",
                      (addon_id, "vetores.dados", vetores.dados))
            for posicao, (palavra, indice) in enumerate(vetores.palavras):
                # Palavra "original" = a dona do vetor (a i-ésima usa o vetor i).
                # As outras são APELIDOS (formas raras que emprestam o vetor de
                # uma palavra parecida): gravadas como -(nº + 1), valem menos.
                original = posicao < vetores.quantidade and indice == posicao
                lexico.setdefault(palavra, [None, None])[1] = indice if original else -(indice + 1)
        c.executemany("INSERT INTO addon_lexico VALUES (?, ?, ?, ?)",
                      ((p, addon_id, l, v) for p, (l, v) in lexico.items()))
        if recursos.get("norma"):
            c.execute("INSERT INTO addon_recursos VALUES (?, ?, ?)",
                      (addon_id, "norma.json",
                       json.dumps(recursos["norma"], ensure_ascii=False).encode("utf-8")))
        if recursos.get("vocabulario"):
            c.execute("INSERT INTO addon_recursos VALUES (?, ?, ?)",
                      (addon_id, "vocabulario", recursos["vocabulario"]))

    def _apagar_addon(self, id: str) -> None:
        """Apaga sem commit (usado dentro de transações)."""
        c = self._con
        c.execute("DELETE FROM addon_lexico WHERE addon_id = ?", (id,))
        c.execute("DELETE FROM addon_recursos WHERE addon_id = ?", (id,))
        c.execute("DELETE FROM conhecimentos_fts WHERE id IN "
                  "(SELECT id FROM conhecimentos WHERE addon_id = ?)", (id,))
        c.execute("DELETE FROM conhecimentos WHERE addon_id = ?", (id,))
        c.execute("DELETE FROM addon_linguagem WHERE addon_id = ?", (id,))
        c.execute("DELETE FROM configuracoes WHERE addon_id = ?", (id,))
        c.execute("DELETE FROM addons WHERE id = ?", (id,))

    def remover_addon(self, id: str) -> bool:
        with self._trava:
            existia = self._con.execute("SELECT 1 FROM addons WHERE id = ?", (id,)).fetchone()
            self._apagar_addon(id)
            self._con.commit()
        self.versao_conhecimento += 1
        self.versao_linguagem += 1
        return existia is not None

    def definir_addon_ativo(self, id: str, ativo: bool) -> bool:
        cur = self._executar("UPDATE addons SET ativo = ? WHERE id = ?", (int(ativo), id))
        # Muda o que a busca enxerga (e talvez sinônimos): invalida os caches.
        self.versao_conhecimento += 1
        self.versao_linguagem += 1
        return cur.rowcount > 0

    # ------------------------------------------------------------------ compreensão
    def recursos_ativos(self, nome: str) -> list[tuple[str, bytes]]:
        """[(addon_id, dados)] do recurso `nome` nos addons ATIVOS, do mais antigo
        ao mais novo (o mais novo vence quando dois dizem coisas diferentes)."""
        return [(l["addon_id"], l["dados"]) for l in self._consultar(
            "SELECT r.addon_id, r.dados FROM addon_recursos r JOIN addons a ON a.id = r.addon_id "
            "WHERE a.ativo = 1 AND r.nome = ? ORDER BY a.instalado_em", (nome,))]

    def tem_lexico(self) -> tuple[bool, bool]:
        """(há lemas ativos?, há vetores ativos?) — evita consultas à toa."""
        l = self._consultar(
            "SELECT EXISTS(SELECT 1 FROM addon_recursos r JOIN addons a ON a.id = r.addon_id "
            "  WHERE a.ativo = 1 AND r.nome = 'compreensao.json' AND EXISTS("
            "    SELECT 1 FROM addon_lexico x WHERE x.addon_id = a.id AND x.lema IS NOT NULL)) AS l, "
            "EXISTS(SELECT 1 FROM addon_recursos r JOIN addons a ON a.id = r.addon_id "
            "  WHERE a.ativo = 1 AND r.nome = 'vetores.dados') AS v")[0]
        return bool(l["l"]), bool(l["v"])

    def consultar_lexico(self, palavra: str) -> tuple[str | None, tuple[str, int] | None]:
        """
        (lema, (addon_id, nº do vetor)) de uma palavra, só de addons ativos.
        lema: None = desconhecida; "" = conhecida, sem lema diferente.
        """
        linhas = self._consultar(
            "SELECT x.addon_id, x.lema, x.vetor FROM addon_lexico x JOIN addons a "
            "ON a.id = x.addon_id WHERE x.palavra = ? AND a.ativo = 1 "
            "ORDER BY a.instalado_em DESC", (palavra,))
        lema = next((l["lema"] for l in linhas if l["lema"] is not None), None)
        vetor = next(((l["addon_id"], l["vetor"]) for l in linhas if l["vetor"] is not None), None)
        return lema, vetor

    def recurso(self, addon_id: str, nome: str) -> bytes | None:
        linhas = self._consultar("SELECT dados FROM addon_recursos WHERE addon_id = ? AND nome = ?",
                                 (addon_id, nome))
        return linhas[0]["dados"] if linhas else None

    def configuracoes_do_addon(self, id: str) -> dict[str, Any]:
        """Parâmetros e personalização que um addon trouxe (ativo ou não)."""
        return {l["chave"]: json.loads(l["valor"]) for l in self._consultar(
            "SELECT chave, valor FROM configuracoes WHERE addon_id = ?", (id,))}

    # ------------------------------------------------------------------ configurações
    def linhas_configuracoes(self) -> list[dict[str, Any]]:
        """
        Todas as configurações que valem agora, já na ordem de precedência:
        primeiro as do dono, depois as de addons ATIVOS (o mais recente antes).
        Configuracoes.efetivas() pega a primeira de cada chave.
        """
        return self._consultar(
            "SELECT g.chave, g.valor, g.addon_id, a.nome AS addon_nome FROM configuracoes g "
            "LEFT JOIN addons a ON a.id = g.addon_id "
            "WHERE g.addon_id = '' OR a.ativo = 1 "
            "ORDER BY (g.addon_id != ''), a.instalado_em DESC"
        )

    def definir_configuracao(self, chave: str, valor_json: str) -> None:
        self._executar("INSERT OR REPLACE INTO configuracoes (chave, valor, addon_id) "
                       "VALUES (?, ?, '')", (chave, valor_json))

    def remover_configuracao(self, chave: str) -> None:
        self._executar("DELETE FROM configuracoes WHERE chave = ? AND addon_id = ''", (chave,))

    # ------------------------------------------------------------------ conversas
    def criar_conversa(self, titulo: str = "Nova conversa") -> dict[str, Any]:
        id, momento = novo_id(), agora()
        self._executar("INSERT INTO conversas VALUES (?, ?, ?, ?)", (id, titulo, momento, momento))
        return {"id": id, "titulo": titulo, "criada_em": momento, "atualizada_em": momento}

    def obter_conversa(self, id: str) -> dict[str, Any] | None:
        linhas = self._consultar("SELECT * FROM conversas WHERE id = ?", (id,))
        return linhas[0] if linhas else None

    def listar_conversas(self) -> list[dict[str, Any]]:
        return self._consultar("SELECT * FROM conversas ORDER BY atualizada_em DESC")

    def renomear_conversa(self, id: str, titulo: str) -> None:
        self._executar("UPDATE conversas SET titulo = ? WHERE id = ?", (titulo, id))

    def remover_conversa(self, id: str) -> None:
        self._executar("DELETE FROM conversas WHERE id = ?", (id,))

    def adicionar_mensagem(self, conversa_id: str, papel: str, texto: str,
                           meta: dict | None = None) -> dict[str, Any]:
        id, momento = novo_id(), agora()
        with self._trava:
            self._con.execute(
                "INSERT INTO mensagens VALUES (?, ?, ?, ?, ?, ?)",
                (id, conversa_id, papel, texto,
                 json.dumps(meta, ensure_ascii=False) if meta else None, momento),
            )
            self._con.execute("UPDATE conversas SET atualizada_em = ? WHERE id = ?",
                              (momento, conversa_id))
            self._con.commit()
        return {"id": id, "conversa_id": conversa_id, "papel": papel, "texto": texto,
                "meta": meta, "criada_em": momento}

    def obter_mensagem(self, id: str) -> dict[str, Any] | None:
        linhas = self._consultar("SELECT * FROM mensagens WHERE id = ?", (id,))
        if not linhas:
            return None
        msg = linhas[0]
        msg["meta"] = json.loads(msg["meta"]) if msg["meta"] else None
        return msg

    def atualizar_meta_mensagem(self, id: str, meta: dict) -> None:
        self._executar("UPDATE mensagens SET meta = ? WHERE id = ?",
                       (json.dumps(meta, ensure_ascii=False), id))

    def listar_mensagens(self, conversa_id: str) -> list[dict[str, Any]]:
        linhas = self._consultar(
            "SELECT * FROM mensagens WHERE conversa_id = ? ORDER BY criada_em", (conversa_id,)
        )
        for l in linhas:
            l["meta"] = json.loads(l["meta"]) if l["meta"] else None
        return linhas
