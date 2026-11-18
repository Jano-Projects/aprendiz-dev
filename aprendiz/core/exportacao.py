"""
Exportação: transforma o que o DONO ensinou num addon (.aprendiz) para compartilhar.

Fluxo (duas etapas, para o dono ver e escolher antes de gerar o arquivo):

    1. previa(banco)   → tudo o que PODE ser exportado, item a item:
                           • conhecimentos ensinados pelo dono
                           • sinônimos e abreviações que o dono acrescentou
                             (as sementes de fábrica ficam de fora: todo
                             Aprendiz já tem)
                           • parâmetros e personalização que o dono definiu
                           • addons instalados (viram DEPENDÊNCIAS)
                         Itens com cara de dado pessoal (senha, e-mail,
                         telefone, CPF, números longos…) vêm DESMARCADOS e
                         com um aviso do motivo.

    2. exportar(banco, escolha) → bytes do arquivo .aprendiz, só com o que
                         o dono marcou.

A prévia e a exportação também RECOMENDAM o algoritmo de busca e o de
resposta, testando os próprios itens (core/recomendacao.py). O dono pode
trocar a recomendação antes de gerar o arquivo; ela vai no manifesto.

Regras que não mudam com a escolha do dono:

    • origem é SEMPRE "terceiros": "oficial" é reservado à Jano Projects.
    • addons instalados entram só como referência (id + versão + nome). O
      conteúdo deles NÃO é copiado: quem receber o arquivo instala cada
      dependência da fonte original. Isso respeita a licença de cada addon
      e evita cópias desatualizadas.
    • o manifesto registra a versão do app que gerou o arquivo.

Nada sai do computador: o arquivo é gerado e entregue ao navegador, que
salva onde o dono escolher.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from aprendiz import addons as pacotes
from aprendiz import configuracoes as cfg
from aprendiz.algoritmos import BUSCAS, RESPOSTAS, titulo_curto
from aprendiz.core.recomendacao import recomendar
from aprendiz.linguagem import extrair_entidades, normalizar
from aprendiz.memoria import sementes

# Palavras que costumam aparecer perto de dados pessoais. A comparação é
# feita no texto normalizado (minúsculas, sem acento).
_PALAVRAS_SENSIVEIS = re.compile(
    r"\b(senha|password|pin|cpf|cnpj|rg|cartao|cvv|agencia|conta bancaria|"
    r"chave pix|pix|token|login|usuario|endereco|placa|nascimento)\b")
_NUMERO_LONGO = re.compile(r"\d{6,}")


def avisos_privacidade(texto: str) -> list[str]:
    """
    Motivos para suspeitar que o texto tem dado pessoal. Lista vazia = nada
    suspeito. É uma heurística: ajuda o dono a revisar, não garante nada.
    """
    motivos: list[str] = []
    for e in extrair_entidades(texto):
        if e["tipo"] in ("email", "telefone"):
            motivos.append(e["tipo"])
    if _NUMERO_LONGO.search(texto.replace(".", "").replace("-", "")):
        motivos.append("número longo")
    motivos += _PALAVRAS_SENSIVEIS.findall(normalizar(texto))
    return sorted(set(motivos))


def _linguagem_do_dono(banco) -> dict[str, list[dict[str, str]]]:
    """Sinônimos/abreviações do dono que NÃO vieram das sementes de fábrica."""
    fabrica = {
        "abreviacoes": {normalizar(t): normalizar(v) for t, v in sementes.ABREVIACOES.items()},
        "sinonimos": {normalizar(t): normalizar(v) for t, v in
                      {**sementes.SINONIMOS, **sementes.SINONIMOS_V3}.items()},
    }
    atuais = {"abreviacoes": banco.mapa_abreviacoes(incluir_addons=False),
              "sinonimos": banco.mapa_sinonimos(incluir_addons=False)}
    return {
        tipo: [{"termo": t, "valor": v} for t, v in sorted(mapa.items())
               if fabrica[tipo].get(t) != v]
        for tipo, mapa in atuais.items()
    }


def previa(banco, recomendar: bool = True) -> dict[str, Any]:
    """Tudo o que pode ser exportado, já com a sugestão de marcação."""
    conhecimentos = []
    for k in banco.listar_conhecimentos(limite=pacotes.MAX_CONHECIMENTOS):
        avisos = avisos_privacidade(f"{k['pergunta'] or ''} {k['conteudo']}")
        conhecimentos.append({
            "id": k["id"], "tipo": k["tipo"], "pergunta": k["pergunta"],
            "conteudo": k["conteudo"], "avisos": avisos, "marcado": not avisos,
        })

    configuracoes = cfg.Configuracoes(banco)
    def bloco(tipo: str) -> list[dict[str, Any]]:
        # Os algoritmos padrão NÃO viram parâmetros do addon: eles vão como
        # RECOMENDAÇÃO, que quem instala aceita ou não (parâmetros valeriam
        # sem perguntar).
        return [{"chave": c, "titulo": cfg.DEFINICOES[c].titulo, "valor": v, "marcado": True}
                for c, v in configuracoes.do_dono(tipo).items()
                if c not in ("busca.padrao", "resposta.padrao")]

    dependencias = [{
        "id": a["id"], "nome": a["nome"], "versao": a["versao"], "ativo": bool(a["ativo"]),
        "origem": (a["manifesto"] or {}).get("origem", "terceiros"),
        "marcado": bool(a["ativo"]),
    } for a in banco.listar_addons()]

    linguagem = _linguagem_do_dono(banco)
    return {
        "conhecimentos": conhecimentos,
        "linguagem": linguagem,
        "recomendacao": recomendar_para(
            [k for k in conhecimentos if k["marcado"]],
            {t: {e["termo"]: e["valor"] for e in lista} for t, lista in linguagem.items()},
        ) if recomendar else None,
        "parametros": bloco("parametros"),
        "personalizacao": bloco("personalizacao"),
        "dependencias": dependencias,
        "app": {"versao": pacotes.__version__},
    }


def recomendar_para(itens: list[dict[str, Any]],
                    linguagem: dict[str, dict[str, str]] | None = None) -> dict[str, Any] | None:
    """Recomendação de algoritmos para estes itens, com os títulos para a interface."""
    rec = recomendar([{k: v for k, v in item.items() if k in ("pergunta", "conteudo", "tipo")}
                      for item in itens],
                     {t: m for t, m in (linguagem or {}).items() if m})
    if rec:
        rec["titulo_busca"] = titulo_curto(BUSCAS, rec["busca"])
        rec["titulo_resposta"] = titulo_curto(RESPOSTAS, rec["resposta"])
    return rec


def exportar(banco, escolha: dict[str, Any]) -> tuple[str, bytes]:
    """
    Gera o .aprendiz. `escolha` traz o manifesto digitado pelo dono e as
    listas do que foi MARCADO na prévia:

        {"manifesto": {"id", "nome", "versao", "autor", "descricao", "licenca"},
         "conhecimentos": [ids], "abreviacoes": [termos], "sinonimos": [termos],
         "parametros": [chaves], "personalizacao": [chaves], "dependencias": [ids],
         "recomendado": {"busca": "bm25", "resposta": "direta"}}   ← opcional

    Sem "recomendado", vale o resultado do teste com os itens exportados. Com
    ele, vale a escolha do dono, e o "acerto" é o que aquele algoritmo teve
    no teste.

    Devolve (nome_do_arquivo, bytes). Lança ErroAddon se algo estiver inválido.
    """
    dados = previa(banco, recomendar=False)

    def marcados(lista: list[dict], chave: str, escolhidos: list) -> list[dict]:
        escolhidos = set(escolhidos or [])
        return [item for item in lista if item[chave] in escolhidos]

    conhecimentos = [
        {k: v for k, v in (("pergunta", item["pergunta"]), ("conteudo", item["conteudo"]),
                           ("tipo", item["tipo"])) if v}
        for item in marcados(dados["conhecimentos"], "id", escolha.get("conhecimentos"))
    ]
    linguagem = {
        tipo: {e["termo"]: e["valor"]
               for e in marcados(dados["linguagem"][tipo], "termo", escolha.get(tipo))}
        for tipo in ("abreviacoes", "sinonimos")
    }
    linguagem = {t: m for t, m in linguagem.items() if m}
    parametros = {c["chave"]: c["valor"] for c in
                  marcados(dados["parametros"], "chave", escolha.get("parametros"))}
    personalizacao = {c["chave"]: c["valor"] for c in
                      marcados(dados["personalizacao"], "chave", escolha.get("personalizacao"))}
    dependencias = [{"id": d["id"], "versao": d["versao"], "nome": d["nome"]}
                    for d in marcados(dados["dependencias"], "id", escolha.get("dependencias"))]

    if not (conhecimentos or linguagem or parametros or personalizacao):
        raise pacotes.ErroAddon("Marque pelo menos um item para exportar.")

    informado = escolha.get("manifesto") or {}
    manifesto = {campo: informado.get(campo) for campo in
                 ("id", "nome", "versao", "autor", "descricao", "licenca", "site")}
    manifesto["versao"] = manifesto["versao"] or "1.0.0"
    if not manifesto["id"] and manifesto["nome"]:
        manifesto["id"] = re.sub(r"[^a-z0-9]+", "-", normalizar(manifesto["nome"])).strip("-")[:63]
    if manifesto["id"] in {d["id"] for d in dependencias}:
        raise pacotes.ErroAddon("O id do seu addon não pode ser igual ao de uma dependência.")
    # Recomendação: o teste roda sobre exatamente o que vai no arquivo.
    escolhido = escolha.get("recomendado") or {}
    for campo, registro in (("busca", BUSCAS), ("resposta", RESPOSTAS)):
        if escolhido.get(campo) and escolhido[campo] not in registro:
            raise pacotes.ErroAddon(f"Algoritmo desconhecido em 'recomendado.{campo}': "
                                    f"{escolhido[campo]!r}.")
    teste = recomendar(conhecimentos, linguagem) if conhecimentos else None
    if teste or escolhido.get("busca"):
        busca = escolhido.get("busca") or teste["busca"]
        manifesto["recomendado"] = {
            "busca": busca,
            "resposta": escolhido.get("resposta") or (teste["resposta"] if teste else "direta"),
            **({"acerto": teste["acertos"][busca]} if teste else {}),
        }

    manifesto.update(
        origem="terceiros",            # sempre: "oficial" é só da Jano Projects
        dependencias=dependencias,
        criado_em=date.today().isoformat(),
    )

    conteudo = pacotes.criar_pacote(manifesto, conhecimentos, linguagem,
                                    parametros, personalizacao)
    return f"{manifesto['id']}{pacotes.EXTENSAO}", conteudo
