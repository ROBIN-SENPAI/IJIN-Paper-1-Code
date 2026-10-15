param([string]$in, [string]$out)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $doc = $word.Documents.Open($in, $false, $true)
  $doc.SaveAs2($out, 17)
  $doc.Close($false)
} finally { $word.Quit() }
