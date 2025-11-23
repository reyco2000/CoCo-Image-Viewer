"""
CoCo Image Viewer - GUI and CLI for viewing vintage image formats from DSK images.
"""

import argparse
from io import BytesIO
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog

# Import from the coco_image_formats library
from coco_image_formats import (
    DSKImage,
    convert_max_to_ppm,
    convert_cm3_to_ppm,
    convert_mge_to_ppm,
    convert_mac_to_ppm,
    convert_pcx_to_ppm,
    convert_clp_to_ppm,
)


# --- GUI Application ---

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CoCo MAX/CM3/CLP/MGE/MAC/PCX/GIF DSK Viewer")
        self.geometry("900x800")
        self.dsk = None

        # Top frame for button
        self.btn_open = tk.Button(self, text="Open DSK File", command=self.open_dsk)
        self.btn_open.pack(pady=5)

        # Create a paned window for file list and image
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left frame for file list
        self.left_frame = tk.Frame(self.paned)
        self.paned.add(self.left_frame, width=200)

        self.file_list = tk.Listbox(self.left_frame)
        self.file_list.pack(fill=tk.BOTH, expand=True)
        self.file_list.bind("<<ListboxSelect>>", self.on_file_select)

        # Right frame for image with scrollbars
        self.right_frame = tk.Frame(self.paned)
        self.paned.add(self.right_frame)

        # Create canvas with scrollbars for image display
        self.canvas = tk.Canvas(self.right_frame, bg='gray')
        self.h_scrollbar = tk.Scrollbar(self.right_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.v_scrollbar = tk.Scrollbar(self.right_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)

        # Grid layout for canvas and scrollbars
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.v_scrollbar.grid(row=0, column=1, sticky='ns')
        self.h_scrollbar.grid(row=1, column=0, sticky='ew')

        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.photo = None
        self.canvas_image = None

    def open_dsk(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("DSK files", "*.DSK"), ("All files", "*.*")]
        )
        if not filepath:
            return

        self.dsk = DSKImage(filepath)
        if self.dsk.mount():
            self.file_list.delete(0, tk.END)
            for entry in self.dsk.directory:
                filename = f"{entry.filename}.{entry.extension}" if entry.extension else entry.filename
                self.file_list.insert(tk.END, filename)

    def display_image(self, img):
        """Display a PIL Image on the scrollable canvas."""
        self.photo = ImageTk.PhotoImage(img)

        # Clear previous image
        if self.canvas_image:
            self.canvas.delete(self.canvas_image)

        # Update canvas scroll region to image size
        width, height = img.size
        self.canvas.configure(scrollregion=(0, 0, width, height))

        # Create image at top-left corner
        self.canvas_image = self.canvas.create_image(0, 0, anchor='nw', image=self.photo)

        # Update window title with image dimensions
        self.title(f"CoCo Image Viewer - {width}x{height}")

    def on_file_select(self, event):
        selection = event.widget.curselection()
        if not selection:
            return

        selected_index = selection[0]
        selected_entry = self.dsk.directory[selected_index]

        if selected_entry.extension.upper() == "MAX":
            max_data = self.dsk.extract_file(selected_entry)
            if max_data:
                ppm_data, width, height = convert_max_to_ppm(max_data, 1, False, 256, None, 0, True)
                if ppm_data:
                    try:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    except Exception as e:
                        print(f"Error displaying image: {e}")

        elif selected_entry.extension.upper() == "CM3":
            cm3_data = self.dsk.extract_file(selected_entry)
            if cm3_data:
                try:
                    ppm_data, width, height = convert_cm3_to_ppm(cm3_data)
                    img = Image.open(BytesIO(ppm_data))
                    self.display_image(img)
                except Exception as e:
                    print(f"Error displaying CM3 image: {e}")

        elif selected_entry.extension.upper() == "CLP":
            clp_data = self.dsk.extract_file(selected_entry)
            if clp_data:
                try:
                    ppm_data, width, height = convert_clp_to_ppm(clp_data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        print("No picture found in CLP file")
                except Exception as e:
                    print(f"Error displaying CLP image: {e}")

        elif selected_entry.extension.upper() == "MGE":
            mge_data = self.dsk.extract_file(selected_entry)
            if mge_data:
                try:
                    ppm_data, width, height = convert_mge_to_ppm(mge_data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        print("Failed to convert MGE file")
                except Exception as e:
                    print(f"Error displaying MGE image: {e}")

        elif selected_entry.extension.upper() == "MAC":
            mac_data = self.dsk.extract_file(selected_entry)
            if mac_data:
                try:
                    ppm_data, width, height = convert_mac_to_ppm(mac_data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        print("Failed to convert MAC file")
                except Exception as e:
                    print(f"Error displaying MAC image: {e}")

        elif selected_entry.extension.upper() == "PCX":
            pcx_data = self.dsk.extract_file(selected_entry)
            if pcx_data:
                try:
                    ppm_data, width, height = convert_pcx_to_ppm(pcx_data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        print("Failed to convert PCX file")
                except Exception as e:
                    print(f"Error displaying PCX image: {e}")

        elif selected_entry.extension.upper() == "GIF":
            gif_data = self.dsk.extract_file(selected_entry)
            if gif_data:
                try:
                    # PIL natively supports GIF format
                    img = Image.open(BytesIO(gif_data))
                    # Convert to RGB if needed (for consistency)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    self.display_image(img)
                except Exception as e:
                    print(f"Error displaying GIF image: {e}")


# --- CLI Application ---

def main():
    parser = argparse.ArgumentParser(description="CoCo MAX/CM3/CLP/MGE/MAC/PCX/GIF DSK Tool")
    subparsers = parser.add_subparsers(dest="command")

    gui_parser = subparsers.add_parser("gui", help="Launch the GUI application")

    list_parser = subparsers.add_parser("list", help="List files in a DSK image")
    list_parser.add_argument("dsk_file", help="Path to the DSK file")

    extract_parser = subparsers.add_parser("extract", help="Extract and convert a MAX, CM3, CLP, MGE, MAC, PCX, or GIF file to PNG")
    extract_parser.add_argument("dsk_file", help="Path to the DSK file")
    extract_parser.add_argument("image_file", help="Name of the image file to extract (MAX, CM3, CLP, MGE, MAC, PCX, GIF)")
    extract_parser.add_argument("png_file", help="Path to save the output PNG file")

    args = parser.parse_args()

    if args.command == "gui":
        app = App()
        app.mainloop()
    elif args.command == "list":
        dsk = DSKImage(args.dsk_file)
        if dsk.mount():
            for entry in dsk.directory:
                filename = f"{entry.filename}.{entry.extension}" if entry.extension else entry.filename
                print(filename)

    elif args.command == "extract":
        dsk = DSKImage(args.dsk_file)
        if dsk.mount():
            entry_to_extract = None
            for entry in dsk.directory:
                filename = f"{entry.filename}.{entry.extension}" if entry.extension else entry.filename
                if filename.upper() == args.image_file.upper():
                    entry_to_extract = entry
                    break

            if entry_to_extract:
                image_data = dsk.extract_file(entry_to_extract)
                if image_data:
                    # Determine format based on extension
                    extension = entry_to_extract.extension.upper()
                    ppm_data = None
                    width = height = 0

                    if extension == "MAX":
                        ppm_data, width, height = convert_max_to_ppm(image_data, 1, False, 256, None, 0, True)
                    elif extension == "CM3":
                        ppm_data, width, height = convert_cm3_to_ppm(image_data)
                    elif extension == "CLP":
                        ppm_data, width, height = convert_clp_to_ppm(image_data)
                        if not ppm_data:
                            print("No picture found in CLP file")
                    elif extension == "MGE":
                        ppm_data, width, height = convert_mge_to_ppm(image_data)
                        if not ppm_data:
                            print("Failed to convert MGE file")
                    elif extension == "MAC":
                        ppm_data, width, height = convert_mac_to_ppm(image_data)
                        if not ppm_data:
                            print("Failed to convert MAC file")
                    elif extension == "PCX":
                        ppm_data, width, height = convert_pcx_to_ppm(image_data)
                        if not ppm_data:
                            print("Failed to convert PCX file")
                    elif extension == "GIF":
                        # GIF is natively supported by PIL - save directly
                        try:
                            img = Image.open(BytesIO(image_data))
                            width, height = img.size
                            img.save(args.png_file, 'PNG')
                            print(f"Saved GIF image as {args.png_file} ({width}x{height})")
                        except Exception as e:
                            print(f"Error converting GIF to PNG: {e}")
                        ppm_data = None  # Already handled
                    else:
                        print(f"Unsupported file format: {extension}")
                        ppm_data = None

                    if ppm_data:
                        try:
                            img = Image.open(BytesIO(ppm_data))
                            img.save(args.png_file, 'PNG')
                            print(f"Saved {extension} image as {args.png_file} ({width}x{height})")
                        except Exception as e:
                            print(f"Error converting to PNG: {e}")
                else:
                    print(f"Failed to extract data from {args.image_file}")
            else:
                print(f"File not found: {args.image_file}")


if __name__ == "__main__":
    main()
