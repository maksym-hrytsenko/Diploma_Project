"""Standalone manual test harness for ActionExecutor, run outside the app.

Note: predates ActionExecutor's current EventBus-driven constructor and
execute() API, kept for reference rather than exercised in CI.
"""

from action_executor import ActionExecutor


executor = ActionExecutor()

while True:

    print("\nAvailable commands:")
    print("CLICK")
    print("MOVE_CURSOR_LEFT")
    print("MOVE_CURSOR_RIGHT")
    print("MOVE_CURSOR_UP")
    print("MOVE_CURSOR_DOWN")
    print("SCROLL_UP")
    print("SCROLL_DOWN")
    print("MAXIMIZE_WINDOW")
    print("MINIMIZE_WINDOW")
    print("MOVE_WINDOW_LEFT")
    print("MOVE_WINDOW_RIGHT")
    print("OPEN_BROWSER")
    print("OPEN_CHATGPT")
    print("OPEN_VSCODE")
    print("OPEN_TERMINAL")
    print("ALT_TAB")
    print("CTRL_C")
    print("CTRL_V")
    print("SCREENSHOT")
    print("EXIT")

    command = input("\nCommand: ").strip()

    if command == "EXIT":
        break

    executor.execute(command)
