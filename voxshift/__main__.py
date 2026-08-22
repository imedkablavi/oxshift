import tkinter as tk

from .pro_ui import OxShiftStudioUI


def main() -> None:
    root = tk.Tk()
    OxShiftStudioUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
