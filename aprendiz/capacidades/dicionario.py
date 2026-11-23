"""
Dicionário: consultas aos VERBETES dos addons, nos dois sentidos.

Os addons de dicionário (gírias, crioulos, regionalismos) trazem verbetes:
um termo, o significado e, opcionalmente, as TRADUÇÕES para o português
padrão e a REGIÃO do dicionário. Com isso, o Aprendiz entende:

    Sentido direto (o que quer dizer o termo):
        "kota" · "o que significa kota?"            → o pipeline normal resolve
        "o que é kota em Angola?" · "kota em Angola" → aqui: tira a região da
                                                       frase e filtra por ela
    Sentido inverso (como se diz em tal lugar):
        "como se fala aldeia em Guiné?"              → tabanka
        "qual a gíria pra dinheiro em Moçambique?"   → mola
        "como os angolanos chamam o dinheiro?"       → kumbu
        "traduza aldeia para kriol"                  → tabanka
        "aldeia em kriol"                            → tabanka
        "como se diz ônibus?" (sem região)           → lista todos os lugares

Como funciona:
    1. A mensagem normalizada é testada contra alguns PADRÕES de frase
       (expressões regulares) que separam o termo (X) e a região (R).
    2. A região é procurada nos "termos" que cada addon declara no manifesto
       ("angola", "angolanos", "kriol"…).
    3. X vira radicais e é comparado por IGUALDADE com o termo/variações de
       cada verbete (sentido direto) ou com as traduções (sentido inverso).
       Igualdade, não semelhança: o dicionário só responde quando tem certeza.
    4. Se nada for encontrado, devolve None e o pipeline segue normalmente.
       Assim, "como se chama o seu pai?" não é sequestrado pelo dicionário.

Variedades (0.8+): um dicionário pode declarar regiões dentro da sua região
("Nordeste", "Sul" no Brasil) ou línguas que convivem com o português
("kriol" na Guiné-Bissau, "tétum" em Timor-Leste), e cada verbete pode dizer
de qual variedade é. "Como se diz mandioca no Nordeste?" filtra só os
verbetes daquela variedade; "em Brasil" continua valendo para todos.
Internamente, a região de uma variedade é a chave "<addon_id>/<variedade>".

O índice é montado a partir dos verbetes de addons ATIVOS e refeito sempre
que a base muda (versao_conhecimento do banco).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aprendiz.linguagem import normalizar
from aprendiz.memoria.banco import lista_json

# ------------------------------------------------------------------ padrões
_PREP = r"(?:em|no|na|nos|nas|pra|para|pro)"
_SUJEITO = r"(?:se|eu|a gente|voce|voces|o pessoal|as pessoas|o povo|vcs)"
_VERBO = (r"(?:diz|dizem|digo|dizer|fala|falam|falo|falar|chama|chamam|chamo|chamar|"
          r"escreve|escrevem|escrevo|traduz|traduzem|traduzo)")
_NOME = r"(?:giria|girias|palavra|termo|expressao|traducao|nome|jeito de (?:falar|dizer))"
# "variações", "traduções ou variações", "sinônimos e variantes"...
_VARIACAO = (r"(?:variacoes|variantes|traducoes|sinonimos|equivalentes|formas|maneiras|jeitos"
             r"|outros nomes|outras palavras)")
_VARIACOES = rf"{_VARIACAO}(?: (?:ou|e) (?:as |os |outras |outros )?{_VARIACAO})*"
# Pedido educado ANTES do pedido (2.3.1): "é possível listar ou indicar…",
# "você pode me dizer…", "me mostra…". Sai da frase antes dos padrões.
_LISTAR = r"(?:me )?(?:listar|liste|lista|indicar|indique|indica|mostrar|mostre|mostra|dizer|diga|diz|" \
          r"falar|fale|fala|citar|cite|cita|dar|de|da|passar|passe|passa|informar|informe|enumerar)"
_EDUCADO = re.compile(
    r"^(?:(?:e possivel|tem como|da (?:pra|para)|(?:voce )?(?:pode|poderia|consegue|conseguiria)"
    r"|gostaria de|quero|queria|preciso|por favor)(?: (?:me )?(?:por favor))? )?"
    rf"{_LISTAR}(?: (?:ou|e) {_LISTAR})* (?=(?:quais |as |os |algumas |alguns |outras |outros )?{_VARIACAO})")
_SOBRE_A_PALAVRA = re.compile(r"\b(?:traducoes|sinonimos|equivalentes|outras palavras|outros nomes)\b"
                              r"|\b(?:da palavra|do termo|de (?:se )?(?:dizer|falar))\b")
_LIGA = r"(?:de|do|da|para|pra|pro|que (?:significa|quer dizer)|que se usa para|usad[oa] para)"

# Os padrões olham só o "miolo" da frase: a região ("em Angola", "no kriol")
# já foi separada do fim por separar_regiao(). Cada padrão tem um sentido:
#   inverso → "como se diz X": X está em português padrão
#   direto  → "o que significa X": X é o termo do dicionário
# Grupos nomeados: x = o termo; ra = região dita como gentílico/adjetivo
# ("os angolanos", "a gíria angolana"); r1 = região no meio da frase.
PADROES: list[tuple[str, bool, re.Pattern]] = [   # (sentido, exige região?, regex)
    ("inverso", False, re.compile(
        rf"^(?:e )?como (?:e que )?(?:{_SUJEITO} )?(?:(?:os|as) (?P<ra>[a-z ]+?) )?{_VERBO}"
        rf"(?: (?:a palavra|o termo|a expressao))? (?P<x>.+)$")),
    ("inverso", False, re.compile(
        rf"^(?:e )?qual (?:e )?(?:a |o )?{_NOME}(?: (?P<ra>[a-z]+))?(?: {_PREP} (?P<r1>.+?))?"
        rf" {_LIGA} (?P<x>.+)$")),
    # "quais as variações de aldeia (em português)?", "outras formas de dizer aldeia":
    # a mesma ideia em todas as variedades (inverso sem região), mesmo com "em português".
    ("variacoes", False, re.compile(
        rf"^(?:quais (?:sao )?(?:as |os )?|outras |outros |as |os |algumas |alguns )?{_VARIACOES}"
        r" (?:de (?:se )?(?:dizer|falar) |de |da palavra |do termo |para (?:a palavra |o termo )?)(?P<x>.+?)"
        r"(?: (?:em|nos|no|pelos|pelo) (?:outros |varios |cada )?(?:paises|lugares|lusofonia|mundo))?$")),
    ("inverso", True, re.compile(r"^traduz(?:a|ir|e|ao de|ao)? (?P<x>.+)$")),
    ("inverso", True, re.compile(r"^como (?:e|fica|seria) (?P<x>.+)$")),
    ("direto", False, re.compile(
        r"^(?:o )?(?:que )?(?:e|significa|quer dizer) (?:o |a |um |uma )?"
        r"(?:(?:palavra|termo|expressao|giria) )?(?P<x>.+)$")),
    ("direto", False, re.compile(r"^qual (?:e )?(?:o )?(?:significado|sentido) (?:de|da|do) (?P<x>.+)$")),
    ("direto", False, re.compile(r"^(?:significado|definicao|traducao) (?:de|da|do) (?P<x>.+)$")),
    ("direto", False, re.compile(r"^(?P<x>.+?) (?:significa|quer dizer) o que$")),
    # "kota em Angola", "aldeia em kriol": só com região reconhecida
    ("qualquer", True, re.compile(r"^(?P<x>[a-z][a-z ]{0,40})$")),
]
_SUFIXO_COMO = re.compile(r" (?:e|se diz|se fala|fica) como$")

_ARTIGOS = {"o", "a", "os", "as", "um", "uma", "uns", "umas", "do", "da", "dos", "das", "de"}
_PREFIXOS_REGIAO = {"crioulo", "lingua", "idioma", "portugues", "giria", "girias", "dialeto",
                    "sotaque", "povo", "pais", "regiao"}
MAX_PALAVRAS_TERMO = 5
_CONTRACOES = {
    "em": {"": "em", "o": "no", "a": "na", "os": "nos", "as": "nas"},
    "de": {"": "de", "o": "do", "a": "da", "os": "dos", "as": "das"},
}
# "como se diz kota em português?" pede o SIGNIFICADO (sentido direto), não
# uma região: o português padrão é a língua das traduções.
_PORTUGUES_PADRAO = {"portugues", "bom portugues", "portugues padrao", "portugues normal",
                     "lingua portuguesa"}

@dataclass
class Pedido:
    sentido: str                 # "direto", "inverso" ou "qualquer" (o padrão que casou)
    termo: str                   # X, normalizado
    regiao_texto: str | None     # R como a pessoa escreveu (normalizado), se houver
    regioes: set[str] | None     # ids de addons dessa região; None = região não informada
    padrao: int = 0
    regiao_escrita: str | None = None  # R como está na mensagem, com acentos
    lexico: bool = False         # pedido claramente sobre a PALAVRA ("sinônimos de X")

    def como_dict(self) -> dict[str, Any]:
        return {"sentido": self.sentido, "termo": self.termo, "regiao": self.regiao_texto,
                "regiao_reconhecida": self.regioes is not None or self.regiao_texto is None,
                "padrao": self.padrao}


@dataclass
class _Indice:
    versao: int = -1
    termos: dict[frozenset, list[dict]] = field(default_factory=dict)
    traducoes: dict[frozenset, list[tuple[dict, str]]] = field(default_factory=dict)
    regioes: dict[str, dict[str, Any]] = field(default_factory=dict)   # addon_id → regiao
    apelidos: dict[str, set[str]] = field(default_factory=dict)       # termo → addon_ids


class Dicionario:
    def __init__(self, banco, linguagem) -> None:
        self.banco = banco
        self.linguagem = linguagem
        self._indice = _Indice()

    # ------------------------------------------------------------ índice
    def chave(self, texto: str) -> frozenset:
        """
        Chave de comparação de um termo: os radicais de TODAS as palavras,
        inclusive as que a busca ignora ("muito", "bem", "meu"…), sem o artigo
        do começo. "o ônibus" e "ônibus" dão a mesma chave; "sô" também tem
        uma, mesmo sendo igual a "só" (stopword).
        """
        limpo = self._limpar_termo(normalizar(texto))
        return frozenset(self.linguagem.processar(limpo, corrigir=False).radicais_todos)

    def indice(self) -> _Indice:
        versao = (self.banco.versao_conhecimento, self.banco.versao_linguagem)
        if self._indice.versao == versao:
            return self._indice
        novo = _Indice(versao=versao)
        addons = {a["id"]: a for a in self.banco.listar_addons() if a["ativo"]}
        for addon_id, a in addons.items():
            regiao = (a.get("manifesto") or {}).get("regiao") or {}
            nome = regiao.get("nome") or a["nome"]
            artigo = regiao.get("artigo", "")
            novo.regioes[addon_id] = {
                "nome": nome,
                "em": f"{_CONTRACOES['em'][artigo]} {nome}",    # "no Brasil", "em Angola"
                "de": f"{_CONTRACOES['de'][artigo]} {nome}",    # "do Brasil", "de Angola"
            }
            for termo in [nome, *regiao.get("termos", [])]:
                novo.apelidos.setdefault(normalizar(termo), set()).add(addon_id)
            for v in regiao.get("variedades") or []:
                chave_v = f"{addon_id}/{v['id']}"
                novo.regioes[chave_v] = {
                    "nome": v["nome"],
                    "em": f"{_CONTRACOES['em'][v.get('artigo', '')]} {v['nome']}",
                    "de": f"{_CONTRACOES['de'][v.get('artigo', '')]} {v['nome']}",
                }
                for termo in [v["nome"], *v.get("termos", [])]:
                    novo.apelidos.setdefault(normalizar(termo), set()).add(chave_v)

        for doc in self.banco.conhecimentos_ativos():
            if doc["tipo"] != "verbete" or doc["addon_id"] not in addons:
                continue
            for forma in [doc["pergunta"] or "", *lista_json(doc, "variacoes")]:
                chave = self.chave(forma)
                if chave and doc not in novo.termos.get(chave, []):
                    novo.termos.setdefault(chave, []).append(doc)
            for traducao in lista_json(doc, "traducoes"):
                chave = self.chave(traducao)
                if chave:
                    novo.traducoes.setdefault(chave, []).append((doc, traducao))
        self._indice = novo
        return novo

    # ------------------------------------------------------------ região
    def resolver_regiao(self, texto: str | None) -> set[str] | None:
        """'em Angola' → {'girias-angola'}. None se não reconhecer."""
        if not texto:
            return None
        apelidos = self.indice().apelidos
        palavras = texto.split()
        # Tira artigos e palavras como "crioulo de", "língua do", "os"...
        while palavras and (palavras[0] in _ARTIGOS or palavras[0] in _PREFIXOS_REGIAO):
            palavras.pop(0)
        candidato = " ".join(palavras)
        for forma in (candidato, candidato.rstrip("s"),
                      re.sub(r"as?$", "o", candidato), re.sub(r"os$", "o", candidato)):
            if forma in apelidos:
                return set(apelidos[forma])
        return None

    def separar_regiao(self, texto: str) -> tuple[str, str | None, set[str] | None, bool]:
        """
        Separa a região do FIM da frase: "como se diz casa de banho em portugal"
        → ("como se diz casa de banho", "portugal", {ids}, False). Tenta da
        última preposição para a primeira, para "casa de banho" e
        "estar-se nas tintas" continuarem inteiros. O último valor diz se a
        região é o "português padrão" ("como se diz kota em português?").
        Se nenhum trecho for uma região conhecida, devolve o último corte com
        regiões None (a pessoa citou um lugar que não tem dicionário).
        """
        cortes = [m for m in re.finditer(rf" {_PREP} ", texto)]
        for m in reversed(cortes):
            resto, sufixo = texto[:m.start()], texto[m.end():]
            if self._sem_artigos(sufixo) in _PORTUGUES_PADRAO:
                return resto, None, None, True
            regioes = self.resolver_regiao(sufixo)
            if regioes:
                return resto, sufixo, regioes, False
        if cortes:
            m = cortes[-1]
            return texto[:m.start()], texto[m.end():], None, False
        return texto, None, None, False

    # ------------------------------------------------------------ interpretação
    @staticmethod
    def _sem_artigos(texto: str) -> str:
        palavras = texto.split()
        while palavras and palavras[0] in _ARTIGOS:
            palavras.pop(0)
        return " ".join(palavras)

    @staticmethod
    def _limpar_termo(texto: str) -> str:
        palavras = texto.strip(" \"'").split()
        while palavras and palavras[0] in _ARTIGOS | {"palavra", "termo", "expressao", "giria"}:
            palavras.pop(0)
        return " ".join(palavras)

    def interpretar(self, mensagem: str, reescrito: str | None = None) -> Pedido | None:
        """
        Procura um pedido de dicionário na mensagem. None = não é um.

        `reescrito` (2.5.1) é a mensagem com abreviações expandidas e erros de
        digitação corrigidos ("o q siginfica trampo" → "o que significa
        trampo"). Ela é tentada depois da original, e vale se achar um termo
        que existe no dicionário.
        """
        indice = self.indice()
        if not indice.termos and not indice.traducoes:
            return None
        original = normalizar(mensagem)
        reserva: Pedido | None = None
        for texto in dict.fromkeys(t for t in (original, reescrito) if t):
            achado, possivel = self._interpretar_texto(texto, mensagem, indice)
            if achado:
                return achado
            reserva = reserva or possivel
        return reserva

    def _interpretar_texto(self, texto: str, mensagem: str,
                           indice) -> tuple[Pedido | None, Pedido | None]:
        """(pedido com termo do dicionário, pedido possível) lendo um texto normalizado."""
        texto = _EDUCADO.sub("", _SUFIXO_COMO.sub("", texto))
        miolo, regiao_texto, regioes, em_portugues = self.separar_regiao(texto)

        # Com região reconhecida (ou "em português"), testa só o miolo. Com um
        # lugar desconhecido no fim ("em inglês"), testa a frase inteira (o
        # "lugar" pode ser parte do termo) e o miolo, preferindo a leitura
        # cujo termo existe no dicionário.
        if regioes or em_portugues:
            alvos = [miolo]
        elif regiao_texto:
            alvos = [texto, miolo]
        else:
            alvos = [texto]

        reserva: Pedido | None = None
        for numero, (sentido, exige_regiao, padrao) in enumerate(PADROES):
            for alvo in alvos:
                pedido = self._montar(numero, sentido, exige_regiao, padrao, alvo,
                                      alvo is miolo,
                                      regiao_texto, regioes, em_portugues, mensagem)
                if not pedido:
                    continue
                chave = self.chave(pedido.termo)
                if chave in indice.termos or chave in indice.traducoes:
                    return pedido, None
                reserva = reserva or pedido
        return None, reserva

    def _montar(self, numero, sentido, exige_regiao, padrao, alvo, usa_miolo,
                regiao_texto, regioes, em_portugues, mensagem) -> Pedido | None:
        achado = padrao.match(alvo)
        if not achado:
            return None
        grupos = achado.groupdict()
        termo = self._limpar_termo(grupos.get("x") or "")
        if not termo or len(termo.split()) > MAX_PALAVRAS_TERMO:
            return None
        if sentido == "variacoes":
            # "sinônimos de X", "variações da palavra X": é sobre a palavra, e
            # não sobre o assunto ("as formas de ordenar uma lista" é Python).
            return Pedido("inverso", termo, None, None, numero, self._como_escrito(mensagem, None),
                          lexico=bool(_SOBRE_A_PALAVRA.search(alvo)))
        if em_portugues and usa_miolo:
            return Pedido("direto", termo, None, None, numero)
        # Região: a do fim da frase; ou dita no meio ("qual a gíria em Angola
        # para…") ou como gentílico ("os angolanos", "a gíria angolana").
        r_texto, r_ids = (regiao_texto, regioes) if usa_miolo else (None, None)
        interna = grupos.get("r1") or grupos.get("ra")
        if interna and not r_ids:
            r_texto, r_ids = interna, self.resolver_regiao(interna)
        if exige_regiao and not r_ids:
            return None
        if sentido != "inverso" and r_texto and not r_ids:
            return None  # termo + lugar desconhecido: não dá para separar com segurança
        return Pedido(sentido, termo, r_texto, r_ids, numero, self._como_escrito(mensagem, r_texto))

    @staticmethod
    def _como_escrito(mensagem: str, normalizado: str | None) -> str | None:
        """Recupera da mensagem original o trecho da região, com acentos ("Moçambique")."""
        if not normalizado:
            return None
        originais = re.findall(r"[\w'-]+", mensagem)
        alvo = normalizado.split()
        for i in range(len(originais)):
            for j in range(i + 1, len(originais) + 1):
                if normalizar(" ".join(originais[i:j])).split() == alvo:
                    return " ".join(originais[i:j])
        return normalizado

    # ------------------------------------------------------------ respostas
    def responder(self, pedido: Pedido) -> tuple[str, list[dict]] | None:
        """(texto, verbetes usados) ou None se o dicionário não sabe."""
        indice = self.indice()
        chave = self.chave(pedido.termo)
        diretos = indice.termos.get(chave, [])
        inversos = indice.traducoes.get(chave, [])
        if pedido.sentido == "inverso":
            ordem = (self._inverso, self._direto)
        else:
            ordem = (self._direto, self._inverso)
        for metodo in ordem:
            resposta = metodo(pedido, diretos, inversos)
            if resposta:
                return resposta
        return None

    def _regiao(self, doc: dict, forma: str = "nome") -> str:
        """Nome da região do verbete: forma "nome" (Brasil), "em" (no Brasil) ou "de" (do Brasil).
        Um verbete de uma variedade usa o nome dela ("no Nordeste")."""
        regioes = self.indice().regioes
        if doc.get("variedade"):
            chave = f"{doc['addon_id']}/{doc['variedade']}"
            if chave in regioes:
                return regioes[chave].get(forma, "?")
        return regioes.get(doc["addon_id"], {}).get(forma, "?")

    @staticmethod
    def _da_regiao(doc: dict, regioes: set[str] | None) -> bool:
        """O verbete pertence a uma das regiões pedidas (país inteiro ou variedade)?"""
        if not regioes:
            return False
        return (doc["addon_id"] in regioes
                or (bool(doc.get("variedade")) and f"{doc['addon_id']}/{doc['variedade']}" in regioes))

    def _nao_tem(self, pedido: Pedido) -> str:
        if pedido.regioes is None:
            return f"Não tenho um dicionário de “{pedido.regiao_escrita or pedido.regiao_texto}” instalado."
        nomes = sorted({self.indice().regioes[i]["de"] for i in pedido.regioes
                        if i in self.indice().regioes})
        return f"Não encontrei *{pedido.termo}* no dicionário {', '.join(nomes)}."

    def _direto(self, pedido: Pedido, diretos: list[dict], _inversos) -> tuple[str, list] | None:
        if not diretos:
            return None
        da_regiao = [d for d in diretos if self._da_regiao(d, pedido.regioes)]
        if da_regiao or not pedido.regiao_texto:
            usados = da_regiao or diretos
            return "\n\n".join(d["conteudo"] for d in usados), usados
        return (f"{self._nao_tem(pedido)} Nos outros dicionários:\n\n"
                + "\n\n".join(d["conteudo"] for d in diretos)), diretos

    def _inverso(self, pedido: Pedido, _diretos, inversos: list) -> tuple[str, list] | None:
        if not inversos:
            return None
        palavra = inversos[0][1]  # a tradução como está no addon (com acentos)
        da_regiao = [(d, t) for d, t in inversos if self._da_regiao(d, pedido.regioes)]

        if da_regiao:
            regiao = self._regiao(da_regiao[0][0], "em")
            termos = " ou ".join(f"**{d['pergunta']}**" for d, _ in da_regiao)
            texto = f"{regiao[0].upper()}{regiao[1:]}, *{palavra}* se diz {termos}.\n\n"
            texto += "\n\n".join(d["conteudo"] for d, _ in da_regiao)
            return texto, [d for d, _ in da_regiao]

        # Sem região (ou a região pedida não tem): lista por região.
        por_regiao: dict[str, list[str]] = {}
        for d, _ in inversos:
            termos = por_regiao.setdefault(self._regiao(d), [])
            if d["pergunta"] not in termos:
                termos.append(d["pergunta"])
        linhas = "\n".join(f"- **{regiao}:** {', '.join(termos)}"
                           for regiao, termos in sorted(por_regiao.items()))
        if pedido.regiao_texto:
            inicio = f"{self._nao_tem(pedido)} Nos dicionários que tenho, *{palavra}* se diz:"
        else:
            inicio = f"*{palavra.capitalize()}* nos dicionários instalados:"
        if len(inversos) == 1 and not pedido.regiao_texto:
            d = inversos[0][0]
            regiao = self._regiao(d, "em")
            texto = (f"{regiao[0].upper()}{regiao[1:]}, *{palavra}* se diz **{d['pergunta']}**.\n\n"
                     + d["conteudo"])
            return texto, [d]
        fim = "\n\nPergunte “o que significa <termo>” para ver o significado e exemplos."
        return f"{inicio}\n\n{linhas}{fim}", [d for d, _ in inversos]
