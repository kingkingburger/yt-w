Option Explicit

Dim shell
Dim fileSystem
Dim scriptDirectory
Dim repositoryRoot
Dim helperPath
Dim downloadRoot
Dim onceArgument
Dim command
Dim exitCode

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
repositoryRoot = fileSystem.GetParentFolderName(scriptDirectory)
helperPath = fileSystem.BuildPath(scriptDirectory, "windows-recycle-helper.ps1")
downloadRoot = fileSystem.BuildPath(repositoryRoot, "downloads")

onceArgument = ""
If WScript.Arguments.Named.Exists("Once") Then
    onceArgument = " -Once"
End If

command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & _
    QuoteArgument(helperPath) & " -DownloadRoot " & _
    QuoteArgument(downloadRoot) & onceArgument
exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode

Function QuoteArgument(value)
    QuoteArgument = Chr(34) & value & Chr(34)
End Function
