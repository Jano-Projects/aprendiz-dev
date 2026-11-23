"""
Extração de entidades com expressões regulares (regex).

"Entidades" são pedaços da mensagem com significado estruturado:
datas, horários, valores, CEPs, percentuais, telefones, e-mails, números.

As entidades aparecem no Monitor, para quem estuda
o projeto ver o que foi reconhecido em cada mensagem. A exportação de addons
também as usa para apontar possíveis dados pessoais (e-mail, telefone).

Regex é uma ferramenta simples e muito eficiente para padrões fixos.
Cada padrão abaixo está comentado para facilitar o estudo.
"""

from __future__ import annotations

import calendar
import re

PADROES: list[tuple[str, re.Pattern[str]]] = [
    # E-mail: algo@algo.dominio
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    # Valor em reais: R$ 10 | R$10,50 | R$ 1.234,56
    ("valor", re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|R\$\s?\d+(?:,\d{2})?", re.I)),
    # Data no formato ISO: 2026-03-12 (2.5.1; antes virava "2026" + "03-12")
    ("data", re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b")),
    # Data: 12/03/2026 | 12/03 | 12-03-26
    ("data", re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b")),
    # Datas relativas por extenso
    ("data", re.compile(r"\b(?:hoje|amanh[ãa]|ontem|depois de amanh[ãa])\b", re.I)),
    # Horário: 14h | 14h30 | 14:30 | 8 horas
    ("horario", re.compile(r"\b\d{1,2}(?::\d{2}|h\d{0,2})\b|\b\d{1,2}\s?horas?\b", re.I)),
    # CEP: 01310-100 (2.5.1; antes virava dois números)
    ("cep", re.compile(r"\b\d{5}-\d{3}\b")),
    # Telefone brasileiro: (00) 90000-0000 | 00900000000 | 0000-0000
    ("telefone", re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b")),
    # Percentual: 10% | 10,5 %
    ("percentual", re.compile(r"\b\d+(?:[.,]\d+)?\s?%")),
    # Número genérico (o que sobrar)
    ("numero", re.compile(r"\b\d+(?:[.,]\d+)?\b")),
]


def _data_valida(valor: str) -> bool:
    """31/02 e 13/13 não são datas (2.5.1). Datas por extenso sempre valem."""
    numeros = [int(n) for n in re.findall(r"\d+", valor)]
    if not numeros:
        return True
    if valor[:4].isdigit():
        ano, mes, dia = numeros            # ISO: ano-mês-dia
    else:
        dia, mes = numeros[0], numeros[1]
        ano = numeros[2] if len(numeros) > 2 else 2000      # 2000: ano bissexto (29/02 vale)
        if ano < 100:
            ano += 2000
    if not 1 <= mes <= 12:
        return False
    return 1 <= dia <= calendar.monthrange(ano, mes)[1]


def _horario_valido(valor: str) -> bool:
    """25:99 e 30h não são horários (2.5.1)."""
    numeros = [int(n) for n in re.findall(r"\d+", valor)]
    hora, minuto = numeros[0], (numeros[1] if len(numeros) > 1 else 0)
    return hora <= 23 and minuto <= 59


VALIDAR = {"data": _data_valida, "horario": _horario_valido}


def extrair_entidades(texto: str) -> list[dict]:
    """
    Procura todas as entidades no texto ORIGINAL (com acentos e maiúsculas).

    Um trecho já reconhecido não é reconhecido de novo por um padrão mais
    genérico (ex.: o "12" de "12/03" não vira também um "numero"). Datas e
    horários impossíveis ("31/02", "25:99") são descartados e ficam para os
    padrões seguintes.
    """
    encontradas: list[dict] = []
    ocupado: list[tuple[int, int]] = []

    for tipo, padrao in PADROES:
        for m in padrao.finditer(texto):
            ini, fim = m.span()
            if any(ini < f and fim > i for i, f in ocupado):
                continue  # sobrepõe algo já reconhecido
            if tipo in VALIDAR and not VALIDAR[tipo](m.group(0)):
                continue
            ocupado.append((ini, fim))
            encontradas.append({"tipo": tipo, "valor": m.group(0), "inicio": ini, "fim": fim})

    return sorted(encontradas, key=lambda e: e["inicio"])
