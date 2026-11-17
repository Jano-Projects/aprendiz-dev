# =============================================================================
# Instalador do Aprendiz para Windows (chamado pelo instalar.bat).
#
# O que ele faz, sozinho:
#   1. procura um Python 3.10+ (variavel PYTHON, lancador "py", "python",
#      pastas padrao de instalacao);
#   2. se nao encontrar, AVISA e instala o Python oficial do python.org:
#        - descobre a versao estavel mais recente compativel (3.14 ou 3.13);
#        - pede permissao de ADMINISTRADOR (janela do UAC) para instalar
#          para todos os usuarios;
#        - se o UAC for recusado, instala so para o usuario atual (sem admin);
#   3. cria o ambiente virtual .venv e instala as dependencias.
#
# Opcoes (repassadas pelo instalar.bat):
#   --janela-nativa     tambem instala o pywebview
#   --dev               tambem instala pytest e PyInstaller
#   --instalar-python   instala o Python mesmo que ja exista (usado nos testes)
#
# Este arquivo usa apenas caracteres ASCII de proposito: o Windows PowerShell
# 5.1 le scripts sem BOM como ANSI e estragaria os acentos.
# =============================================================================

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"   # deixa o download muito mais rapido
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Raiz = Split-Path $PSScriptRoot -Parent
Set-Location $Raiz

$JanelaNativa = $args -contains "--janela-nativa"
$Dev = $args -contains "--dev"
$ForcarPython = $args -contains "--instalar-python"

function Info($texto)  { Write-Host "-> $texto" }
function Aviso($texto) { Write-Host "[!] $texto" -ForegroundColor Yellow }
function Falhar($texto) {
    Write-Host "[X] $texto" -ForegroundColor Red
    exit 1
}

# -------------------------------------------------------------------- Python
function Testar-Python([string]$exe) {
    # O Python existe, e 3.10+ e tem SQLite com FTS5?
    if (-not $exe -or -not (Test-Path $exe)) { return $false }
    if ($exe -like "*\WindowsApps\*") { return $false }   # atalho da Microsoft Store
    $codigo = "import sys,sqlite3; assert sys.version_info>=(3,10); " +
              "sqlite3.connect(':memory:').execute('create virtual table t using fts5(x)')"
    & $exe -c $codigo 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Caminho-Real([string]$comando, [string[]]$argumentos) {
    # Pergunta ao proprio Python onde ele esta (resolve "py -3" e "python").
    try {
        $saida = & $comando @argumentos -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $saida) { return ($saida | Select-Object -First 1).Trim() }
    } catch { }
    return $null
}

function Encontrar-Python {
    $candidatos = @()
    if ($env:PYTHON) {
        $c = Caminho-Real $env:PYTHON @()
        if ($c) { $candidatos += $c }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) { $candidatos += Caminho-Real "py" @("-3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidatos += Caminho-Real "python" @() }
    $padroes = @(
        "$env:LocalAppData\Programs\Python\Python3*\python.exe",
        "$env:ProgramFiles\Python3*\python.exe"
    )
    foreach ($p in $padroes) {
        $candidatos += Get-ChildItem $p -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | ForEach-Object { $_.FullName }
    }
    foreach ($c in $candidatos) {
        if (Testar-Python $c) { return $c }
    }
    return $null
}

function Descobrir-Instalador {
    # Lista as versoes publicadas no python.org e escolhe a mais nova da serie
    # 3.14 ou 3.13 que tenha instalador para esta arquitetura.
    $arq = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "amd64" }
    $base = "https://www.python.org/ftp/python/"
    try {
        $pagina = (Invoke-WebRequest $base -UseBasicParsing -TimeoutSec 30).Content
    } catch {
        Falhar "Nao consegui acessar o python.org. Verifique a internet."
    }
    $versoes = [regex]::Matches($pagina, 'href="(3\.1[34]\.\d+)/"') |
        ForEach-Object { [version]($_.Groups[1].Value) } |
        Sort-Object -Descending -Unique
    foreach ($v in $versoes) {
        $url = "$base$v/python-$v-$arq.exe"
        try {
            Invoke-WebRequest $url -Method Head -UseBasicParsing -TimeoutSec 30 | Out-Null
            return @{ Versao = $v; Url = $url }
        } catch { }   # versao sem instalador (ex.: so correcoes de seguranca)
    }
    Falhar "Nao encontrei um instalador do Python no python.org."
}

function Localizar-Instalado([version]$v) {
    # Onde o Python $v foi instalado? Em vez de adivinhar a pasta, perguntamos
    # ao Windows: todo instalador oficial registra o caminho no Registro
    # (padrao PEP 514), e e assim que o lancador "py" encontra o Python.
    # Isso importa porque, se ja existe outro Python da mesma serie (ex.: 3.14),
    # o instalador ATUALIZA essa instalacao na pasta onde ela ja esta.
    $serie = "$($v.Major).$($v.Minor)"
    $chaves = @(
        "HKLM:\SOFTWARE\Python\PythonCore\$serie\InstallPath",
        "HKCU:\SOFTWARE\Python\PythonCore\$serie\InstallPath",
        "HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore\$serie\InstallPath"
    )
    foreach ($chave in $chaves) {
        $dados = Get-ItemProperty $chave -ErrorAction SilentlyContinue
        if (-not $dados) { continue }
        $exe = $dados.ExecutablePath
        if (-not $exe -and $dados.'(default)') { $exe = Join-Path $dados.'(default)' "python.exe" }
        if (Testar-Python $exe) { return $exe }
    }
    # Plano B: o lancador "py" (instalado junto, em C:\Windows).
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $exe = Caminho-Real "py" @("-$serie")
        if (Testar-Python $exe) { return $exe }
    }
    return $null
}

