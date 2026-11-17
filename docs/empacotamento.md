# Instalação, executável e problemas comuns

## O que os scripts fazem

| Script | Função |
|---|---|
| `instalar.sh` | Confere o Python; se faltar, instala pelo gerenciador de pacotes (pedindo sudo, root ou janela de senha); cria `.venv` e baixa as dependências |
| `instalar.bat` → `ferramentas/instalar-windows.ps1` | Confere o Python; se faltar, baixa do python.org e instala (UAC; sem UAC, só para o usuário); cria `.venv` e baixa as dependências |
| `executar.sh` / `executar.bat` | Abre o Aprendiz usando o `.venv` |
| `empacotar.sh` / `empacotar.bat` | Gera o executável com o PyInstaller |

Dependências (cerca de 15 MB no total):

- **fastapi**: rotas da API
- **uvicorn**: servidor HTTP
- **rapidfuzz**: similaridade de texto (núcleo em C++)

Opcional: **pywebview**, para janela nativa (`--janela-nativa`).

## Executável (PyInstaller)

O PyInstaller junta o seu código, as bibliotecas e o próprio interpretador Python numa pasta.
Os pontos de atenção que os scripts já tratam:

- **`--add-data aprendiz/web`**: os arquivos da interface não são Python, então é preciso
  incluí-los explicitamente. (No Windows o separador é `;`, no Linux/macOS é `:`.)
- **`--collect-submodules uvicorn`**: o uvicorn importa partes de si mesmo dinamicamente,
  e o PyInstaller não as encontra sozinho.
- **`--windowed`** (só no Windows): não abre a janela preta do console.
- **`iniciar.py`**: o PyInstaller precisa de um arquivo de entrada, e não aceita `-m`.

Gere o executável em cada sistema operacional de destino: não existe compilação cruzada.

## Verificador

`ferramentas/verificar.py` testa Python, SQLite/FTS5, dependências e um chat completo
numa pasta temporária. O CI usa o mesmo script. Com `--executavel caminho` ele testa o
executável do PyInstaller.

## Encerramento automático

A interface envia um sinal a cada 10 s (`POST /api/sinal`). Se os sinais param por 90 s
(janela ou aba fechada), o app encerra. Isso evita processos esquecidos em segundo plano,
principalmente no executável do Windows, que não tem console.

## Problemas comuns

**Linux: "Não consegui permissão de administrador"**
O instalador tentou o sudo, a senha do root e a janela de senha do sistema, e nenhum
funcionou. Peça a quem administra o computador para rodar o comando que o instalador mostra
(por exemplo, `apt-get install python3 python3-venv`). Depois, rode o instalador de novo.

**"Permission denied" ao rodar `./instalar.sh`**
O arquivo perdeu a permissão de execução (acontece ao enviar pelo site do GitHub ou baixar
como .zip). Use `bash instalar.sh`, que funciona sempre.

**Windows: o instalador fecha ou o PowerShell é bloqueado**
Algumas empresas bloqueiam scripts PowerShell por política de grupo. Nesse caso, instale o
Python manualmente pelo python.org e rode `instalar.bat` de novo. Para usar uma versão
específica do Python: `set PYTHON=C:\caminho\python.exe` antes de rodar `instalar.bat`.

**A janela abre no navegador comum em vez de uma janela de app**
Nenhum Chromium foi encontrado (Chrome, Chromium, Edge ou Brave). Instale um deles ou
use `bash instalar.sh --janela-nativa`.

**Porta ocupada**
Se a 8765 estiver em uso, outra porta é escolhida automaticamente. Para escolher uma:
`bash executar.sh --porta 9000`.

**Quero começar do zero**
Apague o arquivo `aprendiz.db` da pasta de dados (veja o README). Na próxima execução,
o banco de linguagem inicial é recriado.

**Máquina muito limitada**
Use `bash executar.sh --modo navegador` e mantenha o algoritmo BM25: ele roda dentro do
SQLite e praticamente não usa memória.
