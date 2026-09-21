# Add the Pixel print node as a native IPP printer so Windows shows duplex options.
# Run in PowerShell (Admin not required).
#
# Usage:
#   .\scripts\add_windows_ipp_printer.ps1 -PixelIp 192.168.0.63 -Port 8631 -PrinterName "MTU PaperCut"

param(
  [string]$PixelIp = "192.168.0.63",
  [int]$Port = 8631,
  [string]$PrinterName = "MTU PaperCut"
)

$ErrorActionPreference = "Stop"
$IppUrl = "ipp://$PixelIp`:$Port/printer"

$existing = Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue
if ($existing) {
  Write-Host "Removing existing printer '$PrinterName'..."
  Remove-Printer -Name $PrinterName
}

Write-Host "Adding IPP printer at $IppUrl ..."
Add-Printer -Name $PrinterName -DriverName "Microsoft IPP Class Driver" -PortName $IppUrl

Write-Host "Done. Open Print dialog -> More settings -> Print on both sides."
Write-Host "If Add-Printer failed, try: Settings -> Bluetooth & devices -> Printers -> Add device -> Add manually -> IPP."
