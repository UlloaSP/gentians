# Ejecuta benchmarks oficiales de GENTIANS con timeout por benchmark.
# Fuente: benchmarks/run_examples.sh, adaptado a PowerShell y CLI actual
# (--verbosity en vez de --verbose).

[CmdletBinding()]
param(
    # Limite por benchmark. Por defecto: 10 segundos.
    [int]$TimeoutSeconds = 10,

    # Carpeta de salida para logs y resumen.
    [string]$OutputDir = ".\benchmark_runs",

    # Ejecuta solo benchmarks cuyo nombre contenga este texto.
    # Ejemplo: -Only hamming
    [string]$Only = "",

    # Muestra lista de benchmarks y sale sin ejecutar.
    [switch]$ListOnly,

    # Para tras primer fallo/timeout.
    [switch]$StopOnFailure
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$GentiansExe = Join-Path $RepoRoot ".venv\Scripts\gentians.exe"
if (-not (Test-Path $GentiansExe)) {
    $GentiansExe = "gentians"
}

$FullOutputDir = Join-Path $RepoRoot $OutputDir
New-Item -ItemType Directory -Force -Path $FullOutputDir | Out-Null

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

function New-Benchmark {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    [pscustomobject]@{
        Name = $Name
        Arguments = $Arguments
    }
}

function Invoke-BenchmarkLimited {
    param(
        [pscustomobject]$Benchmark
    )

    $SafeName = ($Benchmark.Name -replace '[^a-zA-Z0-9_-]', '_').Trim('_')
    $StdOut = Join-Path $FullOutputDir "$SafeName.out.log"
    $StdErr = Join-Path $FullOutputDir "$SafeName.err.log"

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host $Benchmark.Name -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host "$GentiansExe $($Benchmark.Arguments -join ' ')" -ForegroundColor Gray

    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $GentiansExe
    $StartInfo.WorkingDirectory = $RepoRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true
    $StartInfo.Arguments = ConvertTo-ProcessArgumentString $Benchmark.Arguments

    $Process = [System.Diagnostics.Process]::new()
    $Process.StartInfo = $StartInfo

    $StartTime = Get-Date
    [void]$Process.Start()
    $StdOutTask = $Process.StandardOutput.ReadToEndAsync()
    $StdErrTask = $Process.StandardError.ReadToEndAsync()

    $Finished = $Process.WaitForExit($TimeoutSeconds * 1000)
    $TimedOut = -not $Finished
    if ($TimedOut) {
        try {
            Stop-Process -Id $Process.Id -Force
        } catch {
            Write-Host "No se pudo matar proceso $($Process.Id): $_" -ForegroundColor Red
        }
    } else {
        $Process.WaitForExit()
    }

    $EndTime = Get-Date
    $Elapsed = [Math]::Round(($EndTime - $StartTime).TotalSeconds, 3)

    Set-Content -LiteralPath $StdOut -Value $StdOutTask.Result -Encoding UTF8
    Set-Content -LiteralPath $StdErr -Value $StdErrTask.Result -Encoding UTF8

    $ExitCode = if ($TimedOut) { $null } else { $Process.ExitCode }
    $Status = if ($TimedOut) {
        "TIMEOUT"
    } elseif ($ExitCode -eq 0) {
        "OK"
    } else {
        "FAIL"
    }

    if ($Status -eq "OK") {
        Write-Host "OK ${Elapsed}s" -ForegroundColor Green
    } elseif ($Status -eq "TIMEOUT") {
        Write-Host "TIMEOUT ${Elapsed}s" -ForegroundColor Yellow
    } else {
        Write-Host "FAIL exit=$ExitCode ${Elapsed}s" -ForegroundColor Red
    }

    if (Test-Path $StdOut) {
        Write-Host "stdout tail:" -ForegroundColor Yellow
        Get-Content -LiteralPath $StdOut -Tail 12 | ForEach-Object { Write-Host $_ }
    }
    if ($Status -eq "FAIL" -and (Test-Path $StdErr)) {
        Write-Host "stderr tail:" -ForegroundColor Yellow
        Get-Content -LiteralPath $StdErr -Tail 12 | ForEach-Object { Write-Host $_ }
    }

    if ($StopOnFailure -and $Status -ne "OK") {
        throw "$($Benchmark.Name) -> $Status"
    }

    [pscustomobject]@{
        Name = $Benchmark.Name
        Status = $Status
        ExitCode = $ExitCode
        Seconds = $Elapsed
        StdOut = $StdOut
        StdErr = $StdErr
        Command = "$GentiansExe $($Benchmark.Arguments -join ' ')"
    }
}

# Benchmarks oficiales, adaptados desde benchmarks/run_examples.sh.
$Benchmarks = @(
    New-Benchmark "4queens" @("-e", "4queens", "-d", "5", "--verbosity", "1", "--arithm", "add", "sub", "--comparison", "lt", "--variables", "3")
    New-Benchmark "adjacent_to_red" @("-e", "adjacent_to_red", "-d", "4", "--verbosity", "1")
    New-Benchmark "clique" @("-e", "clique", "-d", "7", "--comparison", "neq", "--verbosity", "1", "--variables", "2")
    New-Benchmark "coin" @("-e", "coin", "--verbosity", "1")
    New-Benchmark "coloring" @("-e", "coloring", "-dh", "3", "-d", "4", "--verbosity", "1")
    New-Benchmark "even_odd" @("-e", "even_odd", "--verbosity", "1")
    New-Benchmark "grandparent" @("-e", "grandparent", "--verbosity", "1")
    New-Benchmark "sudoku" @("-e", "sudoku", "-d", "3")
    New-Benchmark "hamming_0" @("-e", "hamming_0", "-d", "3", "--aggregates", "sum(d/2)", "--comparison", "neq", "--verbosity", "1", "--variables", "4")
    New-Benchmark "hamming_1" @("-e", "hamming_1", "-d", "3", "--aggregates", "sum(d/2)", "--comparison", "neq", "--verbosity", "1", "--variables", "4")
    New-Benchmark "hamming_0_count_ua" @("-e", "hamming_0", "-d", "3", "--aggregates", "sum(d/2)", "count(d/2)", "--comparison", "neq", "--verbosity", "2", "--variables", "4", "-ua")
    New-Benchmark "hamming_1_count_ua" @("-e", "hamming_1", "-d", "3", "--aggregates", "sum(d/2)", "count(d/2)", "--comparison", "neq", "--verbosity", "2", "--variables", "4", "-ua")
    New-Benchmark "subset_sum_count_ua" @("-e", "subset_sum", "-d", "3", "--aggregates", "sum(el/1)", "count(el/1)", "--comparison", "neq", "--verbosity", "1", "-ua")
    New-Benchmark "subset_sum_count_compare_ua" @("-e", "subset_sum", "-d", "3", "--aggregates", "sum(el/1)", "count(el/1)", "--comparison", "neq", "geq", "leq", "--verbosity", "1", "-ua")
    New-Benchmark "subset_sum_double" @("-e", "subset_sum_double", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "--arithm", "add", "--verbosity", "2", "--variables", "3")
    New-Benchmark "subset_sum_double_ua" @("-e", "subset_sum_double", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "--arithm", "add", "--verbosity", "2", "--variables", "3", "-ua")
    New-Benchmark "subset_sum_double_count_ua" @("-e", "subset_sum_double", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "count(el/2)", "count(el/2)", "--arithm", "add", "--verbosity", "2", "--variables", "3", "-ua")
    New-Benchmark "subset_sum_double_prod" @("-e", "subset_sum_double_and_prod", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "--arithm", "add", "mul", "sub", "--verbosity", "1", "--variables", "5")
    New-Benchmark "subset_sum_double_prod_ua" @("-e", "subset_sum_double_and_prod", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "--arithm", "add", "mul", "sub", "--verbosity", "1", "--variables", "5", "-ua")
    New-Benchmark "subset_sum_triple" @("-e", "subset_sum_triple", "-d", "4", "--aggregates", "sum(el/3)", "sum(el/3)", "sum(el/3)", "--verbosity", "1", "--variables", "4")
    New-Benchmark "set_partition_sum_new" @("-e", "set_partition_sum_new", "-d", "4", "--verbosity", "2", "--comparison", "neq", "neq", "--variables", "4", "--aggregates", "sum(p/2)", "-ua")
    New-Benchmark "set_partition_sum" @("-e", "set_partition_sum", "-d", "4", "--verbosity", "1", "--comparison", "neq", "neq", "--variables", "4", "--aggregates", "sum(p/2)", "-ua")
)

if ($Only -ne "") {
    $Benchmarks = @($Benchmarks | Where-Object { $_.Name -like "*$Only*" })
}

if ($ListOnly) {
    $Benchmarks | ForEach-Object {
        Write-Host "$($_.Name): gentians $($_.Arguments -join ' ')"
    }
    return
}

if ($Benchmarks.Count -eq 0) {
    throw "No benchmarks matched Only='$Only'"
}

Write-Host "Gentians: $GentiansExe" -ForegroundColor Gray
Write-Host "Benchmarks: $($Benchmarks.Count)" -ForegroundColor Gray
Write-Host "Timeout por benchmark: $TimeoutSeconds segundos" -ForegroundColor Gray
Write-Host "Output: $FullOutputDir" -ForegroundColor Gray

$Results = foreach ($Benchmark in $Benchmarks) {
    Invoke-BenchmarkLimited $Benchmark
}

$SummaryCsv = Join-Path $FullOutputDir "summary.csv"
$Results | Export-Csv -LiteralPath $SummaryCsv -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "Resumen" -ForegroundColor Cyan
$Results | Group-Object Status | ForEach-Object {
    Write-Host "$($_.Name): $($_.Count)"
}
Write-Host "CSV: $SummaryCsv" -ForegroundColor Green
