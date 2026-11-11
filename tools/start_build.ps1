$p = Start-Process -FilePath 'C:\Users\djkl1\snake_ctf\tools\build_template.bat' -WorkingDirectory 'C:\Users\djkl1\snake_ctf' -RedirectStandardOutput 'C:\Users\djkl1\snake_ctf\tools\build_log.txt' -RedirectStandardError 'C:\Users\djkl1\snake_ctf\tools\build_err.txt' -WindowStyle Hidden -PassThru
Write-Output "PID: $($p.Id)"
