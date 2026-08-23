import tkinter as tk

from .advanced_ui import OxShiftAdvancedUI


def main() -> None:
    root = tk.Tk()
    OxShiftAdvancedUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
