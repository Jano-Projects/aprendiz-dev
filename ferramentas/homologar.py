"""
Homologação: perguntas de gente de verdade contra os addons REAIS da loja.

Os testes do tests/ usam addons pequenos, feitos para cada caso. Aqui é o
contrário: instala os addons publicados e faz perguntas do jeito que uma
pessoa faz (com erro de digitação, gíria, abreviação, fora do assunto, em
sequência) e confere se a resposta veio do lugar certo.

    python ferramentas/homologar.py ../aprendiz-addons
    python ferramentas/homologar.py ../aprendiz-addons --busca hibrido -v

Cada caso diz o que se espera:
    "q:<trecho>"     a 1ª fonte é o conhecimento cuja pergunta contém <trecho>
                     ("q:a|b": qualquer um dos dois, quando as duas respostas servem)
    "tipo:<tipo>"    o tipo da resposta (desconhecido, social, dialogo…)
    "panorama"       uma lista "Sobre X, encontrei isto:"
    "!q:<trecho>"    a resposta NÃO pode vir de <trecho>
    "fundo"          "não entendi" explicou mais fundo (porquês ou a base)
Um caso com "seguir" é feito na mesma conversa da pergunta anterior.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from aprendiz.algoritmos import BUSCAS  # noqa: E402
from aprendiz.core import Assistente  # noqa: E402
from aprendiz.memoria import Banco  # noqa: E402

ADDONS = ["compreensao-portugues", "dialogo-portugues", "vetores-portugues",
          "prog-logica", "prog-vocabulario", "prog-estruturas-dados", "prog-banco-dados",
          "sql-basico", "sql-avancado", "sql-teoria-pratica", "python-basico", "python-avancado",
          "aprendiz-algoritmos", "aprendiz-arquitetura", "aprendiz-codigo", "aprendiz-do-zero",
          "aprendiz-preparar-ambiente", "c-basico", "c-intermediario", "c-avancado",
          "cpp-basico", "cpp-intermediario", "cpp-avancado",
          "atalhos-terminal-linux", "atalhos-windows", "conversoes-medidas",
          "girias-brasil", "girias-portugal", "girias-angola", "girias-mocambique",
          "expressoes-cabo-verde", "expressoes-guine-bissau", "expressoes-sao-tome-e-principe",
          "expressoes-timor-leste"]

CASOS: list[tuple[str, str, str]] = [
    # (grupo, pergunta, esperado)
    ("direto", "o que é null?", "q:null"),
    ("direto", "como usar group by", "q:group by"),
    ("direto", "o que é left join", "q:left join"),
    ("variação", "oq é null", "q:null"),
    ("variação", "null é o quê?", "q:null"),
    ("variação", "me explica o null", "q:null"),
    ("variação", "pra que serve o group by", "q:group by"),
    ("variação", "pra q serve o having", "q:having"),
    ("variação", "como eu faço pra juntar duas tabelas?", "q:join"),
    ("variação", "como apagar registros de uma tabela", "q:apagar"),
    ("variação", "como mudar um valor que já está na tabela", "q:atualizar"),
    ("variação", "como pegar só os 10 primeiros", "q:limitar"),
    ("variação", "como ordenar do maior pro menor", "q:ordenar"),
    ("variação", "como contar quantas linhas tem", "q:agregação"),
    ("digitação", "diferensa entre wehre e havng", "q:having"),
    ("digitação", "o que e nul", "q:null|nulo"),   # NULL do SQL ou ponteiro nulo do C
    ("digitação", "como fazer um lefet join", "q:left join"),
    ("digitação", "grup by serve pra que", "q:group by"),
    ("porquê", "por que usar join?", "q:join"),
    ("porquê", "por que o where não funciona com count?", "q:having"),
    ("porquê", "por que = null não funciona", "q:null"),
    ("conceito", "o que é chave estrangeira?", "q:chave estrangeira"),
    ("conceito", "o que é um índice?", "q:índice"),
    ("conceito", "o que é uma transação", "q:transação"),
    ("resumo", "me fala de banco de dados", "panorama"),
    ("resumo", "tudo sobre join", "panorama"),
    ("resumo", "me dá um resumo de sql", "panorama"),
    ("fora", "o que é um ponteiro em C?", "q:ponteiro em c"),        # com os addons de C, tem resposta
    ("fora", "como fazer bolo de cenoura", "tipo:desconhecido"),
    ("fora", "quem ganhou a copa de 2002", "tipo:desconhecido"),
    # Confusão entre domínios (2.3.1): palavra que só COMEÇA igual
    # ("indicar"/"índice") ou palavra de contexto ("em português") não
    # podem puxar resposta de outro addon.
    ("confusão", "é possível listar ou indicar traduções ou variações da palavra aldeia em português?",
     "q:tabanka|suku"),
    ("confusão", "sinônimos de aldeia", "q:tabanka|suku"),
    ("confusão", "sinônimos de vilarejo", "tipo:desconhecido"),
    ("confusão", "pode me indicar um bom livro de culinária?", "!q:índice"),
    ("confusão", "quais as formas de dizer ônibus", "q:machimbombo|autocarro|busão"),
    ("fora", "o que é c?", "q:linguagem c"),
    ("fora", "qual a capital da frança", "tipo:desconhecido"),
    ("fora", "como declarar uma variável em python", "!q:sql"),
    # Inéditas: jeitos de perguntar que NÃO estão em nenhum addon. Medem se o
    # Aprendiz generaliza, e não se decorou as frases da homologação.
    ("inédita", "quero ver só as 5 primeiras linhas", "q:limitar"),
    ("inédita", "trocar o preço de um produto no banco", "q:atualizar"),
    ("inédita", "jogar fora os pedidos cancelados", "q:apagar"),
    ("inédita", "listar do mais caro pro mais barato", "q:orden"),   # ORDER BY ou algoritmos de ordenação
    ("inédita", "unir a tabela de clientes com a de pedidos", "q:join"),
    ("inédita", "quantos pedidos cada cliente fez", "q:group by"),
    ("inédita", "filtrar só os clientes de são paulo", "q:filtrar"),
    ("inédita", "campo vazio no banco de dados", "q:null"),
    ("inédita", "criar uma tabela nova", "q:criar uma tabela"),
    ("inédita", "colocar um cliente novo na tabela", "q:inserir"),
    # Inéditas 2: escritas ANTES de mexer no vocabulário dos addons, e não
    # consultadas enquanto ele era escrito. É a medida honesta de generalização.
    ("inédita 2", "como deletar um produto que não vende mais", "q:apagar"),
    ("inédita 2", "preciso modificar o email de um cliente", "q:atualizar"),
    ("inédita 2", "adicionar um pedido novo", "q:inserir"),
    ("inédita 2", "mostrar os produtos em ordem de preço", "q:ordenar"),
    ("inédita 2", "registros sem valor numa coluna", "q:null"),
    ("inédita 2", "somar o total vendido por mês", "q:group by"),
    ("inédita 2", "só os 3 produtos mais caros", "q:limitar"),
    ("inédita 2", "tirar um cliente do cadastro", "q:apagar"),
    # Inéditas 3: escritas DEPOIS dos padrões de frase e antes de ajustá-los.
    ("inédita 3", "quantas vendas cada produto teve", "q:group by"),
    ("inédita 3", "os 10 clientes que mais compraram", "q:limitar"),
    ("inédita 3", "incluir uma categoria nova", "q:inserir"),
    ("inédita 3", "excluir o pedido número 5", "q:apagar"),
    ("inédita 3", "juntar a tabela de produtos com a de categorias", "q:join"),
    ("inédita 3", "listar apenas os pedidos de março", "q:filtrar"),
    ("inédita 3", "média de preço por categoria", "q:group by"),
    ("inédita 3", "telefone vazio no cadastro", "q:null"),
    ("inédita 3", "como alterar o nome de um produto", "q:atualizar"),
    ("inédita 3", "mostrar os pedidos do mais novo pro mais antigo", "q:ordenar"),
    # Leva prog-banco-dados: escritas ANTES de pôr os porquês e o vocabulário.
    ("leva bd", "pra que serve uma chave primária", "q:chave primária"),
    ("leva bd", "por que normalizar o banco", "q:normalização"),
    ("leva bd", "o que é uma fk", "q:chave estrangeira"),
    ("leva bd", "diferença entre sql e nosql", "q:nosql"),
    ("leva bd", "o que significa acid", "q:acid"),
    ("leva bd", "por que usar transação", "q:transação"),
    ("leva bd", "como evitar sql injection", "q:sql injection"),
    ("leva bd", "um aluno faz vários cursos e um curso tem vários alunos", "q:muitos para muitos"),
    ("leva bd", "o que é um sgbd", "q:sgbd"),
    ("leva bd", "pra que serve um índice", "q:índice"),
    ("leva bd", "dados repetidos em várias tabelas", "q:normalização"),
    ("leva bd", "o que faz um orm", "q:orm"),
    ("leva bd", "guardar uma cópia do banco", "q:backup"),
    ("leva bd", "salvar várias alterações de uma vez ou nenhuma", "q:transação"),
    ("leva bd", "o que quer dizer crud", "q:crud"),
    # Leva prog-logica: escritas ANTES de pôr os porquês e o vocabulário.
    ("leva lógica", "pra que serve uma variável", "q:variável"),
    ("leva lógica", "qual a diferença entre for e while", "q:while e for"),
    ("leva lógica", "meu programa nunca para de repetir", "q:laço infinito"),
    ("leva lógica", "uma função que chama ela mesma", "q:recursão"),
    ("leva lógica", "por que o vetor começa do zero", "q:índice começa"),
    ("leva lógica", "o que é if e else", "q:condicional|if"),   # lógica ou o if do C
    ("leva lógica", "por que 0.1 + 0.2 dá 0.30000000000000004", "q:0.1"),
    ("leva lógica", "o que é true e false", "q:booleana"),
    ("leva lógica", "como encontrar o erro no meu código", "q:depurar"),
    ("leva lógica", "simular o programa no papel linha por linha", "q:teste de mesa"),
    ("leva lógica", "diferença entre parâmetro e argumento", "q:parâmetro"),
    ("leva lógica", "variável que só existe dentro da função", "q:escopo"),
    ("leva lógica", "um laço dentro de outro laço", "q:aninhado"),
    ("leva lógica", "valor que não muda durante o programa", "q:constante"),
    ("leva lógica", "por onde começar a programar", "q:aprender a programar"),
    # Leva prog-vocabulario: escritas ANTES de pôr os porquês e o vocabulário.
    ("leva vocab", "pra que serve o git", "q:git"),
    ("leva vocab", "salvar uma versão do código no git", "q:commit"),
    ("leva vocab", "trabalhar numa cópia separada do projeto sem mexer no principal", "q:branch"),
    ("leva vocab", "mandar meu código pro github", "q:push"),
    ("leva vocab", "arquivo para o git ignorar", "q:gitignore"),
    ("leva vocab", "diferença entre biblioteca e framework", "q:framework"),
    ("leva vocab", "o que é uma api rest", "q:api"),
    ("leva vocab", "formato de dados com chaves e valores usado na web", "q:json"),
    ("leva vocab", "parte do site que o usuário vê", "q:front end"),
    ("leva vocab", "escrever o teste antes do código", "q:tdd"),
    ("leva vocab", "melhorar o código sem mudar o que ele faz", "q:refatoração"),
    ("leva vocab", "não repetir código", "q:dry"),
    ("leva vocab", "colocar o sistema no ar", "q:deploy"),
    ("leva vocab", "o que significa versão 2.1.3", "q:versionamento"),
    ("leva vocab", "aquela mensagem de erro com a lista de funções", "q:stack trace"),
    ("leva vocab", "programa para escrever código", "q:ide"),
    # Leva prog-estruturas-dados: escritas ANTES de pôr os porquês e o vocabulário.
    ("leva estruturas", "o que é big o", "q:complexidade"),
    ("leva estruturas", "por que meu código fica lento com muitos dados", "q:complexidade"),
    ("leva estruturas", "último a entrar é o primeiro a sair", "q:pilha"),
    ("leva estruturas", "primeiro a chegar é o primeiro a ser atendido", "q:fila"),
    ("leva estruturas", "como funciona um dicionário por dentro", "q:hash"),
    ("leva estruturas", "procurar num vetor ordenado dividindo ao meio", "q:busca binária"),
    ("leva estruturas", "qual o jeito mais rápido de ordenar", "q:ordenação"),
    ("leva estruturas", "menor caminho entre duas cidades", "q:dijkstra"),
    ("leva estruturas", "rede de amigos com ligações entre pessoas", "q:grafo"),
    ("leva estruturas", "quantas letras mudar para uma palavra virar outra", "q:levenshtein"),
    ("leva estruturas", "guardar resultados já calculados para não repetir", "q:programação dinâmica"),
    ("leva estruturas", "conferir se abre e fecha parênteses certo", "q:parênteses"),
    ("leva estruturas", "lista sem elementos repetidos", "q:conjunto"),
    ("leva estruturas", "autocompletar palavras pelo começo", "q:trie"),
    ("leva estruturas", "qual estrutura usar para meu problema", "q:qual estrutura"),
    # Leva SQL avançado e teoria: escritas ANTES de pôr os porquês e o vocabulário.
    ("leva sql 2", "consulta dentro de outra consulta", "q:subconsulta"),
    ("leva sql 2", "pra que serve o with no sql", "q:cte"),
    ("leva sql 2", "numerar as linhas de um resultado", "q:row_number"),
    ("leva sql 2", "total acumulado mês a mês", "q:soma acumulada"),
    ("leva sql 2", "juntar o resultado de duas consultas uma embaixo da outra", "q:union"),
    ("leva sql 2", "inserir ou atualizar se já existir", "q:upsert"),
    ("leva sql 2", "rodar algo automaticamente quando inserir uma linha", "q:trigger"),
    ("leva sql 2", "minha consulta está lenta", "q:otimizar"),
    ("leva sql 2", "transformar linhas em colunas", "q:pivot"),
    ("leva sql 2", "diferença entre postgres e mysql", "q:diferenças entre sqlite"),
    ("leva sql 2", "segunda forma normal", "q:2fn"),
    ("leva sql 2", "uma transação ler dado que outra ainda não confirmou", "q:isolamento"),
    ("leva sql 2", "consistência disponibilidade e tolerância a partição", "q:cap"),
    ("leva sql 2", "como planejar as tabelas de um sistema novo", "q:modelar"),
    ("leva sql 2", "como o banco escolhe o jeito de executar a consulta", "q:otimizador"),
    # Leva Python: escritas ANTES de pôr os porquês e o vocabulário.
    ("leva python", "como pedir um número pro usuário em python", "q:ler dados do teclado"),
    ("leva python", "como colocar uma variável dentro de um texto em python", "q:f-string"),
    ("leva python", "pegar só os 3 primeiros caracteres de uma string", "q:fatiar"),
    ("leva python", "como evitar que o programa feche quando dá erro", "q:tratar erros"),
    ("leva python", "pip install", "q:instalar bibliotecas"),
    ("leva python", "função sem nome numa linha só", "q:lambda"),
    ("leva python", "criar uma lista nova a partir de outra numa linha", "q:list comprehension"),
    ("leva python", "isolar as bibliotecas de cada projeto", "q:ambiente virtual"),
    ("leva python", "função que modifica outra função com arroba", "q:decorador"),
    ("leva python", "abrir arquivo e fechar sozinho com with", "q:gerenciador de contexto"),
    ("leva python", "rodar várias coisas ao mesmo tempo em python", "q:threads"),
    ("leva python", "transformar meu script em um .exe", "q:executável"),
    ("leva python", "meu python está lento", "q:mais rápido|medir desempenho"),
    ("leva python", "chave e valor em python", "q:dicionário"),
    ("leva python", "o que é self em python", "q:classes"),
    # Aprendiz por dentro: o Aprendiz explicando a si mesmo (2.0.1).
    ("aprendiz", "como funciona a resposta trabalhada", "q:trabalhada"),
    ("aprendiz", "o que é a teia de porquês", "q:teia"),
    ("aprendiz", "como o aprendiz entende quantos pedidos cada cliente fez", "q:padrões de frase|estrutura da frase"),
    ("aprendiz", "de onde vêm as frases das respostas", "q:frases|expressão"),
    ("aprendiz", "como escrever os porquês num addon", "q:porquês de um addon"),
    ("aprendiz", "como medir se o aprendiz está acertando", "q:medir se o aprendiz|homologação"),
    ("aprendiz", "qual o caminho de uma mensagem no aprendiz", "q:caminho de uma mensagem"),
    ("aprendiz", "o que tem na pasta core", "q:pasta core"),
    ("aprendiz", "como rodar os testes do aprendiz", "q:rodar os testes"),
    ("aprendiz", "por que dois mais dois e 2+2 dão a mesma resposta", "q:números por extenso|dois mais dois"),
    # Leva C: escritas ANTES de pôr os porquês e o vocabulário.
    ("leva c", "como mostrar um número na tela em c", "q:printf"),
    ("leva c", "como pegar o que o usuário digitou em c", "q:ler dados do teclado"),
    ("leva c", "por que 7/2 dá 3 em c", "q:5 dividido por 2"),
    ("leva c", "meu programa em c deu falha de segmentação", "q:segmentation fault"),
    ("leva c", "variável que guarda o endereço de outra", "q:ponteiro em c"),
    ("leva c", "reservar memória enquanto o programa roda", "q:alocação dinâmica"),
    ("leva c", "esqueci de dar free", "q:vazamento"),
    ("leva c", "juntar vários campos num tipo só em c", "q:struct"),
    ("leva c", "usar -> em c", "q:seta"),
    ("leva c", "compilar vários arquivos de uma vez com make", "q:makefile"),
    ("leva c", "parâmetros da linha de comando no main", "q:argc"),
    ("leva c", "passar uma função como parâmetro em c", "q:ponteiro de função"),
    ("leva c", "escrever além do tamanho do vetor", "q:buffer overflow"),
    ("leva c", "achar onde o programa c trava passo a passo", "q:gdb"),
    ("leva c", "ordenar um vetor em c sem escrever o algoritmo", "q:qsort"),
    # Leva C++: escritas ANTES de pôr os porquês e o vocabulário.
    ("leva c++", "o que o c++ tem a mais que o c", "q:diferença entre c e c++"),
    ("leva c++", "lista que cresce sozinha em c++", "q:vector"),
    ("leva c++", "função com o mesmo nome e parâmetros diferentes", "q:sobrecarga de função"),
    ("leva c++", "método que roda quando o objeto é criado", "q:construtor"),
    ("leva c++", "classe filha que reaproveita a classe mãe em c++", "q:herança"),
    ("leva c++", "ponteiro que libera a memória sozinho", "q:ponteiro inteligente"),
    ("leva c++", "unique_ptr e shared_ptr", "q:ponteiro inteligente"),
    ("leva c++", "função que funciona para qualquer tipo em c++", "q:template"),
    ("leva c++", "dicionário em c++", "q:map"),
    ("leva c++", "try catch em c++", "q:exceções"),
    ("leva c++", "std::move", "q:movimento"),
    ("leva c++", "evitar que duas threads mexam no mesmo dado em c++", "q:mutex"),
    ("leva c++", "novidades do c++20", "q:mudou no c++11|c++20"),
    ("leva c++", "using namespace std", "q:namespace"),
    ("leva c++", "ordenar um vector", "q:ordenar um vector"),
    # Leva utilidades: escritas antes dos porquês, com o jeito de quem pede ajuda.
    ("leva utilidades", "apaguei um texto sem querer, como volto", "q:desfazer"),
    ("leva utilidades", "meu notebook travou e nenhum programa responde", "q:gerenciador de tarefas"),
    ("leva utilidades", "deixar duas janelas uma do lado da outra", "q:metade da tela"),
    ("leva utilidades", "o print que eu tirei foi parar onde", "q:print da tela inteira"),
    ("leva utilidades", "trocar o nome de uma pasta no linux", "q:mover ou renomear"),
    ("leva utilidades", "o script diz permission denied", "q:permissão de execução"),
    ("leva utilidades", "como fecho o nano salvando", "q:editar um arquivo de texto"),
    ("leva utilidades", "o disco do servidor encheu, como descubro", "q:espaço livre"),
    ("leva utilidades", "ver as últimas linhas de um log", "q:começo ou o fim"),
    ("leva utilidades", "120 km/h em milhas", "q:milhas por hora"),
    ("leva utilidades", "forno a 180 graus em fahrenheit", "q:celsius para fahrenheit"),
    ("leva utilidades", "quanto pesa uma xícara de farinha de trigo", "q:farinha"),
    ("leva utilidades", "uma tv de 55 polegadas tem quantos cm", "q:tela de 50 polegadas"),
    ("leva utilidades", "pneu com 32 libras em bar", "q:psi"),
    ("leva utilidades", "um terreno de 2 hectares tem quantos metros", "q:hectare"),
    # Leva idiomas: escritas antes da teia. "texto:" confere a resposta trabalhada.
    ("leva idiomas", "o que significa trampo", "q:trampo"),
    ("leva idiomas", "o que quer dizer bué em angola", "q:bué"),
    ("leva idiomas", "o que é grana", "texto:se diz «"),
    ("leva idiomas", "o que é bacano", "q:bacano"),
    ("leva idiomas", "uai é o quê", "q:uai"),
    ("leva idiomas", "o que significa busão", "q:busão"),
    ("leva idiomas", "como se diz dinheiro em portugal", "tipo:conhecimento"),
    ("leva idiomas", "como se diz obrigado em timor", "tipo:conhecimento"),
    ("leva idiomas", 'quais as variações de "aldeia" em português?', "texto:tabanka"),
    ("leva idiomas", "quando usar crase", "q:crase"),
    ("leva idiomas", "o que mudou com o acordo ortográfico", "q:acordo"),
    ("leva idiomas", "qual a diferença entre mas e mais", "q:mas"),
    ("leva idiomas", "por que se escreve com hífen", "q:hífen|acordo"),
    # Contexto (2.2): a 2ª pergunta segue a 1ª na mesma conversa (SEGUIR). Escritas antes do código.
    ("contexto", "o que é normalização de banco de dados", "q:normalização"),
    ("contexto", "e a segunda forma normal?", "q:2fn"),
    ("contexto", "o que é git", "q:git"),
    ("contexto", "e como salvo uma versão do código?", "q:commit"),
    ("contexto", "como criar uma lista em python", "q:lista"),
    ("contexto", "e pegar só os 3 primeiros caracteres de um texto?", "q:fatiar"),
    ("contexto", "o que é ponteiro em c", "q:ponteiro"),
    ("contexto", "e como acesso o campo de uma struct por ele?", "q:seta"),
    ("contexto", "como usar group by", "q:group by"),
    ("contexto", "e numerar as linhas do resultado?", "q:row_number"),
    ("contexto", "o que é commit e rollback", "q:transação|commit"),
    ("contexto", "como tirar print no windows", "q:print"),
    ("social", "oi, tudo bem?", "tipo:social"),
    ("social", "obrigado!", "tipo:social"),
    ("social", "valeu, ajudou muito", "tipo:social"),
    ("conversa", "o que é null?", "q:null"),
    ("conversa", "e o limit?", "q:limitar", ),
    ("conversa", "não entendi", "fundo"),
    # 2.6: jeitos de ensinar do addon de compreensão. Ficam no FIM porque o que
    # o dono ensina passa na frente dos addons nas perguntas seguintes.
    ("ensino", "a partir de agora a senha do wifi é casa456", "tipo:ensino"),
    ("ensino", "qual a senha do wifi?", "texto:casa456"),
    ("ensino", "Anota aí: levar o carro na revisão em março", "tipo:ensino"),
    ("ensino", "vc sabe qdo é a revisão do carro", "texto:março"),
    ("ensino", "fica sabendo que o aniversário da Ana é em 12 de maio", "tipo:ensino"),
    ("ensino", "qnd é o niver da Ana?", "texto:12 de maio"),
]
SEGUIR = {"e o limit?", "não entendi", "e a segunda forma normal?",
          "e como salvo uma versão do código?", "e pegar só os 3 primeiros caracteres de um texto?",
          "e como acesso o campo de uma struct por ele?", "e numerar as linhas do resultado?",
          "como tirar print no windows"}


def confere(r: dict, esperado: str) -> bool:
    msg = r["mensagem"]
    tipo = msg["meta"].get("tipo")
    fontes = msg["meta"].get("fontes") or []
    titulo = (fontes[0].get("titulo") or "").lower() if fontes else ""
    if esperado == "fundo":   # "não entendi": foi mais fundo, não repetiu
        return msg["texto"].startswith(("Vou explicar o porquê", "Vou pela base"))
    if esperado == "panorama":
        return " encontrei" in msg["texto"][:200]
    if esperado.startswith("texto:"):
        return esperado[6:] in msg["texto"]
    if esperado.startswith("tipo:"):
        return tipo == esperado[5:]
    if esperado.startswith("!q:"):
        return not fontes or esperado[3:] not in titulo
    return any(alvo in titulo for alvo in esperado[2:].split("|"))


BASE_PESSOAL = Path(__file__).parent / "dados" / "base_pessoal.json"


def rodar(assistente: Assistente, casos: list, args) -> list[tuple[str, str]]:
    """Roda os casos e imprime cada um. Devolve as falhas como (grupo, pergunta)."""
    falhas, conversa, grupo_atual = [], None, None
    for grupo, pergunta, esperado in casos:
        if pergunta not in SEGUIR:
            conversa = None
        r = assistente.responder(pergunta, conversa_id=conversa, busca=args.busca,
                                 resposta=args.resposta)
        conversa = r["conversa_id"] if "conversa_id" in r else r["mensagem"].get("conversa_id")
        ok = confere(r, esperado)
        fontes = r["mensagem"]["meta"].get("fontes") or []
        obtido = (fontes[0]["titulo"] if fontes else r["mensagem"]["meta"].get("tipo"))
        if grupo != grupo_atual:
            print(f"\n[{grupo}]")
            grupo_atual = grupo
        print(f"  {'ok ' if ok else 'ERR'} {pergunta!r:50} → {obtido}")
        if not ok:
            falhas.append((grupo, pergunta))
            if args.verbose:
                print("      " + r["mensagem"]["texto"][:160].replace("\n", " "))
    return falhas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("loja", type=Path)
    ap.add_argument("--busca", default="fuzzy")
    ap.add_argument("--resposta", default="trabalhada")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--limiar", type=float,
                    help="troca o limiar da busca escolhida só nesta rodada (ex.: 0.18)")
    ap.add_argument("--pessoal", action="store_true",
                    help="2.7: roda a base PESSOAL (ferramentas/dados/base_pessoal.json): "
                         "fatos ensinados pelo dono e perguntas sobre eles, com os mesmos addons")
    args = ap.parse_args()
    if args.limiar is not None:
        BUSCAS[args.busca].limiar = args.limiar

    assistente = Assistente(Banco(str(Path(tempfile.mkdtemp()) / "homologacao.db")))
    for id_ in ADDONS:
        assistente.instalar_addon((args.loja / "addons" / f"{id_}.aprendiz").read_bytes())

    casos = CASOS
    if args.pessoal:
        # O dono ensina como ensinaria pela tela (pergunta + resposta), por cima
        # dos addons: é o uso principal do Aprendiz.
        base = json.loads(BASE_PESSOAL.read_text(encoding="utf-8"))
        for fato in base["fatos"]:
            assistente.ensinar(fato["conteudo"], pergunta=fato["pergunta"])
        casos = [tuple(c) for c in base["casos"]]

    falhas = rodar(assistente, casos, args)
    print(f"\n{len(casos) - len(falhas)}/{len(casos)} ok")
    sem_resposta = [c for c in casos if c[0] == "sem resposta"]
    if sem_resposta:
        inventou = sum(1 for g, _ in falhas if g == "sem resposta")
        print(f"sem resposta: recusou {len(sem_resposta) - inventou}/{len(sem_resposta)}, "
              f"inventou {inventou}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
