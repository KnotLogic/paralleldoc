' Helper to create a Windows Desktop shortcut for ParallelDoc
Option Explicit

Dim wshShell, fso, desktopPath, shortcut, scriptDir, targetVbs, localAppData, progFiles, progFilesX86
Dim candidates(7), browserPath, i

Set wshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

desktopPath = wshShell.SpecialFolders("Desktop")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
targetVbs = scriptDir & "\launch_paralleldoc.vbs"

If Not fso.FileExists(targetVbs) Then
    MsgBox "Target launcher not found: " & targetVbs, vbCritical, "Error"
    WScript.Quit 1
End If

localAppData = wshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
progFiles = wshShell.ExpandEnvironmentStrings("%ProgramFiles%")
progFilesX86 = wshShell.ExpandEnvironmentStrings("%ProgramFiles(x86)%")

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

Set shortcut = wshShell.CreateShortcut(desktopPath & "\ParallelDoc.lnk")
shortcut.TargetPath = "wscript.exe"
shortcut.Arguments = """" & targetVbs & """"
shortcut.WorkingDirectory = scriptDir
shortcut.Description = "ParallelDoc — 3-Pane Comparative Document Inspector (Original · Translation · Review)"
If browserPath <> "" Then
    shortcut.IconLocation = browserPath & ", 0"
Else
    shortcut.IconLocation = "shell32.dll, 14"
End If
shortcut.Save

WScript.Echo "ParallelDoc shortcut created successfully on your Desktop!"
