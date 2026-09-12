param(
    [Parameter(Mandatory = $true)]
    [string]$BucketName,

    [string]$Prefix = "blender",

    [string]$Destination = "build-assets/blender"
)

$ErrorActionPreference = "Stop"

$requiredFiles = @(
    "blender-2.49b-linux-glibc236-py26-x86_64.tar.bz2",
    "blender-2.79b-linux-glibc219-x86_64.tar.bz2",
    "blender-3.6.9-linux-x64.tar.xz",
    "blender-4.5.5-linux-x64.tar.xz",
    "SHA256SUMS"
)

New-Item -ItemType Directory -Force -Path $Destination | Out-Null

foreach ($fileName in $requiredFiles) {
    $source = "s3://$BucketName/$Prefix/$fileName"
    $target = Join-Path $Destination $fileName
    & aws s3 cp $source $target --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to download $source"
    }
}

$expectedHashes = @{}
$checksumPath = Join-Path $Destination "SHA256SUMS"
foreach ($line in Get-Content -LiteralPath $checksumPath) {
    if ($line -notmatch '^([a-fA-F0-9]{64})\s+\*?(.+)$') {
        throw "Invalid SHA256SUMS line: $line"
    }
    $expectedHashes[$Matches[2]] = $Matches[1].ToLowerInvariant()
}

foreach ($fileName in $requiredFiles | Where-Object { $_ -ne "SHA256SUMS" }) {
    if (-not $expectedHashes.ContainsKey($fileName)) {
        throw "SHA256SUMS does not contain $fileName"
    }
    $actualHash = (Get-FileHash -LiteralPath (Join-Path $Destination $fileName) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHashes[$fileName]) {
        throw "SHA-256 mismatch for $fileName"
    }
    Write-Host "$fileName`: OK"
}
