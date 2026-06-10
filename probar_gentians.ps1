# Script de prueba para GENTIANS.
# Ejecuta varios casos pequenos desde terminal, creando archivos ASP temporales.
# Objetivo: tocar opciones principales sin dejar procesos largos.

[CmdletBinding()]
param(
    # Tiempo maximo por ejecucion de gentians. Sube esto si quieres busquedas mas largas.
    [int]$TimeoutSeconds = 20,

    # Carpeta donde se escriben tareas y logs de prueba.
    [string]$WorkDir = ".\gentians_playground",

    # Si esta activo, deja de ejecutar tras primer fallo.
    [switch]$StopOnFailure
)

$ErrorActionPreference = "Stop"

# Resolver raiz del repo aunque lances el script desde otra carpeta.
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

# Preferir ejecutable instalado en venv local. Si no existe, usar comando global.
$GentiansExe = Join-Path $RepoRoot ".venv\Scripts\gentians.exe"
if (-not (Test-Path $GentiansExe)) {
    $GentiansExe = "gentians"
}

# Crear carpeta de pruebas.
$FullWorkDir = Join-Path $RepoRoot $WorkDir
New-Item -ItemType Directory -Force -Path $FullWorkDir | Out-Null

function Write-Title {
    param([string]$Text)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host $Text -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkGray
}

function Write-TaskFile {
    param(
        [string]$Name,
        [string]$Content
    )

    $Path = Join-Path $FullWorkDir $Name
    # ASCII evita BOM. Un BOM al inicio rompe clingo porque queda pegado a la
    # primera regla ASP.
    Set-Content -LiteralPath $Path -Value $Content -Encoding ASCII
    return $Path
}

function ConvertTo-ProcessArgumentString {
    param([string[]]$Arguments)

    $Quoted = foreach ($Arg in $Arguments) {
        if ($Arg -match '[\s"]') {
            '"' + ($Arg -replace '"', '\"') + '"'
        } else {
            $Arg
        }
    }
    return ($Quoted -join " ")
}

function Invoke-GentiansLimited {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    Write-Title $Name
    Write-Host "Comando:" -ForegroundColor Yellow
    Write-Host "$GentiansExe $($Arguments -join ' ')" -ForegroundColor Gray

    $SafeName = ($Name -replace '[^a-zA-Z0-9_-]', '_').Trim('_')
    $StdOut = Join-Path $FullWorkDir "$SafeName.out.log"
    $StdErr = Join-Path $FullWorkDir "$SafeName.err.log"

    # .NET Process da ExitCode fiable y permite timeout.
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $GentiansExe
    $StartInfo.WorkingDirectory = $RepoRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true
    $StartInfo.Arguments = ConvertTo-ProcessArgumentString $Arguments

    $Process = [System.Diagnostics.Process]::new()
    $Process.StartInfo = $StartInfo
    [void]$Process.Start()

    $StdOutTask = $Process.StandardOutput.ReadToEndAsync()
    $StdErrTask = $Process.StandardError.ReadToEndAsync()
    $Finished = $Process.WaitForExit($TimeoutSeconds * 1000)
    if (-not $Finished) {
        try {
            Stop-Process -Id $Process.Id -Force
        } catch {
            Write-Host "No se pudo matar proceso $($Process.Id): $_" -ForegroundColor Red
        }
        Write-Host "TIMEOUT tras $TimeoutSeconds segundos. Log parcial: $StdOut" -ForegroundColor Yellow
        Set-Content -LiteralPath $StdOut -Value $StdOutTask.Result -Encoding UTF8
        Set-Content -LiteralPath $StdErr -Value $StdErrTask.Result -Encoding UTF8
        if ($StopOnFailure) { throw "Timeout en $Name" }
        return
    }

    $Process.WaitForExit()
    Set-Content -LiteralPath $StdOut -Value $StdOutTask.Result -Encoding UTF8
    Set-Content -LiteralPath $StdErr -Value $StdErrTask.Result -Encoding UTF8

    Write-Host "Exit code: $($Process.ExitCode)" -ForegroundColor Gray
    Write-Host "stdout: $StdOut" -ForegroundColor Gray
    Write-Host "stderr: $StdErr" -ForegroundColor Gray

    # Mostrar cola del log para ver resultado sin abrir archivo.
    if (Test-Path $StdOut) {
        Write-Host "Ultimas lineas stdout:" -ForegroundColor Yellow
        Get-Content -LiteralPath $StdOut -Tail 35
    }

    if ($Process.ExitCode -ne 0) {
        Write-Host "Fallo en $Name. Revisa logs." -ForegroundColor Red
        if (Test-Path $StdErr) {
            Write-Host "stderr:" -ForegroundColor Yellow
            Get-Content -LiteralPath $StdErr -Tail 20
        }
        if ($StopOnFailure) { throw "Fallo en $Name" }
    }
}

