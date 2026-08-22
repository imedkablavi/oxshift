import tkinter as tk

from .enhanced_ui import OxShiftEnhancedUI


def main() -> None:
    root = tk.Tk()
    OxShiftEnhancedUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
