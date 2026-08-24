param(
    [switch]$OpenVendorPage
)

$ErrorActionPreference = 'Stop'

function Get-AudioEndpoints {
    try {
        return Get-PnpDevice -Class AudioEndpoint -PresentOnly -ErrorAction Stop
    } catch {
        return @()
    }
}

$endpoints = @(Get-AudioEndpoints)
$matches = @($endpoints | Where-Object {
    $_.FriendlyName -match 'VB-Audio|CABLE Input|CABLE Output|VoiceMeeter|OxShift|VoxShift'
})

Write-Host ''
Write-Host 'OxShift Windows virtual microphone check' -ForegroundColor Cyan
Write-Host '----------------------------------------'

if ($matches.Count -gt 0) {
    Write-Host 'Compatible virtual-audio endpoints were detected:' -ForegroundColor Green
    $matches | ForEach-Object { Write-Host (" - {0}" -f $_.FriendlyName) }
    Write-Host ''
    Write-Host 'Recommended routing for VB-CABLE:'
    Write-Host '  1. In OxShift, choose your physical microphone as Input.'
    Write-Host '  2. Choose CABLE Input (VB-Audio Virtual Cable) as OxShift Output.'
    Write-Host '  3. In Discord/OBS/Zoom/game chat, choose CABLE Output as Microphone.'
    exit 0
}

Write-Warning 'No supported signed virtual-audio endpoint was detected.'
Write-Host ''
Write-Host 'Alpha policy:'
Write-Host '  - OxShift does not silently download or install kernel audio drivers.'
Write-Host '  - Install a signed virtual-audio driver you trust, then rerun this helper.'
Write-Host '  - VB-CABLE / VoiceMeeter are common third-party options; they are not bundled with OxShift.'
Write-Host ''

if ($OpenVendorPage) {
    Start-Process 'https://vb-audio.com/Cable/'
}

exit 2
