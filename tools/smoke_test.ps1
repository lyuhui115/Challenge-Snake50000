$p = Start-Process -FilePath 'C:\Users\djkl1\snake_ctf\game\build\snake50000.exe' -PassThru
Start-Sleep -Seconds 12
if ($p.HasExited) {
    Write-Output ("FAILED: exited with code " + $p.ExitCode)
} else {
    Write-Output ("ALIVE after 12s, PID " + $p.Id + ", window title: [" + $p.MainWindowTitle + "]")
    Stop-Process -Id $p.Id -Force
    Write-Output "killed."
}