function Mostrar-Log([string]$log) {
    # Em caso de falha, mostra o final do log do instalador oficial.
    if (Test-Path $log) {
        Aviso "Ultimas linhas do log do instalador ($log):"
        Get-Content $log -Tail 15 | ForEach-Object { Write-Host "    $_" }
    }
}

function Instalar-Python {
    Write-Host ""
    Write-Host "+--------------------------------------------------------------+" -ForegroundColor Yellow
    Write-Host "|  E PRECISO INSTALAR O PYTHON                                 |" -ForegroundColor Yellow
    Write-Host "|  O Windows vai pedir permissao de ADMINISTRADOR (UAC).       |" -ForegroundColor Yellow
    Write-Host "|  Clique em 'Sim' para continuar.                             |" -ForegroundColor Yellow
    Write-Host "+--------------------------------------------------------------+" -ForegroundColor Yellow
    Write-Host ""

    $alvo = Descobrir-Instalador
    $v = $alvo.Versao
    $instalador = Join-Path $env:TEMP "python-$v-instalador.exe"
    Info "Baixando Python $v (python.org)"
    try {
        Invoke-WebRequest $alvo.Url -OutFile $instalador -UseBasicParsing -TimeoutSec 600
    } catch {
        Falhar "Falha ao baixar o Python: $($_.Exception.Message)"
    }

    $log = Join-Path $env:TEMP "python-$v-instalador.log"
    $comum = @("/quiet", "/log", "`"$log`"", "PrependPath=1", "Include_launcher=1",
               "Include_test=0", "Include_doc=0")
    $exe = $null

    Info "Instalando Python $v para todos os usuarios (aguarde a janela do UAC)"
    try {
        $p = Start-Process $instalador -ArgumentList ($comum + "InstallAllUsers=1") `
            -Verb RunAs -Wait -PassThru -ErrorAction Stop
        if ($p.ExitCode -ne 0) { Aviso "O instalador terminou com codigo $($p.ExitCode)." }
        $exe = Localizar-Instalado $v
    } catch {
        Aviso "Permissao de administrador recusada."
    }

    if (-not $exe) {
        Info "Instalando Python $v apenas para o seu usuario (sem administrador)"
        $p = Start-Process $instalador -ArgumentList ($comum + "InstallAllUsers=0") -Wait -PassThru
        if ($p.ExitCode -ne 0) { Aviso "O instalador terminou com codigo $($p.ExitCode)." }
        $exe = Localizar-Instalado $v
    }

    Remove-Item $instalador -ErrorAction SilentlyContinue
    if (-not $exe) {
        Mostrar-Log $log
        Falhar "A instalacao do Python nao funcionou."
    }
    Info "Python instalado em $exe"
    return $exe
}

# ==================================================================== inicio
Write-Host "Instalador do Aprendiz" -ForegroundColor Cyan
Info "Procurando o Python"

$py = if ($ForcarPython) { $null } else { Encontrar-Python }
if (-not $py) {
    if (-not $ForcarPython) { Aviso "Python 3.10+ nao encontrado neste computador." }
    $py = Instalar-Python
}
$versao = & $py -c "import platform; print(platform.python_version())"
Info "Usando Python $versao em $py"

Info "Criando ambiente virtual em .venv"
if (Test-Path ".venv") { Remove-Item ".venv" -Recurse -Force }
& $py -m venv .venv
if ($LASTEXITCODE -ne 0) { Falhar "Nao consegui criar o ambiente virtual." }
$vpy = Join-Path $Raiz ".venv\Scripts\python.exe"

Info "Atualizando o pip"
& $vpy -m pip install --upgrade pip --quiet --disable-pip-version-check

Info "Baixando e instalando dependencias"
& $vpy -m pip install -r requirements.txt --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Falhar "Falha ao instalar as dependencias. Verifique a internet." }

if ($JanelaNativa) {
    Info "Instalando suporte a janela nativa (pywebview)"
    & $vpy -m pip install -r requirements-janela.txt --quiet --disable-pip-version-check
}
if ($Dev) {
    Info "Instalando ferramentas de desenvolvimento"
    & $vpy -m pip install -r requirements-dev.txt --quiet --disable-pip-version-check
}

Info "Conferindo a instalacao"
& $vpy -c "import fastapi, uvicorn, rapidfuzz, aprendiz.core"
if ($LASTEXITCODE -ne 0) { Falhar "Algo deu errado na instalacao." }

Write-Host ""
Write-Host "[OK] Instalacao concluida! Para abrir o Aprendiz, rode executar.bat" -ForegroundColor Green
exit 0
