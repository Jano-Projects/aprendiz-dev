"""
Gera docs/referencia/estrutura.md: a árvore indentada de pastas e arquivos do projeto,
com uma linha de explicação para cada um.

De onde vem cada explicação:
    • arquivos .py       → o primeiro parágrafo do docstring do módulo
    • pacotes (pastas)   → o docstring do __init__.py
    • demais arquivos    → o dicionário DESCRICOES abaixo

Assim a documentação nasce do próprio código e não desatualiza: ao criar um
arquivo novo, escreva o docstring (ou acrescente uma linha em DESCRICOES) e rode:

    python ferramentas/gerar_estrutura.py

O teste tests/test_documentacao.py falha se algum arquivo ficar sem
explicação ou se o docs/referencia/estrutura.md estiver desatualizado.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "docs" / "referencia" / "estrutura.md"

IGNORAR = {".git", ".venv", "__pycache__", ".pytest_cache", "build", "dist", "node_modules"}
IGNORAR_SUFIXOS = {".pyc", ".db", ".db-wal", ".db-shm", ".spec"}

# Descrições de pastas e arquivos que não são Python (caminhos relativos à raiz).
DESCRICOES: dict[str, str] = {
    # ---- pastas
    ".github": "Configurações do GitHub",
    ".github/workflows": "Integração contínua (GitHub Actions)",
    ".github/ISSUE_TEMPLATE": "Modelos para abrir issues",
    "aprendiz/web": "Interface de chat e Monitor: HTML, CSS e JS puros, 100% offline",
    "distribuicao": "Instalador do Windows, empacotamento e ponto de entrada do executável",
    "distribuicao/instalar-windows.ps1": "A lógica do instalador do Windows (chamado por instalar.bat e executar.bat)",
    "distribuicao/empacotar.sh": "Gera o executável Linux com o PyInstaller",
    "distribuicao/empacotar.bat": "Gera o executável Windows com o PyInstaller",
    "docs": "Documentação: estudo, guias e referência (índice em docs/README.md)",
    "docs/README.md": "Índice da documentação: por onde começar e o que tem em cada pasta",
    "docs/estudo": "Como a IA do Aprendiz funciona: algoritmos, linguagem, compreensão, revisão, Monitor",
    "docs/guias": "Como fazer: criar addons, criar algoritmos, instalar e empacotar",
    "docs/referencia": "Mapa do projeto: arquitetura e estrutura de arquivos",
    "requirements": "Dependências opcionais (desenvolvimento, janela nativa, treino)",
    "docs/imagens": "Imagens usadas no README",
    "docs/imagens/tela-principal.png": "Captura da tela principal (README)",
    "exemplos": "Exemplos prontos para usar e estudar",
    "exemplos/addons": "Addons de exemplo (oficiais): fontes e arquivos .aprendiz gerados",
    "exemplos/addons/conversoes-medidas": "Fonte de um addon de memória e linguagem",
    "exemplos/addons/modo-exigente": "Fonte de um addon só de parâmetros",
    "ferramentas": "Ferramentas de desenvolvimento: verificar, criar e conferir addons, homologar, treinar, comparar",
    "ferramentas/dados": "Dados das ferramentas: base do benchmark e perguntas rotuladas da Calibrada",
    "tests": "Testes automatizados (pytest)",
    # ---- raiz
    ".editorconfig": "Padrão de indentação e fim de linha para qualquer editor",
    ".gitattributes": "Fins de linha corretos por tipo de arquivo (LF/CRLF)",
    ".gitignore": "O que nunca vai para o Git (ambiente, bancos, builds)",
    "CHANGELOG.md": "Histórico de versões",
    ".github/CODE_OF_CONDUCT.md": "Código de conduta da comunidade",
    ".github/CONTRIBUTING.md": "Como contribuir: ambiente, padrões e fluxo de PR",
    "LICENSE": "Licença MIT",
    "README.md": "Apresentação, instalação e mapa do projeto",
    ".github/SECURITY.md": "Política de segurança e como reportar falhas",
    "pyproject.toml": "Metadados do pacote Python e configuração do pytest",
    "requirements.txt": "Dependências essenciais (FastAPI, Uvicorn, RapidFuzz)",
    "requirements/dev.txt": "Dependências de desenvolvimento (pytest, httpx, PyInstaller)",
    "requirements/janela.txt": "Dependência opcional da janela nativa (pywebview)",
    "requirements/treino.txt": "Dependência só para treinar a busca Calibrada (scikit-learn)",
    "instalar.sh": "Instalador Linux/macOS: instala o Python se faltar, cria o .venv",
    "executar.sh": "Abre o Aprendiz no Linux/macOS (instala na primeira vez)",
    "instalar.bat": "Instalador Windows (chama distribuicao/instalar-windows.ps1)",
    "executar.bat": "Abre o Aprendiz no Windows (instala na primeira vez)",
    # ---- .github
    ".github/workflows/testes.yml": "Testa a instalação em Windows, Ubuntu, Fedora e Debian",
    ".github/ISSUE_TEMPLATE/bug.md": "Modelo para relatar um erro",
    ".github/ISSUE_TEMPLATE/ideia.md": "Modelo para sugerir uma melhoria",
    ".github/PULL_REQUEST_TEMPLATE.md": "Checklist de pull request",
    # ---- interface
    "aprendiz/web/index.html": "Estrutura da página, ícones SVG e diálogos",
    "aprendiz/web/estilo.css": "Visual: temas claro/escuro, layout, responsivo",
    "aprendiz/web/app.js": "Lógica da interface: chat, envio ao vivo, addons, configurações",
    "aprendiz/web/monitor.js": "Monitor (2.4): pipeline ao vivo, busca, parâmetros do modelo, desempenho e glossário",
    "aprendiz/web/markdown.js": "Mini renderizador de Markdown com proteção contra XSS",
    "aprendiz/web/icone.svg": "Ícone do aplicativo",
    # ---- docs
    "docs/estudo/algoritmos.md": "Como funciona cada algoritmo, com exemplo calculado",
    "docs/estudo/monitor.md": "O Monitor: abas, níveis, fluxo ao vivo (NDJSON) e o que conta como parâmetro",
    "docs/estudo/testes.md": "Como o Aprendiz é testado: metamórficos, fuzz, invariantes, modelos e homologação",
    "docs/guias/addons.md": "Formato .aprendiz, como criar addons e segurança",
    "docs/referencia/arquitetura.md": "Camadas, decisões de projeto e tabelas do banco",
    "docs/estudo/compreensao.md": "Addons de compreensão e vetores: lemas, tipos de pergunta, recomendação",
    "docs/estudo/revisao.md": "Addons de norma e revisão de texto: vocabulário, grafias, regras de gramática",
    "docs/guias/criar-algoritmo.md": "Passo a passo para adicionar um algoritmo ao seletor",
    "docs/guias/empacotamento.md": "Instaladores, executável e problemas comuns",
    "docs/referencia/estrutura.md": "Este mapa (gerado por ferramentas/gerar_estrutura.py)",
    "docs/estudo/linguagem.md": "O pipeline de PLN, etapa por etapa",
    # ---- exemplos e ferramentas
    "ferramentas/dados/dados_exemplo.json": "Base e perguntas usadas no benchmark",
    "ferramentas/dados/conjunto_calibrado.json": "Perguntas rotuladas (treino e teste) da busca Calibrada, geradas das variações dos addons",
    "exemplos/addons/conversoes-medidas.aprendiz": "Addon pronto para importar",
    "exemplos/addons/modo-exigente.aprendiz": "Addon pronto para importar (limiares mais altos)",
    "exemplos/addons/modo-exigente/manifesto.json": "Identidade do addon (origem oficial)",
    "exemplos/addons/modo-exigente/parametros.json": "Limiares de confiança mais exigentes",
    "exemplos/addons/conversoes-medidas/manifesto.json": "Identidade do addon (id, nome, versão, origem…)",
    "exemplos/addons/conversoes-medidas/perguntas.txt": "Pares P:/R: (o jeito mais fácil de escrever)",
    "exemplos/addons/conversoes-medidas/linguagem.json": "Sinônimos e abreviações do addon",
    "exemplos/addons/conversoes-medidas/forno.md": "Texto livre, dividido em trechos",
    "distribuicao/instalar-windows.ps1": "Lógica do instalador Windows (baixa o Python se faltar)",
}


MAX_DESCRICAO = 90


def docstring(arquivo: Path) -> str | None:
    """
    Primeiro parágrafo do docstring de um módulo Python, numa linha só.
    Se for longo, corta numa palavra inteira e termina com "…".
    """
    try:
        doc = ast.get_docstring(ast.parse(arquivo.read_text(encoding="utf-8")))
    except SyntaxError:
        return None
    if not doc:
        return None
    paragrafo = " ".join(doc.strip().split("\n\n")[0].split())
    if len(paragrafo) <= MAX_DESCRICAO:
        return paragrafo
    return paragrafo[:MAX_DESCRICAO].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def descricao(caminho: Path) -> str | None:
    rel = caminho.relative_to(RAIZ).as_posix()
    if rel in DESCRICOES:
        return DESCRICOES[rel]
    if caminho.is_dir() and (caminho / "__init__.py").exists():
        return docstring(caminho / "__init__.py")
    if caminho.suffix == ".py":
        return docstring(caminho)
    return None


def visivel(caminho: Path) -> bool:
    return caminho.name not in IGNORAR and caminho.suffix not in IGNORAR_SUFIXOS


def filhos(pasta: Path) -> list[Path]:
    itens = [p for p in pasta.iterdir() if visivel(p)]
    # Pastas primeiro, depois arquivos; ordem alfabética sem diferenciar maiúsculas.
    return sorted(itens, key=lambda p: (p.is_file(), p.name.lower()))


def arvore(pasta: Path, prefixo: str = "") -> list[tuple[str, str | None, Path]]:
    linhas = []
    itens = filhos(pasta)
    for i, item in enumerate(itens):
        ultimo = i == len(itens) - 1
        ramo = "└── " if ultimo else "├── "
        nome = item.name + ("/" if item.is_dir() else "")
        # __init__.py de pacote repete a descrição da pasta: mostramos assim mesmo
        # (é um arquivo real), mas com um texto padrão quando não há docstring.
        linhas.append((prefixo + ramo + nome, descricao(item), item))
        if item.is_dir():
            linhas += arvore(item, prefixo + ("    " if ultimo else "│   "))
    return linhas


def gerar() -> tuple[str, list[str]]:
    """Devolve (markdown, lista de caminhos sem descrição)."""
    linhas = arvore(RAIZ)
    largura = max(len(texto) for texto, _, _ in linhas) + 2
    faltando = [p.relative_to(RAIZ).as_posix() for _, d, p in linhas if not d]
    corpo = "\n".join(
        f"{texto.ljust(largura)}# {d}" if d else texto for texto, d, _ in linhas
    )
    md = f"""# Estrutura do projeto

