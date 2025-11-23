"""
CoCo Image Viewer - PyQt6 GUI and CLI for viewing vintage image formats from DSK images.
"""

import sys
import argparse
from io import BytesIO
from PIL import Image
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QLabel, QFileDialog, QScrollArea,
    QSplitter, QFrame, QStatusBar
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt

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


def pil_to_qpixmap(pil_image):
    """Convert PIL Image to QPixmap."""
    # Convert PIL image to RGB if necessary
    if pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')

    # Get image data
    data = pil_image.tobytes('raw', 'RGB')
    width, height = pil_image.size

    # Create QImage from data
    qimage = QImage(data, width, height, width * 3, QImage.Format.Format_RGB888)

    # Convert to QPixmap
    return QPixmap.fromImage(qimage)


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dsk = None
        self.current_pixmap = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("CoCo MAX/CM3/CLP/MGE/MAC/PCX/GIF DSK Viewer")
        self.setGeometry(100, 100, 1000, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Top button bar
        button_layout = QHBoxLayout()
        self.btn_open = QPushButton("Open DSK File")
        self.btn_open.clicked.connect(self.open_dsk)
        button_layout.addWidget(self.btn_open)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Create splitter for file list and image view
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - File list
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_file_select)
        left_layout.addWidget(self.file_list)

        splitter.addWidget(left_frame)

        # Right panel - Image display with scroll area
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #404040;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)

        right_layout.addWidget(self.scroll_area)
        splitter.addWidget(right_frame)

        # Set splitter sizes (200px for file list, rest for image)
        splitter.setSizes([200, 800])

        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Open a DSK file to begin")

    def open_dsk(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open DSK File",
            "",
            "DSK files (*.DSK *.dsk);;All files (*.*)"
        )
        if not filepath:
            return

        self.dsk = DSKImage(filepath)
        if self.dsk.mount():
            self.file_list.clear()
            for entry in self.dsk.directory:
                filename = f"{entry.filename}.{entry.extension}" if entry.extension else entry.filename
                self.file_list.addItem(filename)
            self.status_bar.showMessage(f"Loaded: {filepath} ({len(self.dsk.directory)} files)")
        else:
            self.status_bar.showMessage("Failed to load DSK file")

    def display_image(self, pil_image):
        """Display a PIL Image in the scroll area."""
        width, height = pil_image.size

        # Convert PIL image to QPixmap
        self.current_pixmap = pil_to_qpixmap(pil_image)

        # Display in label
        self.image_label.setPixmap(self.current_pixmap)
        self.image_label.adjustSize()

        # Update window title with dimensions
        self.setWindowTitle(f"CoCo Image Viewer - {width}x{height}")
        self.status_bar.showMessage(f"Image: {width}x{height} pixels")

    def on_file_select(self, item):
        if not self.dsk:
            return

        selected_index = self.file_list.row(item)
        selected_entry = self.dsk.directory[selected_index]
        extension = selected_entry.extension.upper()

        try:
            if extension == "MAX":
                data = self.dsk.extract_file(selected_entry)
                if data:
                    ppm_data, width, height = convert_max_to_ppm(data, 1, False, 256, None, 0, True)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)

            elif extension == "CM3":
                data = self.dsk.extract_file(selected_entry)
                if data:
                    ppm_data, width, height = convert_cm3_to_ppm(data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)

            elif extension == "CLP":
                data = self.dsk.extract_file(selected_entry)
                if data:
                    ppm_data, width, height = convert_clp_to_ppm(data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        self.status_bar.showMessage("No picture found in CLP file")

            elif extension == "MGE":
                data = self.dsk.extract_file(selected_entry)
                if data:
                    ppm_data, width, height = convert_mge_to_ppm(data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        self.status_bar.showMessage("Failed to convert MGE file")

            elif extension == "MAC":
                data = self.dsk.extract_file(selected_entry)
                if data:
                    ppm_data, width, height = convert_mac_to_ppm(data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        self.status_bar.showMessage("Failed to convert MAC file")

            elif extension == "PCX":
                data = self.dsk.extract_file(selected_entry)
                if data:
                    ppm_data, width, height = convert_pcx_to_ppm(data)
                    if ppm_data:
                        img = Image.open(BytesIO(ppm_data))
                        self.display_image(img)
                    else:
                        self.status_bar.showMessage("Failed to convert PCX file")

            elif extension == "GIF":
                data = self.dsk.extract_file(selected_entry)
                if data:
                    img = Image.open(BytesIO(data))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    self.display_image(img)

            else:
                self.status_bar.showMessage(f"Unsupported format: {extension}")

        except Exception as e:
            self.status_bar.showMessage(f"Error: {str(e)}")
            print(f"Error displaying {extension} image: {e}")


# --- CLI Application ---

def run_gui():
    """Launch the PyQt6 GUI application."""
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(description="CoCo MAX/CM3/CLP/MGE/MAC/PCX/GIF DSK Tool (PyQt6)")
    subparsers = parser.add_subparsers(dest="command")

    gui_parser = subparsers.add_parser("gui", help="Launch the GUI application")

    list_parser = subparsers.add_parser("list", help="List files in a DSK image")
    list_parser.add_argument("dsk_file", help="Path to the DSK file")

    extract_parser = subparsers.add_parser("extract", help="Extract and convert an image file to PNG")
    extract_parser.add_argument("dsk_file", help="Path to the DSK file")
    extract_parser.add_argument("image_file", help="Name of the image file to extract")
    extract_parser.add_argument("png_file", help="Path to save the output PNG file")

    args = parser.parse_args()

    if args.command == "gui" or args.command is None:
        run_gui()

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
                        try:
                            img = Image.open(BytesIO(image_data))
                            width, height = img.size
                            img.save(args.png_file, 'PNG')
                            print(f"Saved GIF image as {args.png_file} ({width}x{height})")
                        except Exception as e:
                            print(f"Error converting GIF to PNG: {e}")
                        ppm_data = None
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
