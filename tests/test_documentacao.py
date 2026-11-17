"""Garante que o projeto continue documentado: todo arquivo tem explicação."""

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "ferramentas"))

import gerar_estrutura  # noqa: E402


def arquivos_python():
    return [p for p in RAIZ.rglob("*.py")
            if not set(p.relative_to(RAIZ).parts) & gerar_estrutura.IGNORAR]


def test_todo_arquivo_python_tem_docstring():
    sem = [str(p.relative_to(RAIZ)) for p in arquivos_python()
           if not ast.get_docstring(ast.parse(p.read_text(encoding="utf-8")))]
    assert not sem, f"Arquivos sem docstring: {sem}"


def test_todo_arquivo_aparece_explicado_na_estrutura():
    _, faltando = gerar_estrutura.gerar()
    assert not faltando, f"Sem descrição em ferramentas/gerar_estrutura.py: {faltando}"


def test_docs_estrutura_esta_atualizado():
    md, _ = gerar_estrutura.gerar()
    atual = gerar_estrutura.DESTINO.read_text(encoding="utf-8")
    assert md == atual, "Rode: python ferramentas/gerar_estrutura.py"


def test_todo_algoritmo_tem_explicacao():
    from aprendiz.algoritmos import BUSCAS, RESPOSTAS
    for a in [*BUSCAS.values(), *RESPOSTAS.values()]:
        assert len(a.explicacao.strip()) > 100, f"{a.nome} sem explicação"
