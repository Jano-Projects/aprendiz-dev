"""
Resposta direta: devolve o conteúdo do melhor conhecimento encontrado.

É o comportamento ideal para pares pergunta/resposta: o dono ensinou
"horário da farmácia → 8h às 20h", então a resposta é exatamente "8h às 20h".
Custo praticamente zero.
"""

from __future__ import annotations

from aprendiz.algoritmos.base import (
    AlgoritmoResposta, Candidato, ContextoBusca, RespostaGerada, registrar,
)
from aprendiz.linguagem import TextoProcessado


@registrar
class RespostaDireta(AlgoritmoResposta):
    nome = "direta"
    titulo = "Direta"
    apelido = "Fiel"
    quando_usar = "Respostas curtas, exatamente como você ensinou."
    custo = "leve"
    descricao = "Responde com o conhecimento mais relevante, do jeito que foi ensinado."
    explicacao = """
**Ideia:** devolver o conteúdo do melhor conhecimento encontrado, exatamente como foi ensinado.

**Passo a passo**
1. Recebe os candidatos aceitos pela busca, já ordenados.
2. Responde com o conteúdo do primeiro.

**Bom para:** pares de pergunta e resposta ("horário da farmácia → 8h às 20h").
**Limite:** se a resposta estiver no meio de um texto longo, devolve o texto inteiro.
"""

    def responder(self, consulta: TextoProcessado, candidatos: list[Candidato],
                  ctx: ContextoBusca) -> RespostaGerada:
        melhor = candidatos[0]
        return RespostaGerada(
            texto=melhor.conhecimento["conteudo"],
            fontes=[melhor.id],
            detalhes={"usado": melhor.id},
        )
