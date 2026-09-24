# Add the Pixel print node through Windows directed IPP discovery.
#
# Usage:
#   .\scripts\add_windows_ipp_printer.ps1 -PixelIp 192.168.0.63 -Port 8632 -PrinterName "Papercut - Edison"

param(
  [string]$PixelIp = "192.168.0.63",
  [int]$Port = 8632,
  [string]$PrinterName = "Papercut - Edison"
)

$ErrorActionPreference = "Stop"
$IppUrl = "ipp://$PixelIp`:$Port/ipp/print"

$existing = Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue
if ($existing) {
  Write-Host "Printer '$PrinterName' is already installed."
  return
}

Write-Host "Adding IPP printer at $IppUrl ..."
Add-Printer -Name $PrinterName -IppURL $IppUrl

Write-Host "Done. Check that Windows selected Microsoft IPP Class Driver."
Write-Host "If Windows blocks the command, use Settings -> Printers & scanners -> Add device -> Add manually -> IPP Device, and enter $IppUrl."
