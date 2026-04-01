"""
Image Converter Pro - Main Entry Point
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import ImageConverterApp
import tkinter as tk


def main():
    root = tk.Tk()
    app = ImageConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
