' Silent Launcher for ParallelDoc (V2.1)
' Launches Brave, Microsoft Edge, or Chrome in standalone --app mode without flashing a console window.
' Supports optional argument: path to a .json document. If provided, copies it to active_document.json.

Option Explicit
On Error Resume Next

Dim fso, wshShell, scriptDir, htmlPath, fileUrl, localAppData, progFiles, progFilesX86
Dim candidates(7), browserPath, profileDir, cmd, i, srcFile, destFile

Set fso = CreateObject("Scripting.FileSystemObject")
Set wshShell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
htmlPath = scriptDir & "\paralleldoc.html"

If Not fso.FileExists(htmlPath) Then
    MsgBox "Application file not found: " & htmlPath, vbCritical, "ParallelDoc Launch Error"
    WScript.Quit 1
End If

' If an input file argument was provided, copy it to active_document.json
If WScript.Arguments.Count > 0 Then
    srcFile = WScript.Arguments(0)
    If fso.FileExists(srcFile) Then
        destFile = scriptDir & "\active_document.json"
        fso.CopyFile srcFile, destFile, True
    End If
End If

' Convert Windows path backslashes to forward slashes for file:/// URL
fileUrl = "file:///" & Replace(htmlPath, "\", "/")

localAppData = wshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
progFiles = wshShell.ExpandEnvironmentStrings("%ProgramFiles%")
progFilesX86 = wshShell.ExpandEnvironmentStrings("%ProgramFiles(x86)%")

' Priority list of browser executables: Brave -> Microsoft Edge -> Google Chrome
candidates(0) = localAppData & "\BraveSoftware\Brave-Browser\Application\brave.exe"
candidates(1) = progFiles & "\BraveSoftware\Brave-Browser\Application\brave.exe"
candidates(2) = progFilesX86 & "\BraveSoftware\Brave-Browser\Application\brave.exe"
candidates(3) = progFilesX86 & "\Microsoft\Edge\Application\msedge.exe"
candidates(4) = progFiles & "\Microsoft\Edge\Application\msedge.exe"
candidates(5) = localAppData & "\Microsoft\Edge\Application\msedge.exe"
candidates(6) = progFiles & "\Google\Chrome\Application\chrome.exe"
candidates(7) = progFilesX86 & "\Google\Chrome\Application\chrome.exe"

browserPath = ""
For i = 0 To UBound(candidates)
    If candidates(i) <> "" And fso.FileExists(candidates(i)) Then
        browserPath = candidates(i)
        Exit For
    End If
Next

If browserPath <> "" Then
    If InStr(1, LCase(browserPath), "brave") > 0 Then
        profileDir = localAppData & "\BraveSoftware\Brave-Browser\ParallelDocProfile"
        cmd = """" & browserPath & """ --app=""" & fileUrl & """ --user-data-dir=""" & profileDir & """ --allow-file-access-from-files --no-first-run"
    ElseIf InStr(1, LCase(browserPath), "msedge") > 0 Then
        profileDir = localAppData & "\Microsoft\Edge\ParallelDocProfile"
        cmd = """" & browserPath & """ --app=""" & fileUrl & """ --user-data-dir=""" & profileDir & """ --allow-file-access-from-files --no-first-run"
    Else
        profileDir = localAppData & "\Google\Chrome\ParallelDocProfile"
        cmd = """" & browserPath & """ --app=""" & fileUrl & """ --user-data-dir=""" & profileDir & """ --allow-file-access-from-files --no-first-run"
    End If
    ' Window style 0 = vbHide (completely silent, no cmd console flashing)
    wshShell.Run cmd, 0, False
Else
    ' Fallback to default system browser
    wshShell.Run """" & fileUrl & """", 1, False
End If
