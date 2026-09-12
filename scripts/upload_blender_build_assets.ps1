param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDirectory,

    [string]$BucketName = "cg-extractor-build-artifacts-001879457662-us-east-1",

    [string]$Prefix = "blender"
)

$ErrorActionPreference = "Stop"

$archives = @(
    "blender-2.49b-linux-glibc236-py26-x86_64.tar.bz2",
    "blender-2.79b-linux-glibc219-x86_64.tar.bz2",
    "blender-3.6.9-linux-x64.tar.xz",
    "blender-4.5.5-linux-x64.tar.xz"
)

foreach ($fileName in $archives) {
    $path = Join-Path $SourceDirectory $fileName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing required Blender archive: $path"
    }
}

$checksumLines = foreach ($fileName in $archives) {
    $hash = (Get-FileHash -LiteralPath (Join-Path $SourceDirectory $fileName) -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $fileName"
}
$checksumPath = Join-Path $SourceDirectory "SHA256SUMS"
$checksumContent = ($checksumLines -join "`n") + "`n"
[System.IO.File]::WriteAllText($checksumPath, $checksumContent, [System.Text.UTF8Encoding]::new($false))

foreach ($fileName in $archives + "SHA256SUMS") {
    $source = Join-Path $SourceDirectory $fileName
    $destination = "s3://$BucketName/$Prefix/$fileName"
    & aws s3 cp $source $destination --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upload $source to $destination"
    }
    Write-Host "Uploaded $destination"
}
