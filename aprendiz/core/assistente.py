"""
O pipeline: a classe que junta linguagem, memória e algoritmos.

Fluxo de uma mensagem (método `responder`):

    mensagem
       │
       ├─ 1. Normalização ........ linguagem.processar()
       ├─ 2. Ensino explícito? ... "aprenda que X é Y" / "pergunta: ... resposta: ..."
       ├─ 2a. Revisão de texto ... "revise: ..." / "o certo é X ou Y?" (addon de norma)
       ├─ 3. Interpretação ....... intenção (Naive Bayes) + entidades (regex)
       ├─ 4. Intenção social? .... "oi", "obrigado", "ajuda" → resposta pronta
       ├─ 4b. Compreensão ........ tipo da pergunta; perguntas sobre o Aprendiz
       ├─ 5. Busca ............... algoritmo escolhido no seletor
       ├─ 6. Modo estrito ........ nada acima do limiar → antes de desistir:
       │                           fora de alcance? busca por sentido (vetores)?
       │                           algum addon da loja trata disso?
       └─ 7. Resposta ............ algoritmo de resposta escolhido no seletor

As etapas 4b e 6 só fazem algo com um addon de compreensão ativo (0.7+);
veja core/compreensao.py.

Cada etapa registra o que fez e quanto tempo levou. Esse registro vira a
"explicação" exibida no painel "Por que respondi isso?" da interface.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any

from rapidfuzz import fuzz, process

from aprendiz import addons as pacotes
from aprendiz.algoritmos import BUSCAS, RESPOSTAS, ContextoBusca, titulo_curto
from aprendiz.algoritmos.base import Candidato
from aprendiz.algoritmos.resposta.trabalhada import resumo
from aprendiz.configuracoes import Configuracoes
from aprendiz.core.compreensao import Compreensao, FRASE_TIPO, resposta_dinamica
from aprendiz.core.dialogo import SO_SEM_ASSUNTO, Dialogo
from aprendiz.core.dicionario import Dicionario
from aprendiz.core import revisao

from aprendiz.core.expressao import Expressao
from aprendiz.core.padroes import Padroes
from aprendiz.core.teia import Teia
from aprendiz.memoria.banco import lista_json, teia_de
from aprendiz.linguagem import ClassificadorIntencoes, Linguagem, extrair_entidades
from aprendiz.linguagem.normalizador import VERSAO_NORMALIZACAO, normalizar
from aprendiz.linguagem.stemmer import radical
from aprendiz.memoria import Banco

# ---------------------------------------------------------------------------
# Padrões de ensino explícito. Usamos regex (e não só o classificador) porque
# aqui precisamos EXTRAIR as partes da frase, não apenas reconhecer a intenção.
# ---------------------------------------------------------------------------
_VERBOS_ENSINO = r"(?:aprenda|aprende|memorize|memoriza|lembre(?:-se)?|anote|guarde|grave|registre)"

# "pergunta: horário da farmácia resposta: 8h às 20h"
PADRAO_PAR = re.compile(r"^\s*pergunta\s*:\s*(?P<p>.+?)\s*resposta\s*:\s*(?P<r>.+)$",
                        re.I | re.S)

# "aprenda que a senha do wifi é casa123"
PADRAO_FATO = re.compile(
    rf"^\s*{_VERBOS_ENSINO}\s+(?:que\s+)?(?P<p>.+?)\s+(?P<v>é|são|fica|ficam|custa|custam|abre|abrem)\s+(?P<r>.+?)\s*[.!]?\s*$",
    re.I | re.S,
)

# "anote: levar o carro na revisão em março"
PADRAO_NOTA = re.compile(rf"^\s*{_VERBOS_ENSINO}\s*(?:que|isso|:)?\s*:?\s*(?P<n>.+)$",
                         re.I | re.S)

INTENCOES_SOCIAIS = {"saudacao", "despedida", "agradecimento", "ajuda"}
PROBABILIDADE_MINIMA_SOCIAL = 0.45
MARGEM_MINIMA_SOCIAL = 2.0  # a 1ª intenção precisa ser 2x mais provável que a 2ª
MAX_TOKENS_SOCIAL = 6  # frases longas provavelmente são perguntas de verdade

MSG_NAO_SEI = (
    "Ainda não fui ensinado sobre isso. Você pode me ensinar clicando em "
    "**Ensinar isso** logo abaixo, ou escrevendo algo como "
    "`aprenda que ... é ...`."
)
# Pedido composto (1.0): "qual a senha do wifi e o horário da farmácia?". A mensagem
# é dividida em "?", ";" ou num " e " seguido de artigo ou palavra de pergunta.
_DIVISOR_COMPOSTO = re.compile(
    r"\s*[?;]\s+|\s+e\s+(?=(?:o|a|os|as|qual|quais|quando|onde|como|quanto|quantos|quantas|"
    r"quem|que|do|da|dos|das)\b)", re.IGNORECASE)
_PARTE_PERGUNTA = re.compile(
    r"^(?:o que|por que|qual|quais|quando|onde|como|quanto|quantos|quantas|quem)\b", re.IGNORECASE)
MAX_PARTES_COMPOSTO = 4
MAX_ITENS_PANORAMA = 6
PALAVRAS_COMUNS_ASSUNTO = 300  # "quero FAZER um bolo": as N mais comuns saem do assunto
MAX_ELOS_VERBETE = 5     # no dicionário: até 5 equivalências (e 5 falsos amigos) por resposta
FOLGA_MELHOR_ASSUNTO = 0.6  # o único que bate MAIS que todos no assunto: até 60% do limiar
COBERTURA = 0.5        # cada palavra da pergunta coberta pelo assunto declarado soma isto
FOLGA_ASSUNTO = 0.8   # quem bate no assunto declarado é aceito até 80% do limiar
MAX_PROFUNDIDADE = 2  # o diálogo pode reprocessar a mensagem (resto, continuação)

MSG_SEM_NORMA = (
    "Para revisar textos, preciso de um addon de **norma** ativo: os addons de português "
    "de cada país (Brasil, Portugal, Angola, Moçambique, Cabo Verde, Guiné-Bissau, São Tomé "
    "e Príncipe e Timor-Leste) trazem o vocabulário e as regras de gramática. Eles estão "
    "na loja oficial."
)
MSG_FORMATO_ENSINO = (
    "Entendi que você quer me ensinar algo, mas não consegui separar a "
    "informação. Tente um destes formatos:\n\n"
    "- `aprenda que a senha do wifi é casa123`\n"
    "- `pergunta: horário da farmácia resposta: 8h às 20h`\n"
    "- `anote: levar o carro na revisão em março`"
)


def _capitalizar(texto: str) -> str:
    return texto[:1].upper() + texto[1:] if texto else texto


class Etapas:
    """Pequeno cronômetro que registra cada etapa do pipeline."""

    def __init__(self) -> None:
        self.lista: list[dict[str, Any]] = []
        self.meta: dict[str, Any] = {}  # dados extras da resposta (ex.: recomendação)
        self._inicio_total = time.perf_counter()
        self._inicio = self._inicio_total

    def marcar(self, nome: str, dados: dict[str, Any]) -> None:
        agora = time.perf_counter()
        self.lista.append({"nome": nome, "ms": round((agora - self._inicio) * 1000, 2),
                           "dados": dados})
        self._inicio = agora

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self._inicio_total) * 1000, 2)


def _parecida(palavra: str, palavras: set[str], digitacao: bool = True) -> bool:
    """`palavra` aparece em `palavras`, com folga para flexão (mesmo começo) ou digitação."""
    # Começo comum, com folga para flexão ("índices" → "índice"); em palavra de
    # 5 letras, a folga de 2 juntava palavras diferentes ("valeu" e "vale").
    raiz = palavra[:max(5, len(palavra) - 2)] if len(palavra) >= 5 else palavra
    if any(p.startswith(raiz) for p in palavras):
        return True
    # Gerúndio → infinitivo ("dividindo" → "dividir", "ordenando" → "ordenar").
    # Só essa flexão exata: juntar por radical misturaria "ligações" e "ligada".
    for fim, troca in (("ando", "ar"), ("endo", "er"), ("indo", "ir")):
        if palavra.endswith(fim) and len(palavra) > len(fim) + 2:
            if palavra[: -len(fim)] + troca in palavras:
                return True
    if not digitacao:
        return False
    perto = [p for p in palavras if abs(len(p) - len(palavra)) <= 2 and len(p) >= 3]
    return process.extractOne(palavra, perto, scorer=fuzz.ratio, score_cutoff=85) is not None


def texto_indexado(pergunta: str | None, conteudo: str, variacoes: list[str] | None = None) -> str:
    """O texto que vira índice de busca: pergunta + variações + conteúdo."""
    return " ".join([pergunta or "", *(variacoes or []), conteudo])


class Assistente:
    def __init__(self, banco: Banco) -> None:
        self.banco = banco
        self.linguagem = Linguagem(banco)
        self.contexto = ContextoBusca(banco=banco, linguagem=self.linguagem)
        self.teia = Teia(banco, self.linguagem)
        self.padroes = Padroes(banco)
        self._assunto_definicao: set[str] = set()
        self._raras: dict[str, float] = {}
        self._raras_versao = -1
        self._df, self._df_total, self._df_versao = {}, 0, -1   # palavras do assunto de um "o que é X?"
        self.contexto.expressao = Expressao(banco)
        self.configuracoes = Configuracoes(banco)
        self.dicionario = Dicionario(banco, self.linguagem)
        self.compreensao = Compreensao(banco, self.linguagem)
        self.dialogo = Dialogo(banco, self.linguagem)
        self.revisor = revisao.Revisor(banco, self.linguagem.lexico)
        self.classificador = ClassificadorIntencoes()
        self._versao_classificador = -1
        self._frases_exatas: dict[str, str] = {}  # frase normalizada → intenção

        # Se as regras de normalização mudaram desde a última vez que este
        # banco foi aberto (atualização do app), refaz os textos de busca.
        self._garantir_indice()

    def _assinatura_indice(self) -> str:
        """
        O que define como os textos de busca foram calculados: as regras de
        normalização e os addons de compreensão ativos (lemas e expressões
        mudam os radicais). Se a assinatura muda, a base é reindexada.
        """
        recursos = sorted(f"{a['id']}@{a['versao']}" for a in self.banco.listar_addons()
                          if a["ativo"] and a["total_recursos"])
        return "|".join([str(VERSAO_NORMALIZACAO), *recursos])

    def _garantir_indice(self, forcar: bool = False) -> None:
        if forcar or self.banco.obter_meta("assinatura_indice") != self._assinatura_indice():
            self.reindexar()

    # ================================================================ ENSINO
    def ensinar(self, conteudo: str, pergunta: str | None = None,
                tipo: str | None = None, origem: str = "manual",
                id: str | None = None) -> dict[str, Any]:
        """Grava um conhecimento já calculando seu texto de busca (radicais)."""
        conteudo = conteudo.strip()
        pergunta = (pergunta or "").strip() or None
        if not conteudo:
            raise ValueError("O conteúdo não pode ficar vazio.")
        tipo = tipo or ("pergunta" if pergunta else "nota")
        texto = f"{pergunta or ''} {conteudo}"
        texto_busca = self.linguagem.processar(texto, corrigir=False).texto_busca
        return self.banco.salvar_conhecimento(
            conteudo=conteudo, tipo=tipo, pergunta=pergunta, origem=origem,
            texto_busca=texto_busca, id=id,
        )

    def importar_texto(self, nome_arquivo: str, texto: str,
                       tamanho_maximo: int = 800) -> int:
        """Divide um arquivo de texto em trechos (por parágrafo) e ensina cada um."""
        trechos = pacotes.dividir_em_trechos(texto, tamanho_maximo)
        for trecho in trechos:
            self.ensinar(trecho, tipo="trecho", origem=f"arquivo:{nome_arquivo}")
        return len(trechos)

    def reindexar(self) -> int:
        """
        Recalcula o texto de busca de toda a base (inclusive de addons).
        Necessário quando sinônimos ou abreviações mudam, porque eles alteram
        os radicais gravados. Tudo é gravado numa única transação.
        """
        docs = self.banco.todos_conhecimentos()
        self.banco.atualizar_textos_busca([
            (doc["id"], self.linguagem.processar(
                texto_indexado(doc["pergunta"], doc["conteudo"],
                               lista_json(doc, "variacoes") + ((teia_de(doc) or {}).get("assuntos") or [])),
                corrigir=False).texto_busca)
            for doc in docs
        ])
        self.banco.definir_meta("assinatura_indice", self._assinatura_indice())
        return len(docs)

    # ================================================================ ADDONS
    def inspecionar_addon(self, dados: bytes) -> dict[str, Any]:
        """
        Lê e valida um .aprendiz SEM instalar: é o que a tela de confirmação
        mostra (origem, classificação, totais, dependências, versão do app).
        """
        pacote = pacotes.ler_pacote(dados)  # lança ErroAddon se for inválido
        instalados = {a["id"]: a for a in self.banco.listar_addons()}
        dependencias = []
        for dep in pacote.manifesto["dependencias"]:
            atual = instalados.get(dep["id"])
            if not atual:
                situacao = "ausente"
            elif pacotes.comparar_versoes(atual["versao"], dep["versao"]) < 0:
                situacao = "desatualizado"
            elif not atual["ativo"]:
                situacao = "desativado"
            else:
                situacao = "instalado"
            dependencias.append({**dep, "situacao": situacao,
                                 "versao_instalada": atual["versao"] if atual else None})
        # Configurações que o dono já definiu continuam valendo (dono > addon).
        do_dono = {k for k, v in self.configuracoes.efetivas().items() if v["origem"] == "dono"}
        resumo = pacotes.resumo(pacote)
        for item in resumo["configuracoes"]:
            item["dono_ja_definiu"] = item["chave"] in do_dono
        anterior = instalados.get(pacote.manifesto["id"])

        # Recomendação de algoritmos e o GRUPO de addons que pedem o mesmo padrão.
        chave = (pacotes.chave_de_grupo(pacote.manifesto, pacote.parametros)
                 or self._chaves_de_grupo(pacote.manifesto)[pacote.manifesto["id"]][0])
        grupo = next((g for g in self.grupos_de_addons() if g["chave"] == chave), None)
        rec = pacote.manifesto.get("recomendado")
        if rec:
            config = self.configuracoes.efetivas()
            em_uso = (config["busca.padrao"]["valor"], config["resposta.padrao"]["valor"])
            ativos_outro_padrao = [
                g["titulo"] for g in self.grupos_de_addons()
                if g["chave"] != chave and any(a["ativo"] for a in g["addons"])]
            resumo["recomendado"] = {
                **rec,
                "titulo_busca": self._titulo_algoritmo(BUSCAS, rec["busca"]),
                "titulo_resposta": self._titulo_algoritmo(RESPOSTAS, rec["resposta"]),
                "disponivel": rec["busca"] in BUSCAS and rec["resposta"] in RESPOSTAS,
                "ja_em_uso": em_uso == (rec["busca"], rec["resposta"]),
                "outros_padroes_ativos": ativos_outro_padrao,
            }
        else:
            resumo["recomendado"] = None
        resumo["grupo"] = {
            "chave": chave,
            "titulo": grupo["titulo"] if grupo else None,
            "inativos": [{"id": a["id"], "nome": a["nome"]} for a in (grupo["addons"] if grupo else [])
                         if not a["ativo"] and a["id"] != pacote.manifesto["id"]],
            "ativos": sum(1 for a in (grupo["addons"] if grupo else [])
                          if a["ativo"] and a["id"] != pacote.manifesto["id"]),
        } if chave else None
        return {**resumo, "dependencias": dependencias,
                "versao_anterior": anterior["versao"] if anterior else None}

    def instalar_addon(self, dados: bytes) -> dict[str, Any]:
        """
        Lê, valida e instala um arquivo .aprendiz. Se um addon com o mesmo id
        já estiver instalado, ele é substituído (atualização).
        Devolve o addon instalado e, se for o caso, a versão anterior.
        """
        pacote = pacotes.ler_pacote(dados)  # lança ErroAddon se for inválido
        anterior = self.banco.obter_addon(pacote.manifesto["id"])

        conhecimentos = [
            {**k, "texto_busca": self.linguagem.processar(
                texto_indexado(k["pergunta"], k["conteudo"],
                               (k.get("variacoes") or []) + (k.get("teia") or {}).get("assuntos", [])),
                corrigir=False).texto_busca}
            for k in pacote.conhecimentos
        ]
        self.banco.instalar_addon(
            pacote.manifesto, conhecimentos, pacote.linguagem, pacote.hash,
            pacote.configuracoes,
            {"compreensao": pacote.compreensao, "lemas": pacote.lemas,
             "vetores": pacote.vetores, "norma": pacote.norma,
             "vocabulario": pacote.vocabulario})

        # Sinônimos/abreviações novos (ou removidos na atualização) mudam os
        # radicais de TODA a base, não só os do addon. Lemas e expressões de
        # um addon de compreensão também (a assinatura do índice detecta).
        self._garantir_indice(
            forcar=bool(pacote.linguagem or (anterior and anterior["total_linguagem"])))

        return {
            "addon": self.banco.obter_addon(pacote.manifesto["id"]),
            "versao_anterior": anterior["versao"] if anterior else None,
        }

    @staticmethod
    def _titulo_algoritmo(registro: dict, nome: str) -> str:
        return titulo_curto(registro, nome)

    def _chaves_de_grupo(self, extra: dict[str, Any] | None = None) -> dict[str, tuple[str | None, bool]]:
        """
        id → (chave do grupo, herdada?) de cada addon instalado (e de `extra`,
        o manifesto de um addon que ainda vai ser instalado).

        A chave PRÓPRIA vem da recomendação do addon (addons.chave_de_grupo).
        Addons de apoio não têm recomendação: compreensão, diálogo e vetores
        não trazem conhecimentos para testar, e personalização só muda a
        aparência. Eles HERDAM o grupo dos addons relacionados:

            1. os de que dependem e os que declaram em "complementa";
            2. se nenhum desses tiver grupo, os que dependem DELES.

        Vale a chave mais comum entre os relacionados. A herança se propaga:
        Vetores depende de Compreensão, que complementa os addons de
        português → os três ficam no grupo do português. Sem nenhum
        relacionado com grupo, o addon continua sem grupo (ex.: temas).
        """
        manifestos = {a["id"]: (a["manifesto"] or {}, self.banco.configuracoes_do_addon(a["id"]))
                      for a in self.banco.listar_addons()}
        if extra:
            manifestos[extra["id"]] = (extra, {})
        chaves = {i: pacotes.chave_de_grupo(m, p) for i, (m, p) in manifestos.items()}
        herdadas: set[str] = set()
        relacionados = {i: [r for r in pacotes.relacionados_do_grupo(m) if r in manifestos]
                        for i, (m, _) in manifestos.items()}
        dependentes: dict[str, list[str]] = {i: [] for i in manifestos}
        for i, rels in relacionados.items():
            for r in rels:
                dependentes[r].append(i)

        def mais_comum(ids: list[str]) -> str | None:
            contagem: dict[str, int] = {}
            for r in ids:
                if chaves.get(r):
                    contagem[chaves[r]] = contagem.get(chaves[r], 0) + 1
            return max(contagem, key=lambda c: (contagem[c], c)) if contagem else None

        mudou = True
        while mudou:  # cada volta resolve mais um "elo" (vetores → compreensão → português)
            mudou = False
            for i in manifestos:
                if chaves[i]:
                    continue
                chave = mais_comum(relacionados[i]) or mais_comum(dependentes[i])
                if chave:
                    chaves[i] = chave
                    herdadas.add(i)
                    mudou = True
        return {i: (chaves[i], i in herdadas) for i in manifestos}

    def grupos_de_addons(self) -> list[dict[str, Any]]:
        """
        Addons instalados agrupados pelo padrão de busca e resposta que pedem
        (ver _chaves_de_grupo). Addons sem grupo próprio nem herdado ficam
        num grupo à parte, com chave None. Cada grupo diz se o padrão dele
        está em uso.
        """
        config = self.configuracoes.efetivas()
        em_uso = f"{config['busca.padrao']['valor']}+{config['resposta.padrao']['valor']}"
        chaves = self._chaves_de_grupo()
        grupos: dict[str | None, dict[str, Any]] = {}
        for a in self.banco.listar_addons():
            chave, herdada = chaves[a["id"]]
            if chave not in grupos:
                busca, _, resposta = (chave or "+").partition("+")
                grupos[chave] = {
                    "chave": chave, "busca": busca or None, "resposta": resposta or None,
                    "titulo": (f"{self._titulo_algoritmo(BUSCAS, busca)} · "
                               f"{self._titulo_algoritmo(RESPOSTAS, resposta)}"
                               if chave else "Sem recomendação"),
                    "em_uso": chave == em_uso,
                    "addons": [],
                }
            grupos[chave]["addons"].append(
                {"id": a["id"], "nome": a["nome"], "ativo": bool(a["ativo"]), "apoio": herdada})
        # Grupos com recomendação primeiro (o em uso no topo); "sem recomendação" por último.
        return sorted(grupos.values(),
                      key=lambda g: (g["chave"] is None, not g["em_uso"], g["titulo"]))

    def definir_addons_ativos(self, ids: list[str], ativo: bool) -> int:
        """Ativa ou desativa vários addons de uma vez (reindexa uma vez só)."""
        existentes = {a["id"]: a for a in self.banco.listar_addons()}
        alterados = [i for i in ids if i in existentes and bool(existentes[i]["ativo"]) != ativo]
        for addon_id in alterados:
            self.banco.definir_addon_ativo(addon_id, ativo)
        self._garantir_indice(forcar=any(existentes[i]["total_linguagem"] for i in alterados))
        return len(alterados)

    def usar_padrao(self, busca: str, resposta: str) -> None:
        """Define (como escolha do dono) os algoritmos padrão de busca e resposta."""
        self.configuracoes.definir("busca.padrao", busca)
        self.configuracoes.definir("resposta.padrao", resposta)

    def definir_addon_ativo(self, addon_id: str, ativo: bool) -> dict[str, Any]:
        addon = self.banco.obter_addon(addon_id)
        if not addon:
            raise ValueError("Addon não encontrado.")
        self.banco.definir_addon_ativo(addon_id, ativo)
        self._garantir_indice(forcar=bool(addon["total_linguagem"]))
        return self.banco.obter_addon(addon_id)

    def remover_addon(self, addon_id: str) -> bool:
        addon = self.banco.obter_addon(addon_id)
        if not addon:
            return False
        self.banco.remover_addon(addon_id)
        self._garantir_indice(forcar=bool(addon["total_linguagem"]))
        return True

    def _ensino_explicito(self, mensagem: str) -> dict[str, Any] | None:
        """Reconhece frases de ensino e grava o conhecimento."""
        m = PADRAO_PAR.match(mensagem)
        if m:
            c = self.ensinar(m["r"], pergunta=m["p"], origem="chat")
            return {"conhecimento": c, "formato": "pergunta/resposta"}

        m = PADRAO_FATO.match(mensagem)
        if m:
            sujeito = m["p"].strip()
            conteudo = f"{_capitalizar(sujeito)} {m['v'].lower()} {m['r'].strip()}."
            c = self.ensinar(conteudo, pergunta=sujeito, origem="chat")
            return {"conhecimento": c, "formato": "fato"}

        m = PADRAO_NOTA.match(mensagem)
        if m and len(m["n"].split()) >= 2:
            c = self.ensinar(_capitalizar(m["n"].strip()), tipo="nota", origem="chat")
            return {"conhecimento": c, "formato": "nota"}
        return None

    # ================================================================ INTENÇÕES
    def _treinar_classificador(self) -> None:
        """(Re)treina o Naive Bayes quando o banco de linguagem muda."""
        if self._versao_classificador == self.banco.versao_linguagem:
            return
        exemplos = []
        self._frases_exatas = {}
        for e in self.banco.exemplos_intencoes(incluir_addons=True):
            processado = self.linguagem.processar(e["frase"], corrigir=False)
            exemplos.append((e["intencao"], processado.radicais_todos))
            self._frases_exatas[" ".join(processado.tokens)] = e["intencao"]
        self.classificador.treinar(exemplos)
        self._versao_classificador = self.banco.versao_linguagem

    # ================================================================ CONVERSA
    def responder(self, mensagem: str, conversa_id: str | None = None,
                  busca: str | None = None, resposta: str | None = None) -> dict[str, Any]:
        mensagem = mensagem.strip()
        if not mensagem:
            raise ValueError("Mensagem vazia.")
        # Sem escolha explícita, valem os algoritmos padrão das Configurações.
        busca = busca or self.configuracoes.valor("busca.padrao")
        resposta = resposta or self.configuracoes.valor("resposta.padrao")
        if busca not in BUSCAS:
            raise ValueError(f"Algoritmo de busca desconhecido: {busca}")
        if resposta not in RESPOSTAS:
            raise ValueError(f"Algoritmo de resposta desconhecido: {resposta}")

        # Conversa: cria uma nova se não vier id (ou se o id não existir).
        if not conversa_id or not self.banco.obter_conversa(conversa_id):
            titulo = mensagem[:48] + ("…" if len(mensagem) > 48 else "")
            conversa_id = self.banco.criar_conversa(titulo)["id"]
        contexto = self._contexto(conversa_id)
        msg_usuario = self.banco.adicionar_mensagem(conversa_id, "usuario", mensagem)

        etapas = Etapas()
        texto_resposta, tipo, fontes = self._pipeline(mensagem, busca, resposta, etapas,
                                                      contexto)

        meta = {
            "tipo": tipo,
            "pergunta": mensagem,
            "fontes": fontes,
            **etapas.meta,
            "explicacao": {
                "etapas": etapas.lista,
                "algoritmo_busca": busca,
                "algoritmo_resposta": resposta,
                "total_ms": etapas.total_ms,
            },
        }
        msg_assistente = self.banco.adicionar_mensagem(conversa_id, "assistente",
                                                       texto_resposta, meta)
        return {
            "conversa_id": conversa_id,
            "mensagem_usuario": msg_usuario,
            "mensagem": msg_assistente,
        }

    def _contexto(self, conversa_id: str) -> dict[str, Any]:
        """
        A última troca da conversa: a pergunta da pessoa e a resposta (com o
        meta: tipo, fontes, candidatos da busca, recomendação). É o que o
        diálogo usa para "não entendi", "não era isso", "sim" e "e em...?".
        """
        anterior: dict[str, Any] = {"pergunta": None, "resposta": None}
        for m in reversed(self.banco.listar_mensagens(conversa_id)[-6:]):
            if m["papel"] == "assistente" and anterior["resposta"] is None:
                anterior["resposta"] = m
            elif m["papel"] == "usuario" and anterior["resposta"] is not None:
                # A pergunta "de verdade" é a que a resposta tratou (uma
                # continuação já reescrita fica no meta da resposta).
                meta = anterior["resposta"].get("meta") or {}
                anterior["pergunta"] = meta.get("entendida") or m["texto"]
                break
        return anterior

    def _pipeline(self, mensagem: str, busca: str, resposta: str, etapas: Etapas,
                  contexto: dict[str, Any] | None = None,
                  profundidade: int = 0) -> tuple[str, str, list[dict]]:
        """Executa as etapas e devolve (texto, tipo, fontes)."""
        contexto = contexto or {"pergunta": None, "resposta": None}
        # 1. Normalização ----------------------------------------------------
        consulta = self.linguagem.processar(mensagem)
        etapas.marcar("Normalização", consulta.como_dict())

        # 2. Ensino explícito -------------------------------------------------
        ensino = self._ensino_explicito(mensagem)
        if ensino:
            c = ensino["conhecimento"]
            etapas.marcar("Ensino", {"formato": ensino["formato"], "id": c["id"]})
            if c["pergunta"]:
                texto = f"Aprendi! Quando perguntarem sobre **{c['pergunta']}**, vou responder:\n\n{c['conteudo']}"
            else:
                texto = f"Anotado! Guardei esta informação:\n\n{c['conteudo']}"
            return texto, "ensino", [self._fonte(c)]

        # 2a. Revisão de texto (addon de norma) ------------------------------
        # "revise: ...", "o certo é exceção ou excessão?", "como se escreve
        # económico no Brasil?". Pedidos com "revise:" são sempre atendidos;
        # as perguntas curtas cedem a vez ao que o dono ensinou.
        pedido_revisao = revisao.interpretar(mensagem)
        if pedido_revisao:
            respondido = self._revisao(pedido_revisao, consulta, etapas)
            if respondido:
                return respondido

        # 2b. Dicionário ------------------------------------------------------
        # "como se diz aldeia em Guiné?", "o que é kota em Angola?"... Vem
        # antes das intenções porque "como se diz obrigado em Timor" não é um
        # agradecimento. Se o dono ensinou exatamente essa pergunta, vale a dele.
        pedido = self.dicionario.interpretar(mensagem)
        if pedido:
            resposta_dic = self.dicionario.responder(pedido)
            etapas.marcar("Dicionário", {**pedido.como_dict(), "encontrou": bool(resposta_dic)})
            if resposta_dic and not self._dono_ensinou_exatamente(consulta):
                texto, verbetes = resposta_dic
                texto, ligados = self._teia_dos_verbetes(texto, verbetes, consulta, resposta)
                return texto, "conhecimento", [self._fonte(v) for v in [*verbetes, *ligados]]

        # 2c. Diálogo (addon de diálogo) -------------------------------------
        # O QUE a pessoa faz com a frase: cumprimenta e pede algo, desabafa,
        # pede opinião, reage à resposta anterior, continua a pergunta.
        leitura = None
        if self.dialogo.ativo and profundidade < MAX_PROFUNDIDADE:
            respondido, leitura = self._dialogo(mensagem, consulta, busca, resposta, etapas,
                                                contexto, profundidade)
            if respondido:
                return respondido

        # 3. Interpretação ----------------------------------------------------
        self._treinar_classificador()
        # Atalho: se a mensagem é IGUAL a uma frase de exemplo, não há dúvida.
        exata = self._frases_exatas.get(" ".join(consulta.tokens))
        if exata:
            intencoes = [{"intencao": exata, "probabilidade": 1.0, "exata": True}]
        else:
            intencoes = self.classificador.classificar(consulta.radicais_todos)
        entidades = extrair_entidades(mensagem)
        etapas.marcar("Interpretação", {"intencoes": intencoes[:4], "entidades": entidades})

        principal = intencoes[0] if intencoes else {"intencao": "desconhecida", "probabilidade": 0}

        # 4. Intenções sociais -----------------------------------------------
        # Só responde socialmente se a mensagem for curta e a intenção for
        # clara: probabilidade alta E bem à frente da segunda colocada.
        # Conta as palavras ESCRITAS (antes de expressões virarem uma palavra só).
        curta = len(consulta.normalizado.split()) <= MAX_TOKENS_SOCIAL
        segunda = intencoes[1]["probabilidade"] if len(intencoes) > 1 else 0.0
        clara = (principal["probabilidade"] >= PROBABILIDADE_MINIMA_SOCIAL
                 and principal["probabilidade"] >= MARGEM_MINIMA_SOCIAL * segunda)
        # Com o addon de compreensão: uma frase que COMEÇA como pergunta ("como
        # selecionar tudo no windows") e tem assunto não é cumprimento, mesmo
        # que o classificador ache ("tudo" lembra "tudo bem").
        analise = self.compreensao.analisar(consulta, mensagem) if self.compreensao.ativa else None
        self._assunto_definicao = (set(normalizar(analise.assunto).split())
                                   if analise and analise.tipo == "definicao" and analise.assunto
                                   else set())
        if analise and analise.tipo and analise.tipo != "pedido" and not principal.get("exata"):
            assunto = [t for t in consulta.tokens[analise.inicio_assunto:]
                       if t not in self.linguagem.stopwords]
            if len(assunto) >= 2:
                clara = False
        if analise and analise.necessidades:  # "tô com fome" pede algo, não cumprimenta
            clara = False
        # Pergunta sobre o próprio Aprendiz não é cumprimento ("como você se chama?").
        if clara and analise is not None and self.compreensao.autoconhecimento(consulta):
            clara = False
        # Assunto que a base conhece não é conversa social: "me fala de banco
        # de dados" pede o banco de dados, mesmo que o classificador ache que é
        # um pedido de ajuda. Vale para qualquer jeito de pedir, não só para os
        # gatilhos da compreensão.
        if principal["intencao"] in INTENCOES_SOCIAIS and curta and clara \
                and len(consulta.conteudo) >= 2 and any(
                    self._bate_no_assunto(consulta, c.conhecimento)
                    for c in self.buscar(consulta, busca)[1]):
            clara = False
            etapas.marcar("Assunto conhecido", {"palavras": ", ".join(consulta.conteudo),
                                                "intencao ignorada": principal["intencao"]})
        if principal["intencao"] in INTENCOES_SOCIAIS and curta and clara:
            texto = self.banco.resposta_padrao(principal["intencao"]) or "Certo!"
            etapas.marcar("Resposta social", {"intencao": principal["intencao"]})
            return texto, "social", []

        if principal["intencao"] == "ensinar" and principal["probabilidade"] >= 0.6:
            etapas.marcar("Resposta social", {"intencao": "ensinar (formato não reconhecido)"})
            return MSG_FORMATO_ENSINO, "social", []

        # 4b. Compreensão (addon de compreensão) ------------------------------
        if analise is not None:
            sobre_mim = self.compreensao.autoconhecimento(consulta)
            dados = analise.como_dict()
            if sobre_mim:
                dados["sobre o Aprendiz"] = f"{sobre_mim['id']} ({sobre_mim['semelhanca']}%)"
            etapas.marcar("Compreensão", dados)
            if sobre_mim and not self._dono_ensinou_exatamente(consulta):
                texto = (resposta_dinamica(sobre_mim["funcao"], self)
                         if sobre_mim.get("funcao") else sobre_mim["resposta"])
                etapas.marcar("Resposta · Autoconhecimento", {"item": sobre_mim["id"]})
                return texto, "autoconhecimento", []

        # 4c. Sem assunto (addon de diálogo) --------------------------------
        # "consegue fazer isso?", "me explica?": só palavras de conversa. Buscar
        # "fazer" ou "explicar" na base só traria respostas sem relação.
        if leitura is not None and not self.dialogo.assunto_real(consulta.tokens) \
                and not self._dono_ensinou_exatamente(consulta):
            texto = self.dialogo.sem_assunto(mensagem)
            if texto:
                etapas.marcar("Diálogo · sem assunto", {"palavras": ", ".join(consulta.tokens)})
                return texto, "dialogo", []

        # 4d. Padrões de frase (2.0) -------------------------------------------
        # "quantos pedidos cada cliente fez" → agrupar e contar; "pedidos" e
        # "cliente" são o exemplo, não o assunto (core/padroes.py). Só troca a
        # pergunta se a reescrita achar resposta.
        frase = self.padroes.ler(consulta.normalizado)
        if frase is not None:
            reescrita = self.linguagem.processar(frase.texto)
            _, achou, _ = self.buscar(reescrita, busca)
            etapas.marcar("Padrão de frase", {**frase.como_dict(), "encontrou": len(achou)})
            if achou:
                consulta = reescrita

        # 5. Busca -------------------------------------------------------------
        algoritmo_busca = BUSCAS[busca]
        candidatos, aceitos, limiar = self.buscar(consulta, busca)
        etapas.marcar(f"Busca · {algoritmo_busca.titulo}", {
            "limiar": limiar,
            "candidatos": [
                {"id": c.id, "titulo": self._titulo(c.conhecimento),
                 "confianca": c.confianca, "pontuacao": c.pontuacao,
                 "aceito": c.confianca >= limiar, "detalhes": c.detalhes}
                for c in candidatos
            ],
        })

        # 5b. Juntar e reinterpretar (1.0) ------------------------------------
        # "o que você sabe sobre o carro?" → tudo sobre carro, numa lista;
        # "qual a senha do wifi e o horário da farmácia?" → as duas respostas;
        # "quero fazer um bolo" → procura só o assunto ("bolo").
        if analise is not None and analise.tipo == "panorama" and analise.assunto:
            junto = self._panorama(analise.assunto, etapas)
            if junto:
                return junto
        composto = self._composto(mensagem, busca, etapas)
        if composto:
            return composto
        if not aceitos and analise is not None and analise.assunto:
            so_assunto = self._so_o_assunto(analise.assunto, enxugar=True)
            if so_assunto is not None and so_assunto.radicais != consulta.radicais:
                c2, a2, _ = self.buscar(so_assunto, busca)
                etapas.marcar("Busca · só o assunto", {
                    "assunto": " ".join(so_assunto.conteudo), "encontrou": len(a2)})
                if a2:
                    candidatos, aceitos, consulta = c2, a2, so_assunto

        # 6. Modo estrito -----------------------------------------------------
        nota_sentido = ""
        if not aceitos and analise is not None:
            # 6a. Pedido que um assistente offline não atende?
            limite = self.compreensao.fora_de_alcance(consulta)
            if limite:
                etapas.marcar("Fora de alcance", {"tema": limite["tema"]})
                return limite["resposta"], "limite", []
            # 6b. Busca por sentido: palavras de significado próximo (vetores).
            trocas = self.compreensao.expandir(consulta)
            if trocas:
                ampliada = self.linguagem.processar(
                    " ".join([consulta.normalizado, *(t["para"] for t in trocas)]), corrigir=False)
                candidatos2, aceitos2, _ = self.buscar(ampliada, busca)
                etapas.marcar("Busca por sentido", {
                    "trocas": [f"{t['de']} → {t['para']} ({t['semelhanca']})" for t in trocas],
                    "encontrou": len(aceitos2)})
                # A troca precisa levar ao ASSUNTO de um conhecimento, não a uma
                # palavra solta no texto ("ganhou" → "trouxe" achava SQL).
                novas = [t["para"] for t in trocas]
                aceitos2 = [c for c in aceitos2
                            if any(_parecida(n, self._assunto_declarado(c.conhecimento), False)
                                   for n in novas)]
                if aceitos2:
                    candidatos, aceitos, consulta = candidatos2, aceitos2, ampliada
                    usadas = {}
                    for t in trocas:
                        usadas.setdefault(t["de"], []).append(t["para"])
                    nota_sentido = ("*Não encontrei exatamente essas palavras; procurei pelo "
                                    "sentido (" + "; ".join(
                                        f"{de} → {', '.join(para)}" for de, para in usadas.items())
                                    + ").*\n\n")

        # Pergunta reflexiva ("qual o sentido da vida?"): só vale o que a base
        # traz se o conhecimento fala de TODAS as palavras do assunto ("sentido"
        # sozinho, numa regra de gramática, não responde ao sentido da vida).
        if aceitos and leitura and leitura.ato and leitura.ato["acao"] == "refletir" and not any(
                self.dialogo.cobre(self.dialogo.assunto_real(consulta.tokens),
                                   c.conhecimento.get("texto_busca") or "") for c in aceitos[:1]):
            aceitos = []
        if not aceitos and leitura and leitura.ato and leitura.ato["acao"] == "refletir":
            etapas.marcar("Diálogo · reflexão", {"ato": leitura.ato["id"]})
            return self.dialogo.texto(leitura.ato, mensagem, leitura.assunto), "dialogo", []

        if not aceitos:
            texto = MSG_NAO_SEI
            if analise and analise.tipo in FRASE_TIPO and analise.assunto:
                texto = (f"Entendi que você quer saber {FRASE_TIPO[analise.tipo]} "
                         f"**{analise.assunto}**, mas ainda não fui ensinado sobre isso. "
                         + MSG_NAO_SEI.split(". ", 1)[1])
            # Só sugere o que tem pelo menos uma palavra em comum com a pergunta:
            # "o que é um animal?" não deve sugerir "me empresta ou empresta-me".
            parecidos = [c for c in candidatos
                         if set(consulta.radicais)
                         & set((c.conhecimento.get("texto_busca") or "").split())
                         and self._cobre_palavra_forte(consulta, c)]
            if parecidos:
                sugestoes = "\n".join(f"- {self._titulo(c.conhecimento)}" for c in parecidos[:3])
                texto += f"\n\nTalvez você esteja procurando algo parecido com:\n{sugestoes}"
            # 6c. Algum addon da loja oficial trata disso?
            rec = self.compreensao.recomendar(consulta, analise) if analise is not None else None
            if rec:
                if rec["acao"] == "ativar":
                    texto += (f"\n\nVocê tem o addon **{rec['nome']}** instalado, mas ele está "
                              "desativado. Ele deve saber responder isso: quer ativá-lo?")
                else:
                    texto += (f"\n\nNa loja oficial há um addon que trata disso: "
                              f"**{rec['nome']}** — {rec['descricao']}")
                etapas.meta["recomendacao"] = rec
                etapas.marcar("Recomendação de addon", {
                    "addon": rec["nome"], "ação": rec["acao"],
                    "palavras": ", ".join(rec["motivo"]) or "—", "pontuação": rec["pontuacao"]})
            etapas.marcar("Modo estrito", {"motivo": "nenhum candidato acima do limiar"})
            return texto, "desconhecido", []

        # 7. Resposta ----------------------------------------------------------
        # Dicionário: se a pergunta é exatamente uma palavra com verbete, a
        # resposta junta TODOS os verbetes dessa palavra (ex.: "bué" em
        # Portugal e em Angola), um por parágrafo.
        verbetes = [c for c in aceitos if c.detalhes.get("verbete") == "palavra exata"]
        if verbetes and aceitos[0] in verbetes:
            etapas.marcar("Resposta · Dicionário", {"verbetes": len(verbetes)})
            docs = [c.conhecimento for c in verbetes]
            texto, ligados = self._teia_dos_verbetes(
                "\n\n".join(d["conteudo"] for d in docs), docs, consulta, resposta)
            return (nota_sentido + texto, "conhecimento",
                    [self._fonte(d) for d in [*docs, *ligados]])

        # Teia de porquês (2.0): o caminho a partir do melhor candidato.
        self.contexto.caminho = self.teia.percorrer(aceitos[0].conhecimento, consulta.radicais)
        if self.contexto.caminho is not None:
            etapas.marcar("Teia de porquês", self.contexto.caminho.explicacao())

        algoritmo_resposta = RESPOSTAS[resposta]
        gerada = algoritmo_resposta.responder(consulta, aceitos, self.contexto)
        etapas.marcar(f"Resposta · {algoritmo_resposta.titulo}", gerada.detalhes)

        por_id = {c.id: c.conhecimento for c in aceitos}
        if self.contexto.caminho is not None:   # fragmentos ligados pela teia também são fontes
            por_id.update({p.para["id"]: p.para for p in self.contexto.caminho.passos if p.para})
        fontes = [self._fonte(por_id[i]) for i in gerada.fontes if i in por_id]
        return nota_sentido + gerada.texto, "conhecimento", fontes

    def _teia_dos_verbetes(self, texto: str, verbetes: list[dict], consulta,
                           resposta: str) -> tuple[str, list[dict]]:
        """
        Na resposta Trabalhada, o dicionário também segue a teia (2.0): a mesma
        ideia em outras variedades ("equivale") e a mesma palavra com outro
        sentido ("diferente-de"). Só os elos diretos (um verbete não tem cadeia
        de causas, tem vizinhos), e nada que já esteja na resposta ou que venha
        de um addon desativado.
        """
        if resposta != "trabalhada":
            return texto, []
        presentes = {v["id"] for v in verbetes}
        # Uma frase por verbete e relação, com os elos juntos. Com mais de um
        # sentido ("mina": moça no Brasil, filho em São Tomé), cada frase diz de qual.
        por_relacao: dict[tuple[int, str], list[str]] = {}
        ligados = []
        for i, doc in enumerate(verbetes):
            caminho = self.teia.percorrer(doc, consulta.radicais)
            for passo in (caminho.usados if caminho else []):
                if (passo.nivel != 1 or not passo.texto or passo.cortado == "fora"
                        or (passo.para is not None and passo.para["id"] in presentes)):
                    continue
                elos = por_relacao.setdefault((i, passo.relacao), [])
                if len(elos) >= MAX_ELOS_VERBETE:
                    continue
                elos.append(passo.texto)
                if passo.para is not None:
                    presentes.add(passo.para["id"])
                    ligados.append(passo.para)
        sentidos = [(lista_json(v, "traducoes") or [""])[0] for v in verbetes]
        varios = len(set(sentidos)) > 1
        frases = []
        for (i, relacao), elos in por_relacao.items():
            if varios and relacao == "equivale" and sentidos[i]:
                frases.append(f"No sentido de {sentidos[i]}: " + "; ".join(elos) + ".")
            else:
                frases.append(self.contexto.expressao.dizer(relacao, "; ".join(elos)))
        if not frases:
            return texto, []
        return texto + "\n\n" + " ".join(frases), ligados

    # ================================================================ JUNTAR (1.0)
    def _so_o_assunto(self, assunto: str, enxugar: bool = False):
        """
        O assunto processado. Com enxugar=True (e o addon de vetores), sem as
        palavras mais comuns da língua: "fazer um bolo" → "bolo".
        """
        proc = self.linguagem.processar(assunto)
        lexico = self.linguagem.lexico
        if enxugar and lexico.tem_vetores:
            fortes = [p for p in proc.conteudo if not lexico.frequente(p, PALAVRAS_COMUNS_ASSUNTO)]
            if fortes and len(fortes) < len(proc.conteudo):
                proc = self.linguagem.processar(" ".join(fortes))
        return proc if proc.radicais else None

    def _panorama(self, assunto: str, etapas: Etapas) -> tuple[str, str, list] | None:
        """
        Tudo o que a base sabe sobre um assunto, numa lista: os conhecimentos
        que têm TODAS as palavras do assunto. O que o dono ensinou vem primeiro.
        """
        # 1º o assunto inteiro ("acordo ortográfico"); se nada tiver TODAS as
        # palavras, o assunto enxuto ("o que tenho que fazer com o carro" → "carro").
        docs, proc = [], None
        for enxugar in (False, True):
            proc = self._so_o_assunto(assunto, enxugar)
            if proc is None:
                return None
            alvo = set(proc.radicais)
            for linha in self.banco.buscar_fts(" OR ".join(f'"{r}"' for r in alvo), 40):
                doc = self.banco.obter_conhecimento(linha["id"])
                if doc and doc.get("tipo") != "verbete" and alvo <= set(doc["texto_busca"].split()):
                    docs.append(doc)
            if docs:
                break
        docs.sort(key=lambda d: bool(d.get("addon_id")))  # do dono primeiro (sort estável)
        etapas.marcar("Panorama", {"assunto": " ".join(proc.conteudo), "encontrou": len(docs)})
        if not docs:
            return None
        mostrados = docs[:MAX_ITENS_PANORAMA]
        # Como a pessoa escreveu (com acentos), sem o artigo do começo.
        nome = re.sub(r"^(?:o|a|os|as|um|uma|uns|umas)\s+", "", assunto.strip(" ?!.,"), flags=re.I)
        cabeca = (f"Sobre **{nome}**, encontrei isto:" if len(mostrados) > 1
                  else f"Sobre **{nome}**, encontrei uma coisa:")
        itens = [f"- **{_capitalizar(d['pergunta'])}:** {d['conteudo']}" if d.get("pergunta")
                 else f"- {d['conteudo']}" for d in mostrados]
        resto = len(docs) - len(mostrados)
        rodape = f"\n\n*E mais {resto}. Pergunte algo mais específico para ver.*" if resto else ""
        return cabeca + "\n\n" + "\n".join(itens) + rodape, "conhecimento", [self._fonte(d) for d in mostrados]

    def _composto(self, mensagem: str, busca: str, etapas: Etapas) -> tuple[str, str, list] | None:
        """
        Várias perguntas numa mensagem só. Cada parte é buscada sozinha; se
        pelo menos duas acham respostas DIFERENTES, a resposta junta todas.
        Se só uma acha, mas outra parte é claramente uma PERGUNTA ("qual…",
        "quando…"), entrega o que existe e diz o que faltou.
        """
        partes = [p.strip(" ?!.,") for p in _DIVISOR_COMPOSTO.split(mensagem)]
        partes = [p for p in partes if p][:MAX_PARTES_COMPOSTO]
        if len(partes) < 2:
            return None
        achados, faltaram, vistos = [], [], set()
        for parte in partes:
            proc = self.linguagem.processar(parte)
            if not proc.conteudo:
                continue
            _, aceitos, _ = self.buscar(proc, busca)
            if aceitos and aceitos[0].id not in vistos:
                vistos.add(aceitos[0].id)
                achados.append((parte, aceitos[0].conhecimento))
            elif not aceitos and _PARTE_PERGUNTA.match(normalizar(parte)):
                faltaram.append(parte)
        if len(achados) < (1 if faltaram else 2):
            return None
        etapas.marcar("Pedido composto", {"partes": [p for p, _ in achados], "faltaram": faltaram})
        texto = "\n\n".join(f"**{_capitalizar(p)}?**\n{d['conteudo']}" for p, d in achados)
        if faltaram:
            texto += "\n\n*Ainda não fui ensinado sobre: " + "; ".join(faltaram) + ".*"
        return texto, "conhecimento", [self._fonte(d) for _, d in achados]

    # ================================================================ DIÁLOGO
    def _dialogo(self, mensagem: str, consulta, busca: str, resposta: str, etapas: Etapas,
                 contexto: dict[str, Any], profundidade: int):
        """
        Etapa de diálogo. Devolve ((texto, tipo, fontes) ou None, leitura).
        Quando a mensagem tem um cumprimento na frente ou é a continuação da
        pergunta anterior, o pipeline roda de novo com a mensagem tratada, e
        a resposta ganha o cumprimento na frente.
        """
        if self._dono_ensinou_exatamente(consulta):
            return None, None  # o que o dono ensinou vale mais
        leitura = self.dialogo.ler(mensagem, consulta.tokens)
        anterior = contexto.get("pergunta")
        tokens_resto = self.linguagem.processar(leitura.resto).tokens if leitura.abertura else consulta.tokens
        leitura.continuacao = self.dialogo.continuar(tokens_resto, leitura.resto, anterior,
                                                     self.compreensao)
        etapas.marcar("Diálogo", leitura.como_dict())

        def com_abertura(resultado):
            texto, tipo, fontes = resultado
            return (f"{leitura.abertura} {texto}" if leitura.abertura else texto), tipo, fontes

        # Continuação: "e em Portugal?" → a pergunta anterior reescrita.
        if leitura.continuacao:
            etapas.meta["entendida"] = leitura.continuacao
            texto, tipo, fontes = self._pipeline(leitura.continuacao, busca, resposta, etapas,
                                                 contexto, profundidade + 1)
            return com_abertura((f"*Entendi: “{leitura.continuacao}”.*\n\n{texto}", tipo, fontes)), leitura

        ato = leitura.ato
        acao = ato["acao"] if ato else None
        tem_assunto = bool(leitura.assunto_real)
        if acao in ("crise", "acolher"):
            etapas.marcar(f"Diálogo · {ato['id']}", {"ação": acao})
            return (self.dialogo.texto(ato, mensagem, leitura.assunto), "dialogo", []), leitura
        if acao == "convidar" and not tem_assunto:
            etapas.marcar(f"Diálogo · {ato['id']}", {"ação": acao})
            return com_abertura((self.dialogo.texto(ato, mensagem), "dialogo", [])), leitura
        if acao in SO_SEM_ASSUNTO and not tem_assunto:
            return com_abertura(self._ato_de_contexto(ato, mensagem, busca, resposta, etapas,
                                                      contexto, profundidade)), leitura
        if acao == "opinar":
            return com_abertura(self._opinar(ato, mensagem, leitura, busca, resposta, etapas,
                                             contexto, profundidade)), leitura

        # Pedido COM assunto ("consegue me ajudar com a senha do wifi?") ou
        # cumprimento + pergunta: segue com o que interessa.
        if acao == "convidar" and leitura.assunto and leitura.vago and ato.get("assunto_vago"):
            etapas.marcar(f"Diálogo · {ato['id']}", {"ação": acao, "assunto vago": leitura.assunto})
            return com_abertura((self.dialogo.texto(ato, mensagem, leitura.assunto, vago=True),
                                 "dialogo", [])), leitura
        if acao == "convidar" and leitura.assunto:
            return com_abertura(self._pipeline(leitura.assunto, busca, resposta, etapas,
                                               contexto, profundidade + 1)), leitura
        if leitura.abertura and leitura.resto:
            etapas.meta.setdefault("entendida", leitura.resto)
            return com_abertura(self._pipeline(leitura.resto, busca, resposta, etapas,
                                               contexto, profundidade + 1)), leitura
        return None, leitura

    def _ato_de_contexto(self, ato: dict, mensagem: str, busca: str, resposta: str,
                         etapas: Etapas, contexto: dict[str, Any], profundidade: int):
        """Atos que reagem à resposta anterior: não entendi, não era isso, sim, não."""
        acao = ato["acao"]
        anterior = contexto.get("resposta") or {}
        meta = anterior.get("meta") or {}
        etapas.marcar(f"Diálogo · {ato['id']}", {
            "ação": acao, "resposta anterior": meta.get("tipo") or "nenhuma"})
        padrao = (self.dialogo.texto(ato, mensagem), "dialogo", [])

        # 2.0: com teia, "não entendi" vai mais FUNDO em vez de repetir o texto.
        # Se a resposta anterior não explicou os porquês, explica; se já
        # explicou, desce até a BASE: o que é cada conceito em que ela se apoiou.
        if acao == "reformular" and meta.get("tipo") == "conhecimento" and meta.get("fontes"):
            fundo = self._explicar_mais_fundo(meta, mensagem, etapas)
            if fundo:
                return fundo
        if acao == "reformular" and meta.get("tipo") == "conhecimento" and meta.get("fontes"):
            # A resposta anterior pode ter sido um resumo (Direta/Extrativa):
            # mostra o texto inteiro de onde ela saiu, se ele trouxer algo a mais.
            ja_dito = anterior.get("texto") or ""
            partes, fontes, origem = [], [], []
            for f in meta["fontes"][:2]:
                c = self.banco.obter_conhecimento(f["id"])
                if not c:
                    continue
                fontes.append(self._fonte(c))
                origem.append(f"**{f['titulo']}**" + (f" (addon {f['addon']})" if f.get("addon") else ""))
                if c["conteudo"].strip() not in ja_dito:
                    partes.append(c["conteudo"])
            if partes:
                texto = ("Vou mostrar de outro jeito: este é o texto completo de onde tirei a "
                         "resposta.\n\n" + "\n\n".join(partes)
                         + "\n\nSe ainda não ficou claro, me diga qual parte e eu procuro de novo.")
                return texto, "conhecimento", fontes
            if origem:
                return (self.dialogo.texto(ato, mensagem) + "\n\nA resposta anterior já era o "
                        "texto inteiro que eu tenho, e veio de " + ", ".join(origem) + "."), \
                    "dialogo", fontes
        if acao == "reformular" and meta.get("tipo") == "desconhecido":
            return ("Eu quis dizer que ainda não aprendi nada sobre isso: não está no que você "
                    "me ensinou nem nos addons ativos. Se você souber a resposta, clique em "
                    "**Ensinar isso** e eu passo a saber."), "dialogo", []

        if acao == "outras_opcoes" and anterior:
            usados = {f["id"] for f in meta.get("fontes") or []}
            busca_anterior = next((e for e in (meta.get("explicacao") or {}).get("etapas", [])
                                   if e["nome"].startswith("Busca")), None)
            outros = [c["titulo"] for c in (busca_anterior or {}).get("dados", {}).get("candidatos", [])
                      if c["id"] not in usados][:4]
            texto = ("Desculpe, então não acertei. Se você souber a resposta certa, clique em "
                     "**Corrigir** embaixo da minha resposta: a correção vira um ensinamento.")
            if outros:
                texto = ("Desculpe! Talvez você estivesse procurando um destes:\n\n"
                         + "\n".join(f"- {t}" for t in outros) + "\n\n" + texto.split(". ", 1)[1])
            return texto, "dialogo", []

        rec = meta.get("recomendacao")
        if acao == "confirmar" and rec and rec.get("acao") == "ativar" and contexto.get("pergunta"):
            self.definir_addon_ativo(rec["id"], True)
            pergunta = contexto["pergunta"]
            etapas.marcar("Diálogo · ativar addon", {"addon": rec["nome"]})
            texto, tipo, fontes = self._pipeline(pergunta, busca, resposta, etapas,
                                                 {"pergunta": None, "resposta": None},
                                                 profundidade + 1)
            return (f"Ativei o addon **{rec['nome']}**. Sobre “{pergunta}”:\n\n{texto}",
                    tipo, fontes)
        if acao == "negar" and rec:
            return "Tudo bem, deixei como está. Se precisar, é só perguntar.", "dialogo", []
        return padrao

    def _opinar(self, ato: dict, mensagem: str, leitura, busca: str, resposta: str,
                etapas: Etapas, contexto: dict[str, Any], profundidade: int):
        """
        "O que você acha de X?": o Aprendiz não tem opinião própria e diz isso
        com franqueza; em seguida mostra o que SABE sobre X (se souber).
        Sem assunto ("o que você acha?"), o assunto é a pergunta anterior.
        """
        assunto = leitura.assunto if leitura.assunto_real else None
        if not assunto and contexto.get("pergunta"):
            assunto = contexto["pergunta"]
        etapas.marcar(f"Diálogo · {ato['id']}", {"ação": "opinar", "assunto": assunto or "—"})
        texto = self.dialogo.texto(ato, mensagem, assunto)
        if not assunto:
            return texto, "dialogo", []
        # Opinião sobre um tema aberto ("o que você acha da vida?"): é uma pergunta
        # reflexiva, e não uma busca pela palavra "vida" na base.
        for forma in (assunto, f"o que é a {assunto}", f"o que é o {assunto}"):
            tema = self.dialogo.ler(forma, self.linguagem.processar(forma).tokens)
            if tema.ato and tema.ato["acao"] == "refletir":
                etapas.marcar("Diálogo · reflexão", {"ato": tema.ato["id"], "tema": assunto})
                return self.dialogo.texto(tema.ato, mensagem, assunto), "dialogo", []
        sub = Etapas()
        achado, tipo, fontes = self._pipeline(assunto, busca, resposta, sub,
                                              {"pergunta": None, "resposta": None},
                                              MAX_PROFUNDIDADE)  # sem diálogo de novo
        etapas.lista.extend(sub.lista)
        if tipo == "conhecimento":
            return f"{texto}\n\nO que eu sei sobre **{assunto}**:\n\n{achado}", tipo, fontes
        return (f"{texto}\n\nE sobre **{assunto}** ainda não aprendi nada. Se quiser, me conte "
                "o que você pensa: escreva `anote: ...` e eu guardo."), "dialogo", []

    # ================================================================ REVISÃO
    def normas_disponiveis(self) -> list[dict[str, Any]]:
        """Normas dos addons ativos (para a interface e a configuração)."""
        return sorted((n.resumo() for n in self.revisor.normas().values()),
                      key=lambda n: n["nome"])

    def revisar_texto(self, texto: str, norma_id: str | None = None) -> dict[str, Any]:
        """Revisão pedida pela interface (tela Revisar texto)."""
        texto = (texto or "").strip()
        if not texto:
            raise ValueError("Escreva um texto para revisar.")
        norma, motivo = self.revisor.escolher(
            norma_id or None, texto=texto,
            padrao=self.configuracoes.valor("revisao.norma") or None)
        if not norma:
            raise ValueError("Nenhum addon de norma está ativo. Instale um dos addons de "
                             "português da loja oficial (Brasil, Portugal, Angola…).")
        resultado = self.revisor.revisar(texto, norma)
        resultado["motivo"] = motivo
        return resultado

    def _revisao(self, pedido, consulta, etapas: Etapas) -> tuple[str, str, list] | None:
        """Atende um pedido de revisão; None = deixa o pipeline seguir."""
        if not pedido.explicito and self._dono_ensinou_exatamente(consulta):
            return None
        texto_base = pedido.texto or " ".join(pedido.opcoes)
        norma, motivo = self.revisor.escolher(
            texto_norma=pedido.norma_texto, texto=texto_base,
            padrao=self.configuracoes.valor("revisao.norma") or None)
        if norma is None:
            if not pedido.explicito:
                return None
            etapas.marcar("Revisão", {**pedido.como_dict(), "norma": "nenhuma ativa"})
            return MSG_SEM_NORMA, "revisao", []
        aviso = ""
        if pedido.norma_texto and motivo != "pedida":
            aviso = f"*Não tenho a norma “{pedido.norma_texto}”; usei {norma.nome}.*\n\n"

        if pedido.acao == "grafar":
            return self._grafar(pedido, etapas)

        if pedido.acao == "comparar":
            opcoes = self.revisor.comparar(pedido.opcoes, norma)
            etapas.marcar("Revisão", {**pedido.como_dict(), "norma": norma.nome,
                                      "certas": [o["opcao"] for o in opcoes if o["certa"]]})
            return aviso + revisao.descrever_comparacao(opcoes, norma.resumo()), "revisao", []

        resultado = self.revisor.revisar(pedido.texto, norma)
        etapas.meta["revisao"] = {**resultado, "motivo": motivo}
        etapas.marcar("Revisão", {**pedido.como_dict(), "norma": norma.nome, "motivo": motivo,
                                  "apontamentos": len(resultado["apontamentos"])})
        return aviso + revisao.descrever(resultado, motivo), "revisao", []

    def _grafar(self, pedido, etapas: Etapas) -> tuple[str, str, list] | None:
        """'como se escreve económico?' → a grafia em cada norma ativa."""
        grafias = self.revisor.grafar(pedido.texto)
        ativas = self.revisor.normas()
        pedida = self.revisor.resolver_norma(pedido.norma_texto) if pedido.norma_texto else None
        etapas.marcar("Revisão", {**pedido.como_dict(), "normas": len(grafias)})
        if not any(grafias.values()):
            return None                       # deixa a busca tentar (talvez o dono ensinou)
        if pedida and grafias.get(pedida.id):
            formas = " ou ".join(f"**{f}**" for f in grafias[pedida.id])
            texto = f"Na norma **{pedida.nome}**, escreve-se {formas}."
            outras = {i: f for i, f in grafias.items() if i != pedida.id and f}
            if outras:
                texto += "\n\nNas outras normas instaladas:\n\n" + "\n".join(
                    f"- **{ativas[i].nome}:** {' ou '.join(f)}"
                    for i, f in sorted(outras.items(), key=lambda par: ativas[par[0]].nome))
            return texto, "revisao", []
        linhas = [f"- **{ativas[i].nome}:** " + (" ou ".join(f"**{x}**" for x in f)
                                                 if f else "não encontrei")
                  for i, f in sorted(grafias.items(), key=lambda par: ativas[par[0]].nome)]
        return f"Como se escreve *{pedido.texto}*:\n\n" + "\n".join(linhas), "revisao", []

    def buscar(self, consulta, busca: str, limite: int = 5) -> tuple[list, list, float]:
        """
        Etapa de busca do pipeline, separada para ser reaproveitada (a
        recomendação de algoritmo dos addons usa este mesmo caminho).
        Devolve (candidatos, aceitos, limiar), com os aceitos já ordenados.
        """
        # Parâmetros em vigor (dono > addon ativo > padrão; ver configuracoes.py)
        config = self.configuracoes.efetivas()
        self.contexto.limiares = {nome: config[f"limiar.{nome}"]["valor"]
                                  for nome in BUSCAS if f"limiar.{nome}" in config}
        margem_dono = config["prioridade_dono.margem"]["valor"]

        limiar = self.contexto.limiar(busca)
        candidatos = self._filtrar_verbetes(
            consulta, BUSCAS[busca].buscar(consulta, self.contexto, limite=limite))
        # Assunto declarado (2.0): quantas palavras informativas da pergunta
        # estão no que o conhecimento DECLARA tratar (pergunta, variações, A:).
        # É evidência mais forte do que a palavra solta no texto, então:
        #   • aceita um pouco abaixo do limiar quem bate no assunto
        #     ("jogar fora os pedidos cancelados" → apagar: "pedidos
        #     cancelados" é só o exemplo, a ação é que é o assunto);
        #   • entre os aceitos, quem bate em mais palavras do assunto vem antes
        #     ("adicionar um pedido NOVO" → inserir, e não ALTER TABLE).
        #   • o que bate MAIS que todos no assunto ganha folga extra ("menor
        #     caminho entre duas cidades" → Dijkstra, mesmo com nota baixa).
        bate = {c.id: self._bate_no_assunto(consulta, c.conhecimento) for c in candidatos}
        maior = max(bate.values(), default=0)
        unico = sum(1 for v in bate.values() if v == maior) == 1
        # O limiar que o DONO definiu é respeitado à risca (modo estrito).
        dono_definiu = config.get(f"limiar.{busca}", {}).get("origem") == "dono"

        def folga(c) -> float:
            if not bate[c.id] or dono_definiu:
                return 1.0
            return FOLGA_MELHOR_ASSUNTO if unico and bate[c.id] == maior else FOLGA_ASSUNTO

        aceitos = [c for c in candidatos
                   if c.confianca >= folga(c) * limiar and self._cobre_palavra_forte(consulta, c)]
        # Quem declarou exatamente esta pergunta (pergunta ou variação) vem antes
        # de tudo: "o que é c?" é a variação do fragmento sobre a linguagem C.
        exata = {c.id: self._mesmas_palavras(consulta, c) for c in aceitos}
        # Empate numa definição ("o que é c?"): vale o fragmento que define
        # ("o que é a linguagem c"), e não o que só usa o assunto (laço for em c).
        def define(c) -> bool:
            return bool(self._assunto_definicao) and normalizar(
                c.conhecimento.get("pergunta") or "").startswith(("o que e ", "o que sao "))
        aceitos.sort(key=lambda c: (not exata[c.id], -bate[c.id], not define(c)))
        # Prioridade do dono: se o melhor resultado veio de um addon, mas há
        # algo ensinado pelo dono quase tão relevante (por padrão, até 10%
        # abaixo), vale o do dono. A margem existe porque respostas mais longas
        # pontuam um pouco menos em alguns algoritmos, mesmo respondendo a
        # mesma coisa. Ajustável em Configurações (prioridade_dono.margem).
        # Um verbete exato (dicionário) só perde para algo do dono que também
        # seja exatamente aquela palavra; senão, "nha" (Cabo Verde) seria
        # trocado por "senha do wifi", que o Fuzzy acha parecido.
        topo_verbete = bool(aceitos) and aceitos[0].detalhes.get("verbete") == "palavra exata"
        if aceitos and aceitos[0].conhecimento.get("addon_id"):
            for i, c in enumerate(aceitos):
                if (not c.conhecimento.get("addon_id")
                        and c.confianca >= margem_dono * aceitos[0].confianca
                        and (not topo_verbete or self._mesmas_palavras(consulta, c))):
                    aceitos.insert(0, aceitos.pop(i))
                    break
        return candidatos, aceitos, limiar

    def _filtrar_verbetes(self, consulta, candidatos: list) -> list:
        """
        Verbetes (entradas de dicionário, vindas de addons) seguem uma regra
        própria: só valem quando a pergunta, sem as stopwords, é EXATAMENTE a
        palavra do verbete. Assim:

            "bué" · "o que significa bué?" · "qual o significado de bué" → responde
            "tem bué de gente na festa"                                 → ignora

        ("significa", "significado"… viram stopwords pelo próprio addon.)
        Um verbete exato ganha confiança 1 e vai para o topo; os outros são
        descartados, para não "sequestrar" perguntas sobre outros assuntos.
        """
        exatos, outros = [], []
        for c in candidatos:
            if c.conhecimento.get("tipo") != "verbete":
                outros.append(c)
                continue
            if self._mesmas_palavras(consulta, c):
                c.confianca = 1.0
                c.detalhes = {**c.detalhes, "verbete": "palavra exata"}
                exatos.append(c)
        return exatos + outros

    def _explicar_mais_fundo(self, meta: dict, mensagem: str,
                             etapas: Etapas) -> tuple[str, str, list] | None:
        """O próximo nível de explicação da resposta anterior, pela teia. None se não houver."""
        doc = self.banco.obter_conhecimento(meta["fontes"][0]["id"])
        if not doc or not teia_de(doc):
            return None
        consulta = self.linguagem.processar(meta.get("pergunta") or doc.get("pergunta") or "")
        self.contexto.caminho = self.teia.percorrer(doc, consulta.radicais)
        algoritmo = (meta.get("explicacao") or {}).get("algoritmo_resposta")
        if algoritmo != "trabalhada":
            gerada = RESPOSTAS["trabalhada"].responder(
                consulta, [Candidato(doc, 1.0, 1.0)], self.contexto)
            etapas.marcar("Diálogo · explicar os porquês", {"partida": teia_de(doc)["ref"]})
            return ("Vou explicar o porquê.\n\n" + gerada.texto, "conhecimento",
                    [self._fonte(doc)])
        # Já tinha os porquês: a base de cada conceito que apareceu.
        base, fontes = [], []
        for passo in self.contexto.caminho.usados if self.contexto.caminho else []:
            alvo = passo.para
            if alvo is None or alvo["id"] in {f["id"] for f in fontes}:
                continue
            # O resumo do conceito; se ele começa direto num exemplo de código,
            # vale o próprio porquê que levou até ele.
            trecho = resumo(alvo["conteudo"]) or _capitalizar(passo.texto)
            if trecho:
                base.append(f"- **{_capitalizar(alvo.get('pergunta') or '')}**: {trecho}")
                fontes.append(self._fonte(alvo))
        if not base:
            return None
        etapas.marcar("Diálogo · explicar a base", {"conceitos": len(base)})
        return ("Vou pela base. A explicação se apoia nestes conceitos:\n\n" + "\n".join(base)
                + "\n\nQuer que eu explique algum deles?"), "conhecimento", fontes

    def _informativas(self, consulta) -> list[str]:
        """Palavras que dizem o assunto: 4 letras ou mais e, com vetores, fora das mais comuns."""
        lexico = self.linguagem.lexico
        return [t for t in consulta.conteudo if len(t) >= 4 and not (
            lexico.tem_vetores and lexico.frequente(t, PALAVRAS_COMUNS_ASSUNTO))]

    def _assunto_declarado(self, doc: dict) -> set[str]:
        teia = teia_de(doc) or {}
        return set(normalizar(" ".join([doc.get("pergunta") or "", *lista_json(doc, "variacoes"),
                                        *(teia.get("assuntos") or [])])).split())

    def _bate_no_assunto(self, consulta, doc: dict) -> float:
        return sum(self._bate_por_palavra(consulta, doc).values())

    def _bate_por_palavra(self, consulta, doc: dict) -> dict[str, float]:
        """
        Quanto a pergunta bate no assunto declarado do conhecimento: cada palavra
        informativa vale 2 se está na PERGUNTA dele (ou nas variações) e 1 se
        está só nos assuntos relacionados (A:). "Por que usar chave
        estrangeira?" é sobre o fragmento cuja pergunta é chave estrangeira, e
        não sobre o JOIN, que só a cita entre os assuntos.
        """
        propria = set(normalizar(" ".join([doc.get("pergunta") or "",
                                           *lista_json(doc, "variacoes")])).split())
        titulo = self._assunto_declarado(doc)
        raras = self._raridade_nos_titulos()
        informativas = set(self._informativas(consulta))
        # Palavras comuns ("começa", "zero") ainda dizem algo: valem metade.
        por_palavra: dict[str, float] = {}
        for t in dict.fromkeys(consulta.conteudo):
            if len(t) < 3 or t.isdigit():
                continue
            if len(t) == 3:
                # Sigla curta ("exe", "cte", "api"): só vale igual, sem folga.
                peso = 2 if t in propria else 1 if t in titulo else 0
            else:
                tol = self._tolera(t)  # "seta" existe: não é "set" mal digitado
                peso = (2 if _parecida(t, propria, tol) else
                        1 if _parecida(t, titulo, tol) else 0)
            if peso:
                # Cobrir mais palavras da pergunta também conta (COBERTURA).
                por_palavra[t] = (peso * raras.get(t, 1.0) * (1.0 if t in informativas else 0.5)
                                  + COBERTURA)
        return por_palavra

    def _raridade_nos_titulos(self) -> dict[str, float]:
        """
        Peso de cada palavra pela raridade entre as PERGUNTAS da base: "banco" e
        "dados" estão na pergunta de dezenas de fragmentos e quase não
        distinguem um do outro; "estrangeira" está em poucos. Peso = 1 / (1 +
        log2 do número de perguntas que têm a palavra). Refeito quando a base muda.
        """
        if self._raras_versao != self.banco.versao_conhecimento:
            contagem: dict[str, int] = {}
            for doc in self.banco.conhecimentos_ativos():
                texto = " ".join([doc.get("pergunta") or "", *lista_json(doc, "variacoes")])
                for p in set(normalizar(texto).split()):
                    contagem[p] = contagem.get(p, 0) + 1
            self._raras = {p: 1 / (1 + math.log2(n)) for p, n in contagem.items()}
            self._raras_versao = self.banco.versao_conhecimento
        return self._raras

    def _cobre_palavra_forte(self, consulta, candidato) -> bool:
        """
        A resposta precisa falar do ASSUNTO da pergunta: ter alguma palavra
        INFORMATIVA dela. Sem isto, "o que é um ponteiro em C?" era respondido
        com SQL por causa do apelido de tabela "c" (ou do radical "pont", que
        também é de "ponto"), e "como fazer bolo de cenoura" casava pelo "fazer".

        Palavra informativa: 4 letras ou mais e, com o addon de vetores, fora
        das palavras mais comuns da língua ("fazer", "coisa", "quero"). Ela está
        coberta se aparece na resposta com folga para flexão ("índices" →
        "índice": o começo da palavra) ou para erro de digitação ("lefet" →
        "left": semelhança de 85% ou mais; "where" e "while" ficam de fora).

        Pergunta de DEFINIÇÃO ("o que é um ponteiro?"): o assunto precisa
        estar no que o conhecimento declara tratar (pergunta, variações, A:).
        Um texto sobre passagem por referência que cita ponteiros não é a
        definição de ponteiro.

        Sem palavra informativa ("o que é c?", "o que e nul"), as palavras
        curtas valem se forem o ASSUNTO declarado do conhecimento (pergunta,
        variações, assuntos A:), e não uma letra perdida no meio do texto.
        """
        doc = candidato.conhecimento
        if not consulta.conteudo:
            return True
        titulo = self._assunto_declarado(doc)
        informativas = self._informativas(consulta)
        if not informativas:
            curtas = [t for t in consulta.conteudo if len(t) >= 3]
            return bool(set(consulta.conteudo) & titulo) or any(
                _parecida(t, titulo) for t in curtas)
        if self._assunto_definicao:
            alvo = [t for t in informativas if t in self._assunto_definicao]
            if alvo and not any(_parecida(t, titulo) for t in alvo):
                return False
        if any(_parecida(t, titulo, self._tolera(t)) for t in informativas):
            return True
        # Fragmento com teia DECLARA o que trata: se a pergunta não bate nesse
        # assunto, citar a palavra no meio do texto não basta ("qual a capital
        # da França?" não é respondida por um tutorial que usa a frase de exemplo).
        if teia_de(doc):
            return False
        # Nenhuma palavra da pergunta no assunto declarado: aí o texto precisa
        # ter TODAS elas. "Como fazer bolo de cenoura" não é respondido por um
        # texto sobre algoritmos que usa um bolo como exemplo (sem cenoura).
        palavras = set(normalizar(doc.get("conteudo") or "").split())

        def flexao(t: str) -> bool:
            # "levo" e "levar": mesmo radical e tamanho parecido. O tamanho evita
            # que "ponteiro" e "ponto" (radical "pont") passem por flexão.
            r = radical(t)
            return any(abs(len(p) - len(t)) <= 2 and radical(p) == r
                       for p in palavras if p[:2] == t[:2])

        return all(_parecida(t, palavras, self._tolera(t)) or flexao(t) for t in informativas)

    def _tolera(self, palavra: str) -> bool:
        """Erro de digitação só se a palavra não existe: "copa" não é "cópia" errada."""
        return not self.linguagem.lexico.conhece(palavra)

    def _dono_ensinou_exatamente(self, consulta) -> bool:
        """O dono ensinou uma pergunta com exatamente estas palavras?"""
        _, aceitos, _ = self.buscar(consulta, "bm25", limite=3)
        return any(not c.conhecimento.get("addon_id") and self._mesmas_palavras(consulta, c)
                   for c in aceitos)

    def _mesmas_palavras(self, consulta, candidato) -> bool:
        """
        A pergunta (sem stopwords) tem exatamente as palavras da 'pergunta' do
        conhecimento, ou de uma das suas variações ("busão", "buzão")?
        """
        doc = candidato.conhecimento
        desejado = set(consulta.radicais)
        for forma in [doc.get("pergunta") or ""] + lista_json(doc, "variacoes"):
            termos = set(self.linguagem.processar(forma, corrigir=False).radicais)
            if termos and termos == desejado:
                return True
        return False

    def corrigir(self, mensagem_id: str, resposta_correta: str) -> dict[str, Any]:
        """
        O dono corrigiu uma resposta: a pergunta original + a resposta certa
        viram um novo par pergunta/resposta. Assim o erro não se repete.
        """
        msg = self.banco.obter_mensagem(mensagem_id)
        if not msg or msg["papel"] != "assistente":
            raise ValueError("Mensagem não encontrada.")
        meta = msg["meta"] or {}
        pergunta = meta.get("pergunta")
        if not pergunta:
            raise ValueError("Não encontrei a pergunta original desta resposta.")

        # Se a resposta errada veio de um par pergunta/resposta cuja pergunta é
        # a mesma (ignorando acentos e maiúsculas), atualizamos esse par em vez
        # de criar um duplicado que "competiria" com ele na busca.
        alvo = None
        chave = " ".join(self.linguagem.processar(pergunta, corrigir=False).radicais)
        for fonte in meta.get("fontes", []):
            c = self.banco.obter_conhecimento(fonte["id"])
            if c and c["pergunta"] and " ".join(
                    self.linguagem.processar(c["pergunta"], corrigir=False).radicais) == chave:
                alvo = c["id"]
                break

        c = self.ensinar(resposta_correta, pergunta=pergunta, origem="correcao", id=alvo)
        meta["corrigida_por"] = c["id"]
        self.banco.atualizar_meta_mensagem(mensagem_id, meta)
        return c

    # ================================================================ utilidades
    @staticmethod
    def _titulo(c: dict) -> str:
        texto = c["pergunta"] or c["conteudo"]
        return texto if len(texto) <= 70 else texto[:67] + "…"

    def _fonte(self, c: dict) -> dict:
        fonte = {"id": c["id"], "tipo": c["tipo"], "titulo": self._titulo(c),
                 "origem": c["origem"], "addon": None}
        if c.get("addon_id"):
            addon = self.banco.obter_addon(c["addon_id"])
            fonte["addon"] = addon["nome"] if addon else c["addon_id"]
        return fonte
