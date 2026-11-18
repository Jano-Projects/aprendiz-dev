"""
O pipeline: a classe que junta linguagem, memória e algoritmos.

Fluxo de uma mensagem (método `responder`):

    mensagem
       │
       ├─ 1. Normalização ........ linguagem.processar()
       ├─ 2. Ensino explícito? ... "aprenda que X é Y" / "pergunta: ... resposta: ..."
       ├─ 3. Interpretação ....... intenção (Naive Bayes) + entidades (regex)
       ├─ 4. Intenção social? .... "oi", "obrigado", "ajuda" → resposta pronta
       ├─ 5. Busca ............... algoritmo escolhido no seletor
       ├─ 6. Modo estrito ........ nada acima do limiar → "ainda não fui ensinado"
       └─ 7. Resposta ............ algoritmo de resposta escolhido no seletor

Cada etapa registra o que fez e quanto tempo levou. Esse registro vira a
"explicação" exibida no painel "Por que respondi isso?" da interface.
"""

from __future__ import annotations

import re
import time
from typing import Any

from aprendiz import addons as pacotes
from aprendiz.algoritmos import BUSCAS, RESPOSTAS, ContextoBusca, titulo_curto
from aprendiz.configuracoes import Configuracoes
from aprendiz.linguagem import ClassificadorIntencoes, Linguagem, extrair_entidades
from aprendiz.linguagem.normalizador import VERSAO_NORMALIZACAO
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


