$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
[IO.File]::WriteAllBytes((Join-Path $PSScriptRoot 'Gilles.ico'),[Convert]::FromBase64String((Get-Content 'Gilles.ico.base64' -Raw)))
$csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $csc /nologo /target:winexe /platform:x64 /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Web.Extensions.dll /win32icon:Gilles.ico /out:Piper-Gilles.exe Fenetre.cs
if($LASTEXITCODE -ne 0){throw 'Compilation failed'}
