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
    QSplitter, QFrame, QStatusBar, QLineEdit, QSlider, QCheckBox,
    QListWidgetItem
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

# Supported image extensions
SUPPORTED_EXTENSIONS = {'MAX', 'CM3', 'CLP', 'MGE', 'MAC', 'PCX', 'GIF'}


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
    # Zoom scale options
    ZOOM_SCALES = [0.25, 0.50, 1.0, 1.25, 1.50, 2.0]
    ZOOM_LABELS = ['0.25x', '0.50x', '1x', '1.25x', '1.50x', '2x']

    def __init__(self):
        super().__init__()
        self.dsk = None
        self.dsk_path = ""
        self.current_pixmap = None
        self.current_pil_image = None
        self.current_scale = 1.0
        self.all_files = []  # Store all files for filtering
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("CoCo MAX/CM3/CLP/MGE/MAC/PCX/GIF DSK Viewer")
        self.setGeometry(100, 100, 1000, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Top bar - Open button and DSK path
        top_layout = QHBoxLayout()

        self.btn_open = QPushButton("Open DSK File")
        self.btn_open.clicked.connect(self.open_dsk)
        self.btn_open.setFixedWidth(120)
        top_layout.addWidget(self.btn_open)

        # DSK path display (read-only)
        self.path_label = QLabel("Disk:")
        top_layout.addWidget(self.path_label)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setStyleSheet("background-color: #e0e0e0; color: #606060;")
        self.path_edit.setPlaceholderText("No disk mounted")
        top_layout.addWidget(self.path_edit)

        main_layout.addLayout(top_layout)

        # Create splitter for file list and image view
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - File list with filter checkbox
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # Filter checkbox
        self.filter_checkbox = QCheckBox("Show only supported files")
        self.filter_checkbox.setChecked(False)
        self.filter_checkbox.stateChanged.connect(self.update_file_list)
        left_layout.addWidget(self.filter_checkbox)

        # File list
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_file_select)
        left_layout.addWidget(self.file_list)

        splitter.addWidget(left_frame)

        # Right panel - Image display with controls
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(5, 5, 5, 5)

        # Zoom controls
        zoom_layout = QHBoxLayout()

        zoom_label = QLabel("Zoom:")
        zoom_layout.addWidget(zoom_label)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(0)
        self.zoom_slider.setMaximum(len(self.ZOOM_SCALES) - 1)
        self.zoom_slider.setValue(2)  # Default to 1x (index 2)
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(1)
        self.zoom_slider.setFixedWidth(200)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)

        self.zoom_value_label = QLabel("1x")
        self.zoom_value_label.setFixedWidth(50)
        zoom_layout.addWidget(self.zoom_value_label)

        zoom_layout.addStretch()

        # Export button
        self.btn_export = QPushButton("Export as PNG")
        self.btn_export.clicked.connect(self.export_png)
        self.btn_export.setEnabled(False)
        zoom_layout.addWidget(self.btn_export)

        right_layout.addLayout(zoom_layout)

        # Scroll area for image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #404040;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)

        right_layout.addWidget(self.scroll_area)
        splitter.addWidget(right_frame)

        # Set splitter sizes (250px for file list, rest for image)
        splitter.setSizes([250, 750])

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
            self.dsk_path = filepath
            self.path_edit.setText(filepath)

            # Store all files
            self.all_files = []
            for entry in self.dsk.directory:
                filename = f"{entry.filename}.{entry.extension}" if entry.extension else entry.filename
                self.all_files.append((filename, entry))

            # Update file list based on filter
            self.update_file_list()

            self.status_bar.showMessage(f"Loaded: {filepath} ({len(self.dsk.directory)} files)")
        else:
            self.status_bar.showMessage("Failed to load DSK file")
            self.path_edit.setText("")
            self.dsk_path = ""

    def update_file_list(self):
        """Update file list based on filter checkbox state."""
        self.file_list.clear()

        filter_enabled = self.filter_checkbox.isChecked()

        for filename, entry in self.all_files:
            ext = entry.extension.upper() if entry.extension else ""

            if filter_enabled and ext not in SUPPORTED_EXTENSIONS:
                continue

            item = QListWidgetItem(filename)
            # Store the original index for later retrieval
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.file_list.addItem(item)

        # Update status
        visible_count = self.file_list.count()
        total_count = len(self.all_files)
        if filter_enabled:
            self.status_bar.showMessage(f"Showing {visible_count} of {total_count} files (filtered)")
        else:
            self.status_bar.showMessage(f"Showing {total_count} files")

    def on_zoom_changed(self, value):
        """Handle zoom slider change."""
        self.current_scale = self.ZOOM_SCALES[value]
        self.zoom_value_label.setText(self.ZOOM_LABELS[value])

        # Update displayed image if we have one
        if self.current_pil_image:
            self.update_displayed_image()

    def update_displayed_image(self):
        """Update the displayed image with current zoom level."""
        if not self.current_pil_image:
            return

        # Get original size
        orig_width, orig_height = self.current_pil_image.size

        # Calculate new size
        new_width = int(orig_width * self.current_scale)
        new_height = int(orig_height * self.current_scale)

        # Resize image
        if self.current_scale != 1.0:
            resample = Image.Resampling.NEAREST if self.current_scale > 1.0 else Image.Resampling.LANCZOS
            scaled_image = self.current_pil_image.resize((new_width, new_height), resample)
        else:
            scaled_image = self.current_pil_image

        # Convert to QPixmap and display
        self.current_pixmap = pil_to_qpixmap(scaled_image)
        self.image_label.setPixmap(self.current_pixmap)
        self.image_label.adjustSize()

        # Update status
        self.status_bar.showMessage(
            f"Image: {orig_width}x{orig_height} | Display: {new_width}x{new_height} ({self.ZOOM_LABELS[self.zoom_slider.value()]})"
        )

    def display_image(self, pil_image):
        """Display a PIL Image in the scroll area."""
        self.current_pil_image = pil_image
        self.btn_export.setEnabled(True)

        # Update window title with dimensions
        width, height = pil_image.size
        self.setWindowTitle(f"CoCo Image Viewer - {width}x{height}")

        # Display with current zoom level
        self.update_displayed_image()

    def export_png(self):
        """Export current image as PNG."""
        if not self.current_pil_image:
            self.status_bar.showMessage("No image to export")
            return

        # Get save path
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Image as PNG",
            "",
            "PNG files (*.png);;All files (*.*)"
        )

        if not filepath:
            return

        # Ensure .png extension
        if not filepath.lower().endswith('.png'):
            filepath += '.png'

        try:
            self.current_pil_image.save(filepath, 'PNG')
            width, height = self.current_pil_image.size
            self.status_bar.showMessage(f"Exported: {filepath} ({width}x{height})")
        except Exception as e:
            self.status_bar.showMessage(f"Export failed: {str(e)}")

    def on_file_select(self, item):
        if not self.dsk:
            return

        # Get the entry from the item's data
        selected_entry = item.data(Qt.ItemDataRole.UserRole)
        if not selected_entry:
            return

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
