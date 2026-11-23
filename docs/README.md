# Documentação do Aprendiz

A documentação está dividida em três pastas, pelo que você quer fazer:

| Pasta | Para quê |
|---|---|
| [`estudo/`](estudo/) | Entender **como a IA do Aprendiz funciona**, com as contas feitas à mão |
| [`guias/`](guias/) | **Fazer** algo: criar um addon, criar um algoritmo, instalar e empacotar |
| [`referencia/`](referencia/) | **Consultar** o mapa do projeto: camadas, tabelas e todos os arquivos |

## Por onde começar

| Você é… | Leia nesta ordem |
|---|---|
| **Iniciante em IA** | [Algoritmos](estudo/algoritmos.md) (seções 1 a 4) → [Linguagem](estudo/linguagem.md) → [Monitor](estudo/monitor.md), usando o app no nível Iniciante |
| **Dev que quer entender PLN e busca** | [Arquitetura](referencia/arquitetura.md) → [Linguagem](estudo/linguagem.md) → [Algoritmos](estudo/algoritmos.md) → [Criar um algoritmo](guias/criar-algoritmo.md) |
| **Estudante de aprendizado de máquina** | [Algoritmos](estudo/algoritmos.md) (seção 5, busca Calibrada) → [Monitor](estudo/monitor.md) (parâmetros e fluxo ao vivo) → [Testes](estudo/testes.md) (como testar um modelo) |
| **Quem vai criar addons** | [Addons](guias/addons.md) → [Compreensão](estudo/compreensao.md) → [Revisão](estudo/revisao.md) |
| **Quem vai distribuir o app** | [Empacotamento](guias/empacotamento.md) |

## Todos os documentos

### Estudo: como a IA funciona

| Documento | Conteúdo |
|---|---|
| [Algoritmos](estudo/algoritmos.md) | BM25, TF-IDF, Fuzzy, Híbrido e Calibrado; respostas Direta, Extrativa e Trabalhada; homologação e benchmark |
| [Linguagem](estudo/linguagem.md) | O pipeline de PLN: normalização, correção, sinônimos, stopwords, radicais, intenções |
| [Compreensão](estudo/compreensao.md) | Addons de compreensão e vetores: lemas, tipos de pergunta, padrões de frase, diálogo, recomendação |
| [Revisão](estudo/revisao.md) | Addons de norma: vocabulário, grafias de cada país, regras de gramática |
| [Monitor](estudo/monitor.md) | O painel técnico, os níveis Iniciante e Avançado, o fluxo ao vivo e o que conta como parâmetro |
| [Testes](estudo/testes.md) | Testes metamórficos, fuzz, invariantes, propriedades dos modelos e homologação com a loja |

### Guias: como fazer

| Documento | Conteúdo |
|---|---|
| [Addons](guias/addons.md) | O formato `.aprendiz`, como escrever e gerar um addon, teia de porquês, segurança |
| [Criar um algoritmo](guias/criar-algoritmo.md) | Os quatro passos para pôr o seu algoritmo no seletor |
| [Empacotamento](guias/empacotamento.md) | O que os instaladores fazem, o executável e problemas comuns |

### Referência: o mapa

| Documento | Conteúdo |
|---|---|
| [Arquitetura](referencia/arquitetura.md) | Camadas, decisões de projeto, caminho de uma mensagem, tabelas e migrações |
| [Estrutura](referencia/estrutura.md) | Todos os arquivos do projeto, com o papel de cada um (gerado pelo código) |

Para contribuir, veja o [guia de contribuição](../.github/CONTRIBUTING.md).
