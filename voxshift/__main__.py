import tkinter as tk

from .ui import VoxShiftUI


def main() -> None:
    root = tk.Tk()
    VoxShiftUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
