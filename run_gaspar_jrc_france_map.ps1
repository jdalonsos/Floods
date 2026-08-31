param(
    [int]$Port = 8502
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcRoot = Join-Path $projectRoot "src"
$sitePackages = Join-Path $projectRoot ".venv\\Lib\\site-packages"
$appPath = Join-Path $srcRoot "gaspar_jrc_france_map_app.py"

if (-not (Test-Path -LiteralPath $sitePackages)) {
    throw "Could not find site-packages at $sitePackages"
}

if (-not (Test-Path -LiteralPath $appPath)) {
    throw "Could not find Streamlit app at $appPath"
}

$pythonCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\\Python\\Python312\\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\\Python\\Python313\\python.exe")
)
$pythonPath = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $pythonPath) {
    throw "Could not find a local Python 3.12/3.13 interpreter under $env:LOCALAPPDATA\\Programs\\Python"
}

$pathParts = @($sitePackages, $srcRoot)
if ($env:PYTHONPATH) {
    $pathParts += $env:PYTHONPATH
}
$env:PYTHONPATH = ($pathParts -join ";")
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Launching France commune activity app on http://localhost:$Port"
& $pythonPath -m streamlit run $appPath --server.headless true --server.port $Port