# ---------------------------------------------------------------------------
# Caso 1: aprendizaje basico con bias manual.
# Background:
#   even(0) y prev(N,N-1) son conocimiento ya verdadero.
# Positivos:
#   queremos que existan odd(1), odd(3), even(2).
# Negativos:
#   queremos evitar even(1), even(3), odd(2).
# Bias:
#   head permite aprender even/1 y odd/1.
#   body permite usar even/1, odd/1 y prev/2.
# ---------------------------------------------------------------------------
$EvenOddManual = Write-TaskFile "01_even_odd_manual.lp" @'
even(0).
prev(1,0).
prev(2,1).
prev(3,2).

#pos({odd(1), odd(3), even(2)}, {}).
#neg({even(1)}, {}).
#neg({even(3)}, {}).
#neg({odd(2)}, {}).

#modeh(1, even, 1).
#modeh(1, odd, 1).
#modeb(1, even, 1, positive).
#modeb(1, odd, 1, positive).
#modeb(2, prev, 2, positive).
'@

Invoke-GentiansLimited "01 manual bias even/odd" @(
    "-f", $EvenOddManual,
    "-d", "3",
    "--variables", "3",
    "-s", "60",
    "-c", "2",
    "-it", "1",
    "-p", "14",
    "-itg", "60",
    "-mp", "0.25",
    "--verbosity", "1"
)

# ---------------------------------------------------------------------------
# Caso 2: mismo problema, pero con bias automatico.
# -alb=1 ignora #modeh/#modeb del archivo y extrae firmas desde background
# y ejemplos. Bueno para probar, menos controlado.
# ---------------------------------------------------------------------------
$EvenOddAuto = Write-TaskFile "02_even_odd_auto.lp" @'
even(0).
prev(1,0).
prev(2,1).
prev(3,2).

#pos({odd(1), odd(3), even(2)}, {}).
#neg({even(1)}, {}).
#neg({even(3)}, {}).
#neg({odd(2)}, {}).
'@

Invoke-GentiansLimited "02 automatic language bias -alb" @(
    "-f", $EvenOddAuto,
    "-alb", "1",
    "-d", "3",
    "--variables", "3",
    "-s", "50",
    "-c", "2",
    "-it", "1",
    "-p", "14",
    "-itg", "50",
    "--verbosity", "1"
)

# ---------------------------------------------------------------------------
# Caso 3: negacion en body.
# positive/negative en #modeb NO significa ejemplo positivo/negativo.
# Significa si ese predicado puede aparecer como literal normal o negado.
# Aqui se permite "not tails(X)" y "not heads(X)".
# ---------------------------------------------------------------------------
$Negation = Write-TaskFile "03_coin_negation.lp" @'
coin(c1).
coin(c2).
coin(c3).

#pos({heads(c1), tails(c2)}, {tails(c1), heads(c2)}).
#pos({heads(c2), tails(c3)}, {tails(c2), heads(c3)}).

#modeh(1, heads, 1).
#modeh(1, tails, 1).
#modeb(1, coin, 1, positive).
#modeb(1, heads, 1, negative).
#modeb(1, tails, 1, negative).
'@

Invoke-GentiansLimited "03 negacion en body" @(
    "-f", $Negation,
    "-d", "3",
    "--variables", "2",
    "-s", "80",
    "-c", "2",
    "-it", "1",
    "-p", "14",
    "-itg", "70",
    "--verbosity", "1"
)

# ---------------------------------------------------------------------------
# Caso 4: comparaciones y aritmetica.
# --comparison habilita operadores relacionales como neq/lt/geq.
# --arithm habilita operadores como add/sub/mul.
# Este caso intenta aprender sucesor con suma:
#   next(X,Y) :- num(X), num(Y), X + 1 = Y.
# GENTIANS no permite constantes en templates de aritmetica directamente,
# por eso damos one(1) en background y permitimos one/1 en body.
# ---------------------------------------------------------------------------
$ArithmComparison = Write-TaskFile "04_arithm_comparison.lp" @'
num(0).
num(1).
num(2).
num(3).
one(1).

#pos({next(0,1), next(1,2), next(2,3)}, {}).
#neg({next(0,2)}, {}).
#neg({next(1,3)}, {}).
#neg({next(2,2)}, {}).

