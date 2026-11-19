"""
Teia de porquês (2.0): a partir do conhecimento que a busca achou, desce
pelos porquês ligados até as raízes, sem sair do assunto.

A busca responde "O QUE": o fragmento mais parecido com a pergunta. A teia
responde "POR QUE": cada fragmento de addon pode trazer porquês, e cada
porquê pode apontar para outro fragmento (do mesmo addon ou de outro), que
tem os seus próprios porquês. Seguindo essas ligações forma-se uma CADEIA:

    where ─porque→ group-by (raiz)
          └diferente-de→ having ─porque→ group-by (já visto)

O percurso é uma busca em largura (BFS): primeiro todos os porquês do
fragmento achado (nível 1), depois os porquês desses (nível 2), e assim por
diante. Três freios impedem a resposta de "perder o sentido":

    1. PROFUNDIDADE máxima (padrão 3 níveis).
    2. RAIZ: um fragmento marcado "N: raiz" é a base; não se desce além dele.
    3. ASSUNTO: do nível 2 em diante, só se segue para um fragmento cujos
       assuntos (linhas A:) têm alguma palavra em comum com a pergunta ou
       com os assuntos do fragmento de partida. Um elo que já não fala do
       assunto é cortado.
    4. LADO x FUNDO: relações de CAUSA (porque, regra, definição, parte de)
       descem até a raiz; relações LATERAIS (diferente de, consequência,
       exemplo, antes, depois) só valem no nível 1 e não se desdobram.
       "O que é NULL?" explica o NULL e cita o WHERE, mas não vira uma
       aula de WHERE.

E um fragmento nunca entra duas vezes (a teia pode ter ciclos).

Aqui só se MONTA o caminho; quem o transforma em texto é o montador de
resposta (resposta "Trabalhada").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aprendiz.memoria.banco import teia_de

PROFUNDIDADE = 3
MAX_PASSOS = 12
# Ordem em que os porquês de um fragmento são seguidos: primeiro a causa e a
# regra (o "por quê" de verdade), depois comparações e desdobramentos.
ORDEM_RELACOES = ("porque", "regra", "definicao", "parte-de", "diferente-de",
                  "consequencia", "exemplo-de", "antes-de", "depois-de")
CAUSAIS = {"porque", "regra", "definicao", "parte-de"}


@dataclass
class Passo:
    """Um porquê percorrido: de um fragmento, por uma relação, até outro (ou só texto)."""

    nivel: int
    origem_id: str                # id do conhecimento de onde sai o porquê
    de: str                       # ref do fragmento de onde sai o porquê
    relacao: str
    texto: str                    # a explicação escrita no porquê
    para: dict[str, Any] | None   # o conhecimento ligado (None = porquê só com texto)
    raiz: bool = False
    cortado: str | None = None    # motivo de não seguir: "visto", "assunto", "fora"

    def como_texto(self) -> str:
        destino = ""
        if self.para is not None:
            destino = f" → {(teia_de(self.para) or {}).get('ref')}"
            destino += " (raiz)" if self.raiz else ""
        motivo = f" [{self.cortado}]" if self.cortado else ""
        return f"{'  ' * (self.nivel - 1)}{self.de} —{self.relacao}{destino}{motivo}"


@dataclass
class Caminho:
    """O resultado do percurso: o fragmento de partida e os passos, em ordem de nível."""

    partida: dict[str, Any]
    passos: list[Passo] = field(default_factory=list)

    @property
    def usados(self) -> list[Passo]:
        """
        Os passos que entram na resposta. "visto" e "fora" ainda valem pelo
        TEXTO do porquê (só não se repete nem se segue o destino); "assunto"
        sai, porque já não fala do que foi perguntado.
        """
        return [p for p in self.passos if p.cortado != "assunto"]

    def explicacao(self) -> dict[str, Any]:
        return {"partida": (teia_de(self.partida) or {}).get("ref"),
                "passos": [p.como_texto() for p in self.passos],
                "usados": len(self.usados)}


class Teia:
    """Índice da teia (refs → conhecimentos) e o percurso."""

    def __init__(self, banco, linguagem=None) -> None:
        self.banco = banco
        self.linguagem = linguagem
        self._assuntos: dict[str, set[str]] = {}
        self._versao = -1
        self._refs: dict[tuple[str, str], dict[str, Any]] = {}

    def _atualizar(self) -> None:
        """Refaz o índice quando a base muda (contador de versão do Banco)."""
        if self._versao == self.banco.versao_conhecimento:
            return
        linhas = self.banco._consultar(
            "SELECT c.* FROM conhecimentos c LEFT JOIN addons a ON a.id = c.addon_id "
            "WHERE c.teia IS NOT NULL AND (c.addon_id IS NULL OR a.ativo = 1)")
        self._refs, self._assuntos = {}, {}
        for doc in linhas:
            teia = teia_de(doc)
            if teia and teia.get("ref"):
                self._refs[(doc.get("addon_id") or "", teia["ref"])] = doc
        self._versao = self.banco.versao_conhecimento

    def assuntos(self, doc: dict[str, Any]) -> set[str]:
        """Radicais da pergunta e dos assuntos (A:) de um fragmento (guardados em cache)."""
        if doc["id"] not in self._assuntos:
            teia = teia_de(doc) or {}
            texto = " ".join([doc.get("pergunta") or "", *(teia.get("assuntos") or [])])
            self._assuntos[doc["id"]] = (set(self.linguagem.processar(texto, corrigir=False).radicais)
                                         if self.linguagem else set(texto.lower().split()))
        return self._assuntos[doc["id"]]

    def resolver(self, liga: str, addon_atual: str) -> dict[str, Any] | None:
        """ "ref" → no mesmo addon; "addon:ref" → em outro addon (se estiver ativo)."""
        addon, _, ref = liga.rpartition(":")
        return self._refs.get((addon or addon_atual, ref))

    def percorrer(self, partida: dict[str, Any], radicais_pergunta: list[str],
                  profundidade: int = PROFUNDIDADE) -> Caminho | None:
        """O caminho de porquês a partir do conhecimento `partida`; None se ele não tem teia."""
        self._atualizar()
        if not teia_de(partida):
            return None
        caminho = Caminho(partida)
        # O "assunto" que segura o sentido: a pergunta + o fragmento de partida.
        assunto = set(radicais_pergunta) | self.assuntos(partida)
        vistos = {partida["id"]}
        fila = [(partida, 1)]
        while fila and len(caminho.passos) < MAX_PASSOS:
            atual, nivel = fila.pop(0)
            teia = teia_de(atual) or {}
            if nivel > profundidade:
                continue
            porques = sorted(teia.get("porques") or [],
                             key=lambda p: ORDEM_RELACOES.index(p["relacao"])
                             if p["relacao"] in ORDEM_RELACOES else len(ORDEM_RELACOES))
            for porque in porques:
                if len(caminho.passos) >= MAX_PASSOS:
                    break
                lateral = porque["relacao"] not in CAUSAIS
                if lateral and nivel > 1:
                    continue          # nível 2+: só a cadeia de causas desce
                destino = (self.resolver(porque["liga"], atual.get("addon_id") or "")
                           if porque.get("liga") else None)
                passo = Passo(nivel, atual["id"], teia.get("ref", "?"), porque["relacao"],
                              porque.get("texto") or "", destino)
                if porque.get("liga") and destino is None:
                    passo.cortado = "fora"        # addon desativado ou ausente
                elif destino is not None:
                    passo.raiz = bool((teia_de(destino) or {}).get("raiz"))
                    if destino["id"] in vistos:
                        passo.cortado = "visto"
                    elif nivel >= 2 and not assunto & self.assuntos(destino):
                        passo.cortado = "assunto"
                    else:
                        vistos.add(destino["id"])
                        if not passo.raiz and not lateral:
                            fila.append((destino, nivel + 1))
                caminho.passos.append(passo)
        return caminho
