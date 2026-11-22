param([Parameter(Mandatory=$true)][string]$Bundle,[Parameter(Mandatory=$true)][string]$MakeAppx,[string]$Python="python",[string]$Identity=(Join-Path $PSScriptRoot "identity.json"))
$details=Get-Content -LiteralPath $Identity -Raw | ConvertFrom-Json
if ($details.name -like "PASTE_*" -or $details.publisher -like "PASTE_*") { throw "Copy your real Product identity values from Partner Center into identity.json first." }
$project=Join-Path $PSScriptRoot "source"
& $Python (Join-Path $project "scripts/build_store.py") --bundle $Bundle --makeappx $MakeAppx --name $details.name --publisher $details.publisher --publisher-display-name $details.publisherDisplayName --version $details.version --output (Join-Path $PSScriptRoot "Spandy-Shows-Store.msix")
if ($LASTEXITCODE) { throw "Store packaging failed." }
