# Fetches latest ECS standard HANA releases from SAP internal wiki and writes a clean summary to file.

$outputFile = "C:\Users\I522148\OneDrive - SAP SE\SWAT\AI\Claude\working directory\HANA_latest_release.txt"
$token  = "MDg2OTM2OTA1NDUxOv5VFbKHv/TUQvnCPJDnzVV626JE"
$pageId = "1617468855"

try {
    $response = Invoke-RestMethod `
        -Uri "https://wiki.one.int.sap/wiki/rest/api/content/$pageId`?expand=body.storage" `
        -Headers @{ Authorization = "Bearer $token" } -Method Get

    $raw = $response.body.storage.value
    $text = $raw -replace '<[^>]+>', ' ' -replace '&amp;', '&' -replace '&nbsp;', ' ' `
                 -replace '&gt;', '>' -replace '&lt;', '<' -replace '\s+', ' '

    # --- Release N ---
    $releaseN = "Not found"
    if ($text -match 'Release \(N\)\s+(SAP HANA 2\.0 SPS\d+ Rev [\d\.]+)') {
        $releaseN = $matches[1].Trim()
    }

    # --- Release N-1 ---
    $releaseNm1 = "Not found"
    if ($text -match 'Release \(N -1\)\s+(SAP HANA 2\.0 SPS\d+ Rev [\d\.]+)') {
        $releaseNm1 = $matches[1].Trim()
    }

    # --- Next planned ---
    $nextPlanned = "Not listed"
    if ($text -match 'Next Planned Release\s+\*+\s+(SAP HANA 2\.0 SPS\d+ Rev [\d\.x]+)') {
        $nextPlanned = $matches[1].Trim()
    }

    # --- Upgrade path (single clean sentence) ---
    $upgradePath = "See wiki"
    if ($text -match 'Upgrade from (Rev [\d\.]+ to Rev [\d\.]+ is supported)') {
        $upgradePath = $matches[1].Trim()
    }

    # --- OS requirements for N ---
    $osN = "See wiki"
    if ($text -match 'SLES15 SP(\d+) or higher RHEL [\d\.]+ or higher') {
        $osN = "SLES 15 SP$($matches[1])+ / RHEL 9.2+"
    } elseif ($text -match 'SLES for SAP Applications 15 SP(\d+) and above') {
        $osN = "SLES 15 SP$($matches[1])+"
    }

    # --- CVEs (unique, short form only) ---
    $cveSet = [System.Collections.Generic.HashSet[string]]::new()
    [regex]::Matches($text, 'CVE-[\d]+-[\d]+') | ForEach-Object { [void]$cveSet.Add($_.Value) }
    $cveList = if ($cveSet.Count -gt 0) { $cveSet -join ", " } else { "None" }

    # --- End of Mainstream Maintenance ---
    $eomSPS08 = if ($text -match 'SPS 08[^:]*:\s*([\d]{1,2} \w+ \d{4})') { $matches[1] } else { "20 Nov 2028" }
    $eomSPS07 = if ($text -match 'SPS 07[^:]*:\s*([\d]{1,2} \w+ \d{4})') { $matches[1] } else { "30 Apr 2028" }

    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm") + " CST"

    $output = @"
========================================================
 SAP HANA ECS Standard Releases
 Last checked: $timestamp
========================================================

CURRENT STANDARD (Release N):
  $releaseN
  OS requirement: $osN

PREVIOUS STANDARD (Release N-1):
  $releaseNm1

NEXT PLANNED RELEASE:
  $nextPlanned

UPGRADE PATH:
  $upgradePath

END OF MAINSTREAM MAINTENANCE:
  HANA 2.0 SPS08 : $eomSPS08
  HANA 2.0 SPS07 : $eomSPS07
  HANA 2.0 SPS06 : 31 Dec 2023 (ended)
  HANA 2.0 SPS05 : 31 Dec 2025 (ended)

SECURITY / CVE:
  Active CVEs : $cveList

SOURCE:
  https://wiki.one.int.sap/wiki/spaces/HECOPS/pages/$pageId
========================================================
"@

    $output | Out-File -FilePath $outputFile -Encoding UTF8 -Force
    Write-Output "SUCCESS: File written at $timestamp"

} catch {
    $errMsg = "ERROR at $(Get-Date -Format 'yyyy-MM-dd HH:mm'): $($_.Exception.Message)"
    $errMsg | Out-File -FilePath $outputFile -Encoding UTF8 -Force
    Write-Output $errMsg
    exit 1
}
