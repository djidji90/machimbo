# borrar_pyc_ventas.ps1
Get-ChildItem .\monedero -Recurse -Include *.pyc | Remove-Item -Force
Write-Host "Archivos .pyc borrados de la carpeta ventas y subcarpetas."

borrar_pyc_monedero.ps1