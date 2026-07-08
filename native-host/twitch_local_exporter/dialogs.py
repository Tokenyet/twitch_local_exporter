from __future__ import annotations

import subprocess
from pathlib import Path

from .config import default_output_dir


def choose_output_folder(initial_dir: str | None = None) -> str:
    initial_path = normalize_initial_dir(initial_dir)
    try:
        return choose_with_powershell(initial_path)
    except Exception:
        return choose_with_tkinter(initial_path)


def normalize_initial_dir(value: str | None) -> Path:
    if value:
        path = Path(value).expanduser()
        if path.exists() and path.is_dir():
            return path
        if path.parent.exists():
            return path.parent
    fallback = default_output_dir()
    return fallback if fallback.exists() else fallback.parent


def choose_with_tkinter(initial_dir: Path) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title="Choose Twitch Local Exporter output folder",
            initialdir=str(initial_dir),
            mustexist=False
        )
    finally:
        root.destroy()
    return str(selected or "")


def choose_with_powershell(initial_dir: Path) -> str:
    escaped = str(initial_dir).replace("'", "''")
    script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$owner = New-Object System.Windows.Forms.Form
$owner.Text = 'Twitch Local Exporter'
$owner.StartPosition = 'CenterScreen'
$owner.Width = 360
$owner.Height = 110
$owner.TopMost = $true
$owner.ShowInTaskbar = $true
$owner.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedToolWindow
$label = New-Object System.Windows.Forms.Label
$label.AutoSize = $true
$label.Left = 18
$label.Top = 20
$label.Text = 'Choose an output folder for Twitch Local Exporter.'
$owner.Controls.Add($label)
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Choose Twitch Local Exporter output folder'
$dialog.SelectedPath = '{escaped}'
$dialog.ShowNewFolderButton = $true
$owner.Add_Shown({{
  $owner.Activate()
  $owner.BringToFront()
}})
$owner.Show()
$result = $dialog.ShowDialog($owner)
$owner.Close()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {{
  [Console]::Out.Write($dialog.SelectedPath)
}}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        timeout=300,
        check=False
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Folder picker failed").strip())
    return result.stdout.strip()
