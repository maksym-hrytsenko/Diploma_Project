import webbrowser
import time

print("Starting in 3 seconds...")
time.sleep(3)

# 1. Open a website
print("Opening Google...")
webbrowser.open("https://www.google.com")

time.sleep(2)

# 2. Open new tab
print("Opening YouTube in new tab...")
webbrowser.open_new_tab("https://www.youtube.com")

time.sleep(2)

# 3. Open another site
print("Opening GitHub...")
webbrowser.open("https://www.github.com")

print("Done!")