Mapa de todas as pastas e arquivos, com o papel de cada um.

> Gerado automaticamente por `ferramentas/gerar_estrutura.py` a partir dos docstrings
> do código. **Não edite à mão:** rode `python ferramentas/gerar_estrutura.py`.

## Por onde começar a estudar

1. `aprendiz/core/assistente.py`: o pipeline completo de uma mensagem
2. `aprendiz/linguagem/normalizador.py`: como o texto é preparado
3. `aprendiz/linguagem/stemmer.py` e `intencoes.py`: radicais e Naive Bayes
4. `aprendiz/algoritmos/busca/tfidf.py`: o algoritmo mais didático
5. `aprendiz/algoritmos/busca/bm25.py` e `hibrido.py`: busca de verdade
6. `aprendiz/algoritmos/busca/calibrado.py`: aprendizado de máquina (regressão logística)
7. `aprendiz/algoritmos/resposta/extrativa.py`: TextRank
8. `aprendiz/memoria/banco.py`: SQLite, FTS5, migrações
9. `aprendiz/api/servidor.py`, `aprendiz/web/app.js` e `monitor.js`: como a interface conversa com o núcleo

## Árvore

```
aprendiz/
{corpo}
```
"""
    return md, faltando


def main() -> None:
    md, faltando = gerar()
    if faltando:
        print("Arquivos sem descrição (escreva o docstring ou adicione em DESCRICOES):")
        for f in faltando:
            print("  -", f)
        sys.exit(1)
    DESTINO.write_text(md, encoding="utf-8")
    print(f"[OK] {DESTINO.relative_to(RAIZ)} atualizado.")


if __name__ == "__main__":
    main()
