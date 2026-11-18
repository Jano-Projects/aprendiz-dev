"""
Compreensão: o motor que usa os addons "compreensao" e "vetores" (0.7+).

O motor fica no app; os DADOS (frases-gatilho, expressões, lemas, vetores,
catálogo da loja) vêm dos addons. Sem addon de compreensão ativo, todos os
métodos daqui devolvem "nada a fazer" e o Aprendiz funciona como antes.

O que ele faz, na ordem em que o pipeline (core/assistente.py) usa:

    1. TIPO DA PERGUNTA — "o que é", "como faço", "onde fica"... e o ASSUNTO
       (o resto da frase). Aparece no painel "Por que respondi isso?" e deixa
       a resposta "ainda não sei" mais precisa ("não sei COMO fazer X").

    2. AUTOCONHECIMENTO — perguntas sobre o próprio Aprendiz ("qual a sua
       versão?", "o que você não sabe fazer?"). Respostas calculadas na hora
       (funções da lista fechada recursos.FUNCOES) ou textos do addon.

    3. Quando a busca não encontra nada:
       a. FORA DE ALCANCE — pedidos impossíveis offline ("previsão do
          tempo", "pesquise na internet"): explica a limitação.
       b. EXPANSÃO POR SENTIDO (precisa do addon de vetores) — troca as
          palavras da pergunta pelas de sentido mais próximo que EXISTEM na
          base ("automóvel" → "carro") e busca de novo.
       c. RECOMENDAÇÃO — procura no catálogo da loja (que vem dentro do
          addon) um addon que trate do assunto. Se ele já estiver instalado
          mas desativado, sugere ativá-lo.

Tudo é comparação de palavras e de vetores; nenhuma regex vem de addon.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rapidfuzz import fuzz

from aprendiz.linguagem.normalizador import normalizar, tokenizar
from aprendiz.linguagem.lexico import cosseno
from aprendiz.linguagem.stemmer import radical
from aprendiz.recursos import TIPOS_PERGUNTA

# Palavras de cortesia que podem vir ANTES do gatilho: "você sabe o que é…",
# "por favor, como faço…". São puladas ao procurar o tipo da pergunta.
_CORTESIA = {"voce", "sabe", "sabes", "me", "diga", "diz", "fala", "conta", "por", "favor",
             "aprendiz", "ei", "oi", "ola", "entao", "e", "ai", "tu"}
MAX_CORTESIA = 3

SEMELHANCA_AUTOCONHECIMENTO = 90     # 0-100 (rapidfuzz), sobre as palavras inteiras
SEMELHANCA_EXPANSAO = 0.62           # cosseno mínimo para trocar uma palavra
FATOR_APELIDO = 0.85                 # palavra que só empresta o vetor de outra vale menos
VIZINHOS_POR_PALAVRA = 2
PALAVRAS_MUITO_COMUNS = 1000         # as N mais frequentes ("quero", "mudar") não são trocadas
SEMELHANCA_CATALOGO = 0.66           # cosseno mínimo entre palavra e addon
PONTUACAO_RECOMENDACAO = 0.45        # fração (ponderada) das palavras da pergunta cobertas
BONUS_INSTALADO = 0.1                # desempate a favor de um addon já instalado (desativado)

# "Entendi que você quer saber ..." — por tipo de pergunta
FRASE_TIPO = {
    "definicao": "o que é", "procedimento": "como", "localizacao": "onde fica",
    "tempo": "quando", "causa": "por que", "quantidade": "quanto",
    "pessoa": "quem", "escolha": "qual", "confirmacao": "se",
}


@dataclass
class Analise:
    """O que a compreensão entendeu de uma mensagem (vai para o painel)."""

    tipo: str | None = None
    titulo_tipo: str | None = None
    gatilho: str | None = None
    assunto: str | None = None
    inicio_assunto: int = 0          # posição (nos tokens) onde o assunto começa
    necessidades: list[str] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        return {"tipo": self.titulo_tipo or "—", "gatilho": self.gatilho or "—",
                "assunto": self.assunto or "—",
                "necessidade deduzida": ", ".join(self.necessidades) or "—"}


def _contem(tokens: list[str], trecho: tuple[str, ...]) -> int:
    """Posição em que `trecho` aparece em `tokens` (sequência contígua), ou -1."""
    n = len(trecho)
    for i in range(len(tokens) - n + 1):
        if tuple(tokens[i:i + n]) == trecho:
            return i
    return -1


class Compreensao:
    def __init__(self, banco, linguagem) -> None:
        self.banco = banco
        self.linguagem = linguagem
        self._versao = -1
        self._versao_vocab = (-1, -1)
        self.dados: dict[str, Any] = {}
        self._vocab_vetores: dict[str, list[float]] = {}
        self._vetores_catalogo: dict[str, list[tuple[str, list[float]]]] = {}

    # ------------------------------------------------------------------ dados
    def _frase(self, texto: str) -> tuple[str, ...]:
        """Gatilho processado do MESMO jeito que a mensagem (lemas, sinônimos...)."""
        return tuple(self.linguagem.processar(texto, corrigir=False).tokens)

    def _carregar(self) -> None:
        """Junta os compreensao.json dos addons ativos (refaz quando algo muda)."""
        if self._versao == self.banco.versao_linguagem:
            return
        dados: dict[str, list] = {"tipos_pergunta": [], "autoconhecimento": [],
                                  "fora_de_alcance": [], "necessidades": [], "catalogo": []}
        auto: dict[str, dict] = {}
        catalogo: dict[str, dict] = {}
        for _, bruto in self.banco.recursos_ativos("compreensao.json"):
            doc = json.loads(bruto)
            vistos: set[tuple[str, ...]] = set()
            for item in doc.get("tipos_pergunta", []):
                for g in item["gatilhos"]:
                    frase = self._frase(g)
                    if frase and frase not in vistos:
                        vistos.add(frase)
                        dados["tipos_pergunta"].append((frase, item["tipo"], g))
            for item in doc.get("autoconhecimento", []):
                auto[item["id"]] = {**item, "_frases": [
                    " ".join(self._frase(p)) for p in item["perguntas"]]}
            for item in doc.get("fora_de_alcance", []):
                dados["fora_de_alcance"].append(
                    {**item, "_frases": [self._frase(g) for g in item["gatilhos"]]})
            for item in doc.get("necessidades", []):
                dados["necessidades"].append(
                    {**item, "_frases": [self._frase(g) for g in item["gatilhos"]]})
            for item in doc.get("catalogo", []):
                # Peso de cada radical: as primeiras palavras da lista (nome,
                # etiquetas, região, as mais repetidas) valem mais que as últimas.
                radicais = self.linguagem.processar(" ".join(item["palavras"]), corrigir=False).radicais
                pesos: dict[str, float] = {}
                for i, r in enumerate(radicais):
                    pesos.setdefault(r, 1.0 - 0.5 * i / max(1, len(radicais)))
                catalogo[item["id"]] = {**item, "_radicais": pesos}
        # Gatilho mais longo primeiro: "o que significa" vence "o que".
        dados["tipos_pergunta"].sort(key=lambda t: -len(t[0]))
        dados["autoconhecimento"] = list(auto.values())
        dados["catalogo"] = list(catalogo.values())
        self.dados = dados
        self._vetores_catalogo = {}
        self._versao = self.banco.versao_linguagem

    @property
    def ativa(self) -> bool:
        self._carregar()
        return any(self.dados.values())

    # ------------------------------------------------------------------ 1. tipo
    def analisar(self, consulta, mensagem: str) -> Analise:
        """Tipo da pergunta, assunto e necessidades deduzidas."""
        self._carregar()
        analise = Analise()
        tokens = consulta.tokens
        for frase, tipo, original in self.dados["tipos_pergunta"]:
            inicio = _contem(tokens[:MAX_CORTESIA + len(frase)], frase)
            if inicio < 0 or any(t not in _CORTESIA for t in tokens[:inicio]):
                continue
            analise.tipo, analise.gatilho = tipo, original
            analise.titulo_tipo = TIPOS_PERGUNTA[tipo]
            analise.assunto = self._assunto(mensagem, inicio + len(frase))
            analise.inicio_assunto = inicio + len(frase)
            break
        for item in self.dados["necessidades"]:
            if any(_contem(tokens, f) >= 0 for f in item["_frases"]):
                analise.necessidades.extend(p for p in item["palavras"]
                                            if p not in analise.necessidades)
        return analise

    def _assunto(self, mensagem: str, pular: int) -> str | None:
        """
        O resto da mensagem ORIGINAL depois do gatilho (com acentos e
        maiúsculas, para mostrar à pessoa). Conta quantas palavras
        processadas cada palavra original rende ("oq" → "o que" = 2).
        """
        palavras = mensagem.split()
        consumidas = i = 0
        while consumidas < pular and i < len(palavras):
            consumidas += len(self.linguagem._expandir(tokenizar(normalizar(palavras[i])), {}))
            i += 1
        assunto = " ".join(palavras[i:]).strip(" ?!.,;:")
        return assunto or None

    # ------------------------------------------------------------------ 2. sobre mim
    def autoconhecimento(self, consulta) -> dict[str, Any] | None:
        """O item de autoconhecimento mais parecido com a mensagem, se houver."""
        self._carregar()
        tokens = list(consulta.tokens)
        while tokens and tokens[0] in _CORTESIA and len(tokens) > 2:
            # "aprendiz, qual a sua versão" = "qual a sua versão"
            if tokens[0] in ("aprendiz", "ei", "oi", "ola"):
                tokens.pop(0)
            else:
                break
        while tokens and tokens[-1] in ("aprendiz", "por", "favor"):
            tokens.pop()
        texto = " ".join(tokens)
        melhor, nota_melhor = None, 0.0
        for item in self.dados["autoconhecimento"]:
            for frase in item["_frases"]:
                if abs(len(frase) - len(texto)) > max(6, len(frase) // 3):
                    continue
                nota = 100.0 if frase == texto else fuzz.ratio(frase, texto)
                if nota > nota_melhor:
                    melhor, nota_melhor = item, nota
        if melhor and nota_melhor >= SEMELHANCA_AUTOCONHECIMENTO:
            return {**melhor, "semelhanca": round(nota_melhor, 1)}
        return None

    # ------------------------------------------------------------------ 3a. limites
    def fora_de_alcance(self, consulta) -> dict[str, Any] | None:
        self._carregar()
        for item in self.dados["fora_de_alcance"]:
            if any(_contem(consulta.tokens, f) >= 0 for f in item["_frases"]):
                return item
        return None

    # ------------------------------------------------------------------ 3b. vetores
    def _vocabulario_com_vetores(self) -> dict[str, tuple[list[float], bool]]:
        """Palavras da base ativa que têm vetor (refeito quando a base muda)."""
        chave = (self.banco.versao_conhecimento, self.banco.versao_linguagem)
        if self._versao_vocab != chave:
            self.linguagem._atualizar_vocabulario()
            lexico = self.linguagem.lexico
            self._vocab_vetores = {}
            for palavra in self.linguagem.vocabulario:
                if palavra in self.linguagem.stopwords or len(palavra) < 3:
                    continue
                info = lexico.vetor_info(palavra)
                if info:
                    self._vocab_vetores[palavra] = info
            self._versao_vocab = chave
        return self._vocab_vetores

    def expandir(self, consulta) -> list[dict[str, Any]]:
        """
        Para cada palavra da pergunta que NÃO está na base, as palavras da
        base de sentido mais próximo. Ex.: base fala de "carro"; a pergunta
        diz "automóvel" → [{"de": "automovel", "para": "carro", ...}].
        """
        lexico = self.linguagem.lexico
        lexico._atualizar()
        if not lexico.tem_vetores:
            return []
        vocab = self._vocabulario_com_vetores()
        if not vocab:
            return []
        radicais_base = set(consulta.radicais)
        trocas: list[dict[str, Any]] = []
        for palavra in dict.fromkeys(consulta.conteudo):
            if palavra in vocab or palavra.isdigit() or lexico.frequente(palavra, PALAVRAS_MUITO_COMUNS):
                continue
            info = lexico.vetor_info(palavra)
            if not info:
                continue
            vetor, apelido = info
            fator = FATOR_APELIDO if apelido else 1.0
            notas = sorted(((cosseno(vetor, v) * fator * (FATOR_APELIDO if ap else 1.0), p)
                            for p, (v, ap) in vocab.items()), reverse=True)
            for nota, vizinha in notas[:VIZINHOS_POR_PALAVRA]:
                if nota < SEMELHANCA_EXPANSAO:
                    break
                processada = self.linguagem.processar(vizinha, corrigir=False)
                if set(processada.radicais) <= radicais_base:
                    continue
                trocas.append({"de": palavra, "para": vizinha, "semelhanca": round(nota, 2)})
        return trocas

    # ------------------------------------------------------------------ 3c. loja
    def _vetores_do_addon(self, item: dict) -> list[tuple[str, list[float]]]:
        if item["id"] not in self._vetores_catalogo:
            lexico = self.linguagem.lexico
            pares = []
            for p in item["palavras"][:200]:
                v = lexico.vetor(p, apelidos=False)  # só palavras com vetor próprio
                if v:
                    pares.append((p, v))
            self._vetores_catalogo[item["id"]] = pares
        return self._vetores_catalogo[item["id"]]

    def recomendar(self, consulta, analise: Analise | None = None) -> dict[str, Any] | None:
        """
        O addon do catálogo (dentro do addon de compreensão) que melhor cobre
        as palavras da pergunta + as necessidades deduzidas. Ignora addons que
        já estão ATIVOS (a busca já olhou para eles).
        """
        self._carregar()
        if not self.dados["catalogo"]:
            return None
        instalados = {a["id"]: a for a in self.banco.listar_addons()}
        extras = set(self.linguagem.processar(" ".join(analise.necessidades), corrigir=False).radicais) \
            if analise and analise.necessidades else set()
        # Só o ASSUNTO conta ("o que significa kota" → kota): as palavras do
        # gatilho, o nome do app e as palavras muito comuns não dizem de que
        # trata a pergunta. radical → palavra (para mostrar o motivo).
        inicio = analise.inicio_assunto if analise else 0
        palavras = [t for t in consulta.tokens[inicio:]
                    if t not in self.linguagem.stopwords and not t.isdigit() and t != "aprendiz"]
        pergunta = {radical(t): t for t in palavras}
        # Palavras muito comuns ("mudar", "cor") contam menos que as raras ("kota").
        peso_pergunta = {r: 0.3 if self.linguagem.lexico.frequente(t, PALAVRAS_MUITO_COMUNS) else 1.0
                         for r, t in pergunta.items()}
        if not pergunta and not extras:
            return None
        lexico = self.linguagem.lexico
        usar_vetores = lexico.tem_vetores
        vetores_pergunta = {r: lexico.vetor_info(p) for r, p in pergunta.items()} if usar_vetores else {}

        melhor, chave_melhor = None, (0.0, 0.0)
        for item in self.dados["catalogo"]:
            atual = instalados.get(item["id"])
            if atual and atual["ativo"]:
                continue
            pesos = item["_radicais"]
            comuns = [r for r in pergunta if r in pesos]
            parecidas: list[str] = []
            if usar_vetores:
                for r, info in vetores_pergunta.items():
                    if r in comuns or not info:
                        continue
                    v, apelido = info
                    minimo = SEMELHANCA_CATALOGO / (FATOR_APELIDO if apelido else 1.0)
                    if any(cosseno(v, w) >= minimo for _, w in self._vetores_do_addon(item)):
                        parecidas.append(r)
            nota = ((sum(pesos[r] * peso_pergunta[r] for r in comuns)
                     + sum(0.6 * peso_pergunta[r] for r in parecidas))
                    / (sum(peso_pergunta.values()) or 1.0))
            if extras:
                # Necessidade deduzida ("estou com fome" → receita, cozinha...)
                nota += len(extras & pesos.keys()) / len(extras)
            # Quase empate: melhor indicar um addon que a pessoa JÁ tem (só ativar).
            chave = (round(nota + (BONUS_INSTALADO if atual else 0.0), 4), nota)
            if chave > chave_melhor:
                melhor, chave_melhor = {"item": item, "comuns": comuns, "parecidas": parecidas}, chave
        nota_melhor = chave_melhor[1]
        if not melhor or nota_melhor < PONTUACAO_RECOMENDACAO:
            return None
        item = melhor["item"]
        atual = instalados.get(item["id"])
        return {
            "id": item["id"], "nome": item["nome"], "descricao": item["descricao"],
            "acao": "ativar" if atual else "loja",
            "pontuacao": round(nota_melhor, 2),
            "motivo": [pergunta[r] for r in melhor["comuns"] + melhor["parecidas"]],
        }


# ====================================================================== respostas
def resposta_dinamica(funcao: str, assistente) -> str:
    """Respostas de autoconhecimento calculadas na hora (recursos.FUNCOES)."""
    from aprendiz import __version__
    from aprendiz.algoritmos import BUSCAS, RESPOSTAS, titulo_curto

    banco = assistente.banco
    addons = banco.listar_addons()
    ativos = [a for a in addons if a["ativo"]]

    if funcao == "versao":
        return (f"Sou o **Aprendiz**, versão **{__version__}**. Sou um assistente pessoal "
                "que funciona 100% offline: aprendo com o que você me ensina e com os "
                "addons que você instala.")
    if funcao == "addons":
        if not addons:
            return "Não tenho nenhum addon instalado. Você encontra addons na loja oficial."
        linhas = "\n".join(f"- {a['nome']} ({a['versao']})" for a in ativos) or "- nenhum"
        texto = f"Tenho **{len(ativos)}** addon(s) ativo(s):\n\n{linhas}"
        desligados = len(addons) - len(ativos)
        if desligados:
            texto += f"\n\nE mais {desligados} instalado(s), mas desativado(s)."
        return texto
    if funcao == "conhecimentos":
        total = banco.contar_conhecimentos()
        de_addons = banco.contar_conhecimentos(de_addons=True)
        return (f"Sei **{total}** coisa(s): **{total - de_addons}** que você me ensinou e "
                f"**{de_addons}** que vieram de addons.")
    if funcao == "algoritmos":
        config = assistente.configuracoes
        busca, resposta = config.valor("busca.padrao"), config.valor("resposta.padrao")
        return (f"Agora eu busco com **{titulo_curto(BUSCAS, busca)}** e monto a resposta com "
                f"**{titulo_curto(RESPOSTAS, resposta)}**.\n\nBuscas disponíveis: "
                + ", ".join(a.titulo for a in BUSCAS.values())
                + ".\nRespostas disponíveis: " + ", ".join(a.titulo for a in RESPOSTAS.values())
                + ".\n\nVocê troca isso nos seletores ou em Configurações.")
    if funcao == "capacidades":
        partes = [
            "- responder o que você me ensinou (perguntas, notas e arquivos .txt/.md);",
            "- aprender na conversa: `aprenda que a senha do wifi é casa123`;",
            "- ser corrigido: a resposta certa vira um novo ensinamento;",
            "- mostrar por que respondi cada coisa (botão **Por que respondi isso?**);",
        ]
        if any(a["manifesto"].get("regiao") for a in ativos):
            partes.append("- traduzir gírias e expressões dos países de língua portuguesa;")
        normas = assistente.normas_disponiveis()
        if normas:
            nomes = ", ".join(n["nome"] for n in normas)
            partes.append(f"- revisar textos pela norma da língua ({nomes}): escreva "
                          "`revise: seu texto` ou pergunte `o certo é X ou Y?`;")
        lexico = assistente.linguagem.lexico
        lexico._atualizar()
        if assistente.compreensao.ativa:
            partes.append("- entender o tipo de pergunta, expressões e formas irregulares "
                          "das palavras, e indicar um addon quando não sei algo;")
        if assistente.dialogo.ativo:
            partes.append("- conversar além de pergunta e resposta: entendo pedidos de ajuda, "
                          "desabafos e pedidos de opinião, e uso a conversa (\"não entendi\", "
                          "\"não era isso\", \"e em Portugal?\");")
        if lexico.tem_vetores:
            partes.append("- procurar por sentido: se você usa uma palavra que não está na "
                          "base, tento as de significado parecido;")
        return "Eu consigo:\n\n" + "\n".join(partes)
    if funcao == "limitacoes":
        contexto = ("- da conversa, só uso a última troca (para \"não entendi\", \"sim\", "
                    "\"e em Portugal?\"); não tenho opiniões nem sentimentos próprios."
                    if assistente.dialogo.ativo else
                    "- não guardo o contexto da conversa: cada pergunta é respondida sozinha.")
        return ("Minhas limitações:\n\n"
                "- **não acesso a internet**: não sei notícias, clima, cotações nem nada que "
                "você não tenha me ensinado ou que não venha de um addon;\n"
                "- **não invento**: só respondo com o que está na minha base; se não sei, "
                "digo que não sei;\n"
                "- **não executo nada** no seu computador (não abro programas, não envio "
                "mensagens, não crio lembretes);\n"
                "- entendo **português**; outras línguas, só o que addons de dicionário trazem;\n"
                + contexto)
    if funcao == "privacidade":
        return ("Tudo fica **no seu computador**, num banco de dados local:\n\n"
                f"`{banco.caminho}`\n\nNada do que você me ensina ou pergunta é enviado para a "
                "internet. O único acesso externo é o botão da loja oficial, e só quando você "
                "clica nele.")
    if funcao == "hora":
        return f"Agora são **{datetime.now():%H:%M}** (horário deste computador)."
    if funcao == "data":
        meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                 "agosto", "setembro", "outubro", "novembro", "dezembro"]
        dias = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                "sexta-feira", "sábado", "domingo"]
        h = datetime.now()
        return f"Hoje é **{dias[h.weekday()]}, {h.day} de {meses[h.month - 1]} de {h.year}**."
    if funcao == "recomendacoes":
        assistente.compreensao._carregar()
        instalados = {a["id"] for a in addons}
        faltam = [i for i in assistente.compreensao.dados["catalogo"] if i["id"] not in instalados]
        if not faltam:
            return "Você já tem todos os addons da loja oficial que eu conheço."
        linhas = "\n".join(f"- **{i['nome']}**: {i['descricao']}" for i in faltam[:12])
        return f"Addons da loja oficial que você ainda não tem:\n\n{linhas}"
    if funcao == "ensinar":
        return ("Você me ensina de três jeitos:\n\n"
                "- na conversa: `aprenda que a senha do wifi é casa123` ou "
                "`pergunta: horário da farmácia resposta: 8h às 20h`;\n"
                "- pelo botão **Ensinar isso**, quando eu não souber algo;\n"
                "- importando arquivos .txt/.md ou addons (.aprendiz) na tela **Addons**.")
    return "Não sei responder isso sobre mim."