class Assistente:
    def __init__(self, banco: Banco) -> None:
        self.banco = banco
        self.linguagem = Linguagem(banco)
        self.contexto = ContextoBusca(banco=banco, linguagem=self.linguagem)
        self.configuracoes = Configuracoes(banco)
        self.classificador = ClassificadorIntencoes()
        self._versao_classificador = -1
        self._frases_exatas: dict[str, str] = {}  # frase normalizada → intenção

        # Se as regras de normalização mudaram desde a última vez que este
        # banco foi aberto (atualização do app), refaz os textos de busca.
        if self.banco.obter_meta("versao_normalizacao") != str(VERSAO_NORMALIZACAO):
            self.reindexar()
            self.banco.definir_meta("versao_normalizacao", str(VERSAO_NORMALIZACAO))

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
                f"{doc['pergunta'] or ''} {doc['conteudo']}", corrigir=False).texto_busca)
            for doc in docs
        ])
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
        chave = pacotes.chave_de_grupo(pacote.manifesto, pacote.parametros)
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
                f"{k['pergunta'] or ''} {k['conteudo']}", corrigir=False).texto_busca}
            for k in pacote.conhecimentos
        ]
        self.banco.instalar_addon(pacote.manifesto, conhecimentos, pacote.linguagem,
                                  pacote.hash, pacote.configuracoes)

        # Sinônimos/abreviações novos (ou removidos na atualização) mudam os
        # radicais de TODA a base, não só os do addon.
        if pacote.linguagem or (anterior and anterior["total_linguagem"]):
            self.reindexar()

        return {
            "addon": self.banco.obter_addon(pacote.manifesto["id"]),
            "versao_anterior": anterior["versao"] if anterior else None,
        }

    @staticmethod
    def _titulo_algoritmo(registro: dict, nome: str) -> str:
        return titulo_curto(registro, nome)

    def grupos_de_addons(self) -> list[dict[str, Any]]:
        """
        Addons instalados agrupados pelo padrão de busca e resposta que pedem
        (ver addons.chave_de_grupo). Addons sem recomendação ficam num grupo
        à parte, com chave None. Cada grupo diz se o padrão dele está em uso.
        """
        config = self.configuracoes.efetivas()
        em_uso = f"{config['busca.padrao']['valor']}+{config['resposta.padrao']['valor']}"
        grupos: dict[str | None, dict[str, Any]] = {}
        for a in self.banco.listar_addons():
            chave = pacotes.chave_de_grupo(a["manifesto"] or {},
                                           self.banco.configuracoes_do_addon(a["id"]))
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
                {"id": a["id"], "nome": a["nome"], "ativo": bool(a["ativo"])})
        # Grupos com recomendação primeiro (o em uso no topo); "sem recomendação" por último.
        return sorted(grupos.values(),
                      key=lambda g: (g["chave"] is None, not g["em_uso"], g["titulo"]))

    def definir_addons_ativos(self, ids: list[str], ativo: bool) -> int:
        """Ativa ou desativa vários addons de uma vez (reindexa uma vez só)."""
        existentes = {a["id"]: a for a in self.banco.listar_addons()}
        alterados = [i for i in ids if i in existentes and bool(existentes[i]["ativo"]) != ativo]
        for addon_id in alterados:
            self.banco.definir_addon_ativo(addon_id, ativo)
        if any(existentes[i]["total_linguagem"] for i in alterados):
            self.reindexar()
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
        if addon["total_linguagem"]:
            self.reindexar()
        return self.banco.obter_addon(addon_id)

    def remover_addon(self, addon_id: str) -> bool:
        addon = self.banco.obter_addon(addon_id)
        if not addon:
            return False
        self.banco.remover_addon(addon_id)
        if addon["total_linguagem"]:
            self.reindexar()
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
        msg_usuario = self.banco.adicionar_mensagem(conversa_id, "usuario", mensagem)

        etapas = Etapas()
        texto_resposta, tipo, fontes = self._pipeline(mensagem, busca, resposta, etapas)

        meta = {
            "tipo": tipo,
            "pergunta": mensagem,
            "fontes": fontes,
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

    def _pipeline(self, mensagem: str, busca: str, resposta: str,
                  etapas: Etapas) -> tuple[str, str, list[dict]]:
        """Executa as etapas e devolve (texto, tipo, fontes)."""
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
        curta = len(consulta.tokens) <= MAX_TOKENS_SOCIAL
        segunda = intencoes[1]["probabilidade"] if len(intencoes) > 1 else 0.0
        clara = (principal["probabilidade"] >= PROBABILIDADE_MINIMA_SOCIAL
                 and principal["probabilidade"] >= MARGEM_MINIMA_SOCIAL * segunda)
        if principal["intencao"] in INTENCOES_SOCIAIS and curta and clara:
            texto = self.banco.resposta_padrao(principal["intencao"]) or "Certo!"
            etapas.marcar("Resposta social", {"intencao": principal["intencao"]})
            return texto, "social", []

        if principal["intencao"] == "ensinar" and principal["probabilidade"] >= 0.6:
            etapas.marcar("Resposta social", {"intencao": "ensinar (formato não reconhecido)"})
            return MSG_FORMATO_ENSINO, "social", []

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

        # 6. Modo estrito -----------------------------------------------------
        if not aceitos:
            texto = MSG_NAO_SEI
            if candidatos:
                sugestoes = "\n".join(f"- {self._titulo(c.conhecimento)}" for c in candidatos[:3])
                texto += f"\n\nTalvez você esteja procurando algo parecido com:\n{sugestoes}"
            etapas.marcar("Modo estrito", {"motivo": "nenhum candidato acima do limiar"})
            return texto, "desconhecido", []

        # 7. Resposta ----------------------------------------------------------
        # Dicionário: se a pergunta é exatamente uma palavra com verbete, a
        # resposta junta TODOS os verbetes dessa palavra (ex.: "bué" em
        # Portugal e em Angola), um por parágrafo.
        verbetes = [c for c in aceitos if c.detalhes.get("verbete") == "palavra exata"]
        if verbetes and aceitos[0] in verbetes:
            etapas.marcar("Resposta · Dicionário", {"verbetes": len(verbetes)})
            texto = "\n\n".join(c.conhecimento["conteudo"] for c in verbetes)
            return texto, "conhecimento", [self._fonte(c.conhecimento) for c in verbetes]

        algoritmo_resposta = RESPOSTAS[resposta]
        gerada = algoritmo_resposta.responder(consulta, aceitos, self.contexto)
        etapas.marcar(f"Resposta · {algoritmo_resposta.titulo}", gerada.detalhes)

        por_id = {c.id: c.conhecimento for c in aceitos}
        fontes = [self._fonte(por_id[i]) for i in gerada.fontes if i in por_id]
        return gerada.texto, "conhecimento", fontes

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
        aceitos = [c for c in candidatos if c.confianca >= limiar]
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

    def _mesmas_palavras(self, consulta, candidato) -> bool:
        """A pergunta (sem stopwords) tem exatamente as palavras da 'pergunta' do conhecimento?"""
        termos = set(self.linguagem.processar(candidato.conhecimento.get("pergunta") or "",
                                              corrigir=False).radicais)
        return bool(termos) and termos == set(consulta.radicais)

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
