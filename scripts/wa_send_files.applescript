on run argv
  if (count of argv) is less than 2 then
    display dialog "Usage: osascript wa_send_files.applescript <phone_or_name> <folder_path>"
    return
  end if

  set targetChat to item 1 of argv
  set folderPath to item 2 of argv

  tell application "WhatsApp" to activate
  delay 0.5

  tell application "System Events"
    if not (exists process "WhatsApp") then return
    tell process "WhatsApp"
      set frontmost to true
      -- Focus search and select chat
      keystroke "f" using {command down}
      delay 0.2
      keystroke targetChat
      delay 0.6
      keystroke return
      delay 0.6
    end tell
  end tell

  -- Collect PDFs in folder
  set pdfFiles to {}
  try
    tell application "Finder"
      set theFolder to (POSIX file folderPath) as alias
      set pdfFiles to every file of theFolder whose name extension is "pdf"
    end tell
  end try

  repeat with f in pdfFiles
    set p to POSIX path of (f as alias)
    -- Open file dialog to attach
    tell application "System Events"
      tell process "WhatsApp"
        keystroke "o" using {command down}
        delay 0.4
      end tell
      -- Go to path in open dialog
      keystroke "g" using {command down, shift down}
      delay 0.2
      keystroke p
      keystroke return
      delay 0.3
      -- Confirm attachment (do NOT send)
      keystroke return
      delay 0.5
    end tell
  end repeat
end run


