"""Standalone exploratory script for testing the webbrowser module.

Opens a couple of URLs via the default browser, including a new-tab call.
Used to verify webbrowser's cross-platform behavior in isolation before
relying on it elsewhere in the project.
"""

import webbrowser
import time

print("Starting in 3 seconds...")
time.sleep(3)

print("Opening Google...")
webbrowser.open("https://www.google.com")

time.sleep(2)

print("Opening YouTube in new tab...")
webbrowser.open_new_tab("https://www.youtube.com")

time.sleep(2)

print("Opening GitHub...")
webbrowser.open("https://www.github.com")

print("Done!")