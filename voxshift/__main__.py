import tkinter as tk

from .alpha_ui import OxShiftAlphaUI


def main() -> None:
    root = tk.Tk()
    OxShiftAlphaUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