#modeh(1, next, 2).
#modeb(2, num, 1, positive).
#modeb(1, one, 1, positive).
'@

Invoke-GentiansLimited "04 comparison y aritmetica" @(
    "-f", $ArithmComparison,
    "-d", "4",
    "--variables", "4",
    "-s", "100",
    "-c", "2",
    "-it", "1",
    "-p", "14",
    "-itg", "80",
    "--comparison", "neq",
    "--arithm", "add",
    "--verbosity", "1"
)

# ---------------------------------------------------------------------------
# Caso 5: agregados.
# --aggregates "sum(el/1)" permite generar #sum sobre el/1.
# Tarea pequena: aprender s(6) desde elecciones de el/1.
# ---------------------------------------------------------------------------
$Aggregates = Write-TaskFile "05_aggregates_sum.lp" @'
{el(1)}.
{el(2)}.
{el(3)}.
{el(4)}.

#pos({s(6)}, {}).
#neg({s(1)}, {}).
#neg({s(10)}, {}).

#modeh(1, s, 1).
#modeb(1, el, 1, positive).
'@

Invoke-GentiansLimited "05 agregados sum" @(
    "-f", $Aggregates,
    "-d", "2",
    "--variables", "2",
    "-s", "80",
    "-c", "1",
    "-it", "1",
    "-p", "14",
    "-itg", "60",
    "--aggregates", "sum(el/1)",
    "--verbosity", "1"
)

# ---------------------------------------------------------------------------
# Caso 6: agregados desbalanceados.
# -ua permite que la tupla agregada use menos variables que el atomo agregado.
# Para el/2 puede generar #sum{X: el(X,Y)} y tambien #sum{X,Y: el(X,Y)}.
# ---------------------------------------------------------------------------
$UnbalancedAggregates = Write-TaskFile "06_unbalanced_aggregates.lp" @'
{el(1,2)}.
{el(2,3)}.
{el(3,5)}.

#pos({s(6)}, {}).
#neg({s(2)}, {}).

#modeh(1, s, 1).
#modeb(1, el, 2, positive).
'@

Invoke-GentiansLimited "06 agregados unbalanced -ua" @(
    "-f", $UnbalancedAggregates,
    "-d", "2",
    "--variables", "3",
    "-s", "60",
    "-c", "1",
    "-it", "1",
    "-p", "14",
    "-itg", "50",
    "--aggregates", "sum(el/2)",
    "-ua",
    "--verbosity", "1"
)

# ---------------------------------------------------------------------------
# Caso 7: predicate invention.
# --invention=1 agrega predicados internos __inv_0__/1 y __inv_0__/2 al bias.
# Puede ayudar cuando target necesita concepto intermedio.
# Aqui usamos grandparent pequeño. Puede no encontrar solucion con timeout bajo,
# pero prueba que opcion corre.
# ---------------------------------------------------------------------------
$Invention = Write-TaskFile "07_predicate_invention.lp" @'
mother(a,b).
father(b,c).
mother(c,d).
father(a,e).

#pos({grandparent(a,c), grandparent(b,d)}, {}).
#neg({grandparent(a,b)}, {}).
#neg({grandparent(b,c)}, {}).

#modeh(1, grandparent, 2).
#modeb(2, mother, 2, positive).
#modeb(2, father, 2, positive).
'@

Invoke-GentiansLimited "07 predicate invention" @(
    "-f", $Invention,
    "-d", "3",
    "--variables", "3",
    "-s", "80",
    "-c", "3",
    "-it", "1",
    "-p", "14",
    "-itg", "60",
    "--invention", "1",
    "--verbosity", "1"
)

# ---------------------------------------------------------------------------
# Caso 8: ejemplo built-in.
# -e usa un ejemplo definido en gentians/example_programs.py.
# Sirve para verificar CLI sin crear archivo.
# ---------------------------------------------------------------------------
Invoke-GentiansLimited "08 built-in example coin" @(
    "-e", "coin",
    "-d", "3",
    "--variables", "2",
    "-s", "60",
    "-c", "2",
    "-it", "1",
    "-p", "14",
    "-itg", "60",
    "--verbosity", "1"
)

Write-Title "Resumen"
Write-Host "Pruebas terminadas. Archivos y logs en: $FullWorkDir" -ForegroundColor Green
Write-Host "Ajusta TimeoutSeconds, -s, -itg, -p, -d, --variables para explorar mas." -ForegroundColor Gray
