"""
Homologação: perguntas de gente de verdade contra os addons REAIS da loja.

Os testes do tests/ usam addons pequenos, feitos para cada caso. Aqui é o
contrário: instala os addons publicados e faz perguntas do jeito que uma
pessoa faz (com erro de digitação, gíria, abreviação, fora do assunto, em
sequência) e confere se a resposta veio do lugar certo.

    python ferramentas/homologar.py ../aprendiz-addons
    python ferramentas/homologar.py ../aprendiz-addons --busca hibrido -v

Cada caso diz o que se espera:
    "q:<trecho>"     a 1ª fonte é o conhecimento cuja pergunta contém <trecho>
    "tipo:<tipo>"    o tipo da resposta (desconhecido, social, dialogo…)
    "panorama"       uma lista "Sobre X, encontrei isto:"
    "!q:<trecho>"    a resposta NÃO pode vir de <trecho>
    "fundo"          "não entendi" explicou mais fundo (porquês ou a base)
Um caso com "seguir" é feito na mesma conversa da pergunta anterior.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from aprendiz.core import Assistente  # noqa: E402
from aprendiz.memoria import Banco  # noqa: E402

ADDONS = ["compreensao-portugues", "dialogo-portugues", "vetores-portugues",
          "prog-logica", "prog-banco-dados", "sql-basico"]

CASOS: list[tuple[str, str, str]] = [
    # (grupo, pergunta, esperado)
    ("direto", "o que é null?", "q:null"),
    ("direto", "como usar group by", "q:group by"),
    ("direto", "o que é left join", "q:left join"),
    ("variação", "oq é null", "q:null"),
    ("variação", "null é o quê?", "q:null"),
    ("variação", "me explica o null", "q:null"),
    ("variação", "pra que serve o group by", "q:group by"),
    ("variação", "pra q serve o having", "q:having"),
    ("variação", "como eu faço pra juntar duas tabelas?", "q:join"),
    ("variação", "como apagar registros de uma tabela", "q:apagar"),
    ("variação", "como mudar um valor que já está na tabela", "q:atualizar"),
    ("variação", "como pegar só os 10 primeiros", "q:limitar"),
    ("variação", "como ordenar do maior pro menor", "q:ordenar"),
    ("variação", "como contar quantas linhas tem", "q:agregação"),
    ("digitação", "diferensa entre wehre e havng", "q:having"),
    ("digitação", "o que e nul", "q:null"),
    ("digitação", "como fazer um lefet join", "q:left join"),
    ("digitação", "grup by serve pra que", "q:group by"),
    ("porquê", "por que usar join?", "q:join"),
    ("porquê", "por que o where não funciona com count?", "q:having"),
    ("porquê", "por que = null não funciona", "q:null"),
    ("conceito", "o que é chave estrangeira?", "q:chave estrangeira"),
    ("conceito", "o que é um índice?", "q:índice"),
    ("conceito", "o que é uma transação", "q:transação"),
    ("resumo", "me fala de banco de dados", "panorama"),
    ("resumo", "tudo sobre join", "panorama"),
    ("resumo", "me dá um resumo de sql", "panorama"),
    ("fora", "o que é um ponteiro em C?", "tipo:desconhecido"),
    ("fora", "como fazer bolo de cenoura", "tipo:desconhecido"),
    ("fora", "quem ganhou a copa de 2002", "tipo:desconhecido"),
    ("fora", "o que é c?", "tipo:desconhecido"),
    ("fora", "qual a capital da frança", "tipo:desconhecido"),
    ("fora", "como declarar uma variável em python", "!q:sql"),
    # Inéditas: jeitos de perguntar que NÃO estão em nenhum addon. Medem se o
    # Aprendiz generaliza, e não se decorou as frases da homologação.
    ("inédita", "quero ver só as 5 primeiras linhas", "q:limitar"),
    ("inédita", "trocar o preço de um produto no banco", "q:atualizar"),
    ("inédita", "jogar fora os pedidos cancelados", "q:apagar"),
    ("inédita", "listar do mais caro pro mais barato", "q:ordenar"),
    ("inédita", "unir a tabela de clientes com a de pedidos", "q:join"),
    ("inédita", "quantos pedidos cada cliente fez", "q:group by"),
    ("inédita", "filtrar só os clientes de são paulo", "q:filtrar"),
    ("inédita", "campo vazio no banco de dados", "q:null"),
    ("inédita", "criar uma tabela nova", "q:criar uma tabela"),
    ("inédita", "colocar um cliente novo na tabela", "q:inserir"),
    # Inéditas 2: escritas ANTES de mexer no vocabulário dos addons, e não
    # consultadas enquanto ele era escrito. É a medida honesta de generalização.
    ("inédita 2", "como deletar um produto que não vende mais", "q:apagar"),
    ("inédita 2", "preciso modificar o email de um cliente", "q:atualizar"),
    ("inédita 2", "adicionar um pedido novo", "q:inserir"),
    ("inédita 2", "mostrar os produtos em ordem de preço", "q:ordenar"),
    ("inédita 2", "registros sem valor numa coluna", "q:null"),
    ("inédita 2", "somar o total vendido por mês", "q:group by"),
    ("inédita 2", "só os 3 produtos mais caros", "q:limitar"),
    ("inédita 2", "tirar um cliente do cadastro", "q:apagar"),
    # Inéditas 3: escritas DEPOIS dos padrões de frase e antes de ajustá-los.
    ("inédita 3", "quantas vendas cada produto teve", "q:group by"),
    ("inédita 3", "os 10 clientes que mais compraram", "q:limitar"),
    ("inédita 3", "incluir uma categoria nova", "q:inserir"),
    ("inédita 3", "excluir o pedido número 5", "q:apagar"),
    ("inédita 3", "juntar a tabela de produtos com a de categorias", "q:join"),
    ("inédita 3", "listar apenas os pedidos de março", "q:filtrar"),
    ("inédita 3", "média de preço por categoria", "q:group by"),
    ("inédita 3", "telefone vazio no cadastro", "q:null"),
    ("inédita 3", "como alterar o nome de um produto", "q:atualizar"),
    ("inédita 3", "mostrar os pedidos do mais novo pro mais antigo", "q:ordenar"),
    # Leva prog-banco-dados: escritas ANTES de pôr os porquês e o vocabulário.
    ("leva bd", "pra que serve uma chave primária", "q:chave primária"),
    ("leva bd", "por que normalizar o banco", "q:normalização"),
    ("leva bd", "o que é uma fk", "q:chave estrangeira"),
    ("leva bd", "diferença entre sql e nosql", "q:nosql"),
    ("leva bd", "o que significa acid", "q:acid"),
    ("leva bd", "por que usar transação", "q:transação"),
    ("leva bd", "como evitar sql injection", "q:sql injection"),
    ("leva bd", "um aluno faz vários cursos e um curso tem vários alunos", "q:muitos para muitos"),
    ("leva bd", "o que é um sgbd", "q:sgbd"),
    ("leva bd", "pra que serve um índice", "q:índice"),
    ("leva bd", "dados repetidos em várias tabelas", "q:normalização"),
    ("leva bd", "o que faz um orm", "q:orm"),
    ("leva bd", "guardar uma cópia do banco", "q:backup"),
    ("leva bd", "salvar várias alterações de uma vez ou nenhuma", "q:transação"),
    ("leva bd", "o que quer dizer crud", "q:crud"),
    ("social", "oi, tudo bem?", "tipo:social"),
    ("social", "obrigado!", "tipo:social"),
    ("social", "valeu, ajudou muito", "tipo:social"),
    ("conversa", "o que é null?", "q:null"),
    ("conversa", "e o limit?", "q:limitar", ),
    ("conversa", "não entendi", "fundo"),
]
SEGUIR = {"e o limit?", "não entendi"}


def confere(r: dict, esperado: str) -> bool:
    msg = r["mensagem"]
    tipo = msg["meta"].get("tipo")
    fontes = msg["meta"].get("fontes") or []
    titulo = (fontes[0].get("titulo") or "").lower() if fontes else ""
    if esperado == "fundo":   # "não entendi": foi mais fundo, não repetiu
        return msg["texto"].startswith(("Vou explicar o porquê", "Vou pela base"))
    if esperado == "panorama":
        return " encontrei" in msg["texto"][:200]
    if esperado.startswith("tipo:"):
        return tipo == esperado[5:]
    if esperado.startswith("!q:"):
        return not fontes or esperado[3:] not in titulo
    return esperado[2:] in titulo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("loja", type=Path)
    ap.add_argument("--busca", default="fuzzy")
    ap.add_argument("--resposta", default="trabalhada")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    assistente = Assistente(Banco(str(Path(tempfile.mkdtemp()) / "homologacao.db")))
    for id_ in ADDONS:
        assistente.instalar_addon((args.loja / "addons" / f"{id_}.aprendiz").read_bytes())

    falhas, conversa, grupo_atual = [], None, None
    for grupo, pergunta, esperado in CASOS:
        if pergunta not in SEGUIR:
            conversa = None
        r = assistente.responder(pergunta, conversa_id=conversa, busca=args.busca,
                                 resposta=args.resposta)
        conversa = r["conversa_id"] if "conversa_id" in r else r["mensagem"].get("conversa_id")
        ok = confere(r, esperado)
        fontes = r["mensagem"]["meta"].get("fontes") or []
        obtido = (fontes[0]["titulo"] if fontes else r["mensagem"]["meta"].get("tipo"))
        if grupo != grupo_atual:
            print(f"\n[{grupo}]")
            grupo_atual = grupo
        print(f"  {'ok ' if ok else 'ERR'} {pergunta!r:50} → {obtido}")
        if not ok:
            falhas.append(pergunta)
            if args.verbose:
                print("      " + r["mensagem"]["texto"][:160].replace("\n", " "))
    print(f"\n{len(CASOS) - len(falhas)}/{len(CASOS)} ok")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
