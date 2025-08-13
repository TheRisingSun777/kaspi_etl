on run argv
  set chatQuery to ""
  if (count of argv) > 0 then set chatQuery to item 1 of argv

  set appNames to {"WhatsApp", "WhatsApp Desktop"}
  set launched to false

  repeat with appName in appNames
    try
      tell application (appName as text) to activate
      set launched to true
      exit repeat
    end try
  end repeat

  if launched is false then return

  delay 0.5
  tell application "System Events"
    repeat with appName in appNames
      if exists process (appName as text) then
        tell process (appName as text)
          -- Focus search field
          keystroke "l" using {command down}
          delay 0.1
          keystroke chatQuery
          delay 0.4
          key code 36 -- Return to open chat
        end tell
        exit repeat
      end if
    end repeat
  end tell
end run


