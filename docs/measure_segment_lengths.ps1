# measure_segment_lengths.ps1
# Milestone 4 / B1: measure the segment-length distribution (L) of the water
# geometry the index is built over.
#
# Input: the exported C++ water-vertices CSV (EPSG:26918, meters).
# Columns (from caprm.water_export.VERTEX_COLUMNS):
#   water_feature_index, part_index, ring_index, vertex_index, x, y
#
# A segment joins two consecutive vertices within the SAME
# (water_feature_index, part_index, ring_index). The exporter writes each
# ring's vertices contiguously and in order, so adjacency on that triple is a
# faithful segment reconstruction.
#
# Expected sanity check (from docs/data_sources.md):
#   segments should total 1,063,159 for the countywide export.

# ---- edit this if your path differs -----------------------------------------
$VerticesCsv = "outputs\cpp_input\water_vertices_countywide.csv"
# -----------------------------------------------------------------------------

if (-not (Test-Path $VerticesCsv)) {
    throw "Vertices CSV not found: $VerticesCsv"
}

$ci = [System.Globalization.CultureInfo]::InvariantCulture
$path = (Resolve-Path $VerticesCsv).Path
$reader = [System.IO.StreamReader]::new($path, [System.Text.Encoding]::UTF8)

$null = $reader.ReadLine()  # skip header

$lengths = [System.Collections.Generic.List[double]]::new(1200000)

$havePrev = $false
$pKey = ''
$pX = 0.0; $pY = 0.0

$sum = 0.0
$maxLen = -1.0
$maxLoc = ''

# coordinate bounding box, as a CRS/units sanity check
$minX = [double]::PositiveInfinity; $maxX = [double]::NegativeInfinity
$minY = [double]::PositiveInfinity; $maxY = [double]::NegativeInfinity

$vertexCount = 0

while ($null -ne ($line = $reader.ReadLine())) {
    if ($line.Length -eq 0) { continue }
    $f = $line.Split(',')

    $key = $f[0] + '|' + $f[1] + '|' + $f[2]   # feature|part|ring
    $x = [double]::Parse($f[4], $ci)
    $y = [double]::Parse($f[5], $ci)

    if ($x -lt $minX) { $minX = $x }
    if ($x -gt $maxX) { $maxX = $x }
    if ($y -lt $minY) { $minY = $y }
    if ($y -gt $maxY) { $maxY = $y }

    if ($havePrev -and $key -eq $pKey) {
        $dx = $x - $pX
        $dy = $y - $pY
        $len = [math]::Sqrt($dx * $dx + $dy * $dy)
        $lengths.Add($len)
        $sum += $len
        if ($len -gt $maxLen) {
            $maxLen = $len
            $maxLoc = "feature_index=$($f[0]) part=$($f[1]) ring=$($f[2]) endpoint_vertex=$($f[3])"
        }
    }

    $pKey = $key; $pX = $x; $pY = $y
    $havePrev = $true
    $vertexCount++
}
$reader.Close()

$n = $lengths.Count
if ($n -eq 0) { throw "No segments reconstructed; check the input file and its columns." }

$arr = $lengths.ToArray()
[Array]::Sort($arr)

function Pct([double[]]$a, [double]$p) {
    $rank = [math]::Ceiling($p / 100.0 * $a.Length)
    if ($rank -lt 1) { $rank = 1 }
    if ($rank -gt $a.Length) { $rank = $a.Length }
    return $a[$rank - 1]
}

function CountGreater([double[]]$a, [double]$t) {
    # count of elements strictly greater than t (a sorted ascending)
    $lo = 0; $hi = $a.Length
    while ($lo -lt $hi) {
        $mid = [int](($lo + $hi) / 2)
        if ($a[$mid] -le $t) { $lo = $mid + 1 } else { $hi = $mid }
    }
    return $a.Length - $lo
}

$mean = $sum / $n

Write-Host ""
Write-Host "=== Segment-length distribution (EPSG:26918, meters) ==="
Write-Host ("input file:          {0}" -f $path)
Write-Host ("vertices read:       {0:N0}" -f $vertexCount)
Write-Host ("segments:            {0:N0}   (expect 1,063,159 countywide)" -f $n)
Write-Host ""
Write-Host ("min:                 {0:N6} m" -f $arr[0])
Write-Host ("mean:                {0:N6} m" -f $mean)
Write-Host ("median (p50):        {0:N6} m" -f (Pct $arr 50))
Write-Host ("p90:                 {0:N6} m" -f (Pct $arr 90))
Write-Host ("p95:                 {0:N6} m" -f (Pct $arr 95))
Write-Host ("p99:                 {0:N6} m" -f (Pct $arr 99))
Write-Host ("p99.9:               {0:N6} m" -f (Pct $arr 99.9))
Write-Host ("max (L):             {0:N6} m" -f $arr[$n - 1])
Write-Host ("L/2 (inflation add): {0:N6} m" -f ($arr[$n - 1] / 2.0))
Write-Host ("longest segment at:  {0}" -f $maxLoc)
Write-Host ""
Write-Host "--- tail counts (relative to the 325 m median nearest-water distance) ---"
foreach ($t in 50, 100, 200, 325, 500, 1000) {
    $c = CountGreater $arr $t
    Write-Host ("segments > {0,5} m:  {1,10:N0}   ({2:N4}%)" -f $t, $c, (100.0 * $c / $n))
}
Write-Host ""
Write-Host "--- coordinate bounding box (units sanity check) ---"
Write-Host ("x: {0:N2} .. {1:N2}   (expect ~2.5e5 .. 3.3e5 for Monroe Co. UTM 18N easting)" -f $minX, $maxX)
Write-Host ("y: {0:N2} .. {1:N2}   (expect ~4.75e6 .. 4.79e6 northing)" -f $minY, $maxY)
Write-Host ""
Write-Host "If segment count != 1,063,159, the grouping or input differs - tell me before we build on L."
Write-Host "If x/y look like small decimals (~0.x), the CSV is in degrees, not meters - stop and flag it."