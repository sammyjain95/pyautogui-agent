"""Test GUI app for the pyautogui-agent live test on a virtual display.

A small tkinter window with a labelled entry and a Submit button. Clicking
Submit writes a result file so the test driver can verify the click landed
without needing to see the screen.

Run under Xvfb; the driver script (vm_live_test.py) launches this app.
"""
import sys
import tkinter as tk

RESULT_FILE = "/tmp/pyautogui-agent-test/result.txt"


def main() -> None:
    root = tk.Tk()
    root.title("PyAutoGUI Agent Test")
    root.geometry("800x600+560+240")
    root.configure(bg="white")

    status = tk.Label(root, text="Status: waiting", font=("Helvetica", 18),
                      bg="white")
    status.pack(pady=40)

    frame = tk.Frame(root, bg="white")
    frame.pack(pady=20)
    name_label = tk.Label(frame, text="Name:", font=("Helvetica", 16),
                          bg="white")
    name_label.pack(side=tk.LEFT)
    entry = tk.Entry(frame, font=("Helvetica", 16), width=24)
    entry.pack(side=tk.LEFT, padx=10)
    # Like a well-behaved native app, clicking the label focuses the field.
    name_label.bind("<Button-1>", lambda e: entry.focus_set())

    def on_submit() -> None:
        status.config(text="Status: clicked")
        with open(RESULT_FILE, "a") as f:
            f.write(f"clicked entry={entry.get()!r}\n")
        root.update_idletasks()

    button = tk.Button(root, text="Submit", font=("Helvetica", 18),
                       bg="#2e7d32", fg="white", padx=30, pady=10,
                       command=on_submit)
    button.pack(pady=40)

    root.mainloop()


if __name__ == "__main__":
    sys.exit(main())
