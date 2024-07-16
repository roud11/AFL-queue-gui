import os
import sys
import subprocess

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QDockWidget,
                             QTextBrowser, QLineEdit, QPushButton, QListWidget, QAction)


def parse_filename(folder_path):
    if not os.path.isdir(folder_path):
        print(f"Error when specifying a path '{folder_path}'")
        return []

    parsed_files = []
    subfolders = ['queue', 'crashes', 'hangs']

    for subfolder in subfolders:
        subfolder_path = os.path.join(folder_path, subfolder)
        if not os.path.isdir(subfolder_path):
            continue

        try:
            files = sorted(os.listdir(subfolder_path))
        except Exception as e:
            print(f"Error reading a folder'{subfolder_path}': {e}")
            continue

        for filename in files:
            parts = filename.split(',')
            file_dict = {}

            for part in parts:
                key_value = part.split(':')
                if len(key_value) == 2:
                    key, value = key_value[0].strip(), key_value[1].strip()

                    if key in ['id', 'time', 'execs', 'rep']:
                        try:
                            value = int(value)
                        except ValueError:
                            pass

                    if key == 'src':
                        if '+' in value:
                            try:
                                value = [int(v) for v in value.split('+')]
                            except ValueError:
                                value = [value]
                        else:
                            try:
                                value = [int(value)]
                            except ValueError:
                                value = [value]

                    file_dict[key] = value
            file_dict['filename'] = filename
            file_dict['folder'] = subfolder
            parsed_files.append(file_dict)

    return parsed_files


def reformat_dict(parsed_files):
    id_to_element = {file_dict.get('id'): file_dict for file_dict in parsed_files}

    for file_dict in parsed_files:
        src_values = file_dict.get('src')
        if not src_values or file_dict.get('folder') in ['crashes', 'hangs']:
            continue

        for src_value in src_values:
            try:
                parent_element = id_to_element.get(src_value)
                if parent_element:
                    parent_element.setdefault('children', []).append(file_dict['id'])
            except Exception as e:
                print(f"Error when adding a child to a parent item: {e}")

    return parsed_files


class InfoDockWidget(QDockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Info')
        self.setWidget(QTextBrowser())
        self.text_browser = self.widget()

    def update_info(self, file_dict):
        self.text_browser.clear()
        if file_dict:
            fields = ['orig', 'id', 'src', 'time', 'execs', 'op', 'rep']
            for field in fields:
                if file_dict.get(field):
                    self.text_browser.append(f"{field.capitalize()}: {file_dict.get(field)}")


class HexDumpDockWidget(QDockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Hex Dump')
        self.setWidget(QTextBrowser())
        self.text_browser = self.widget()

    def update_hex_dump(self, html_content):
        self.text_browser.setHtml(html_content)


def generate_hex_dump(file_path):
    if not os.path.isfile(file_path):
        return f"Error: No such file '{file_path}'"

    try:
        command = f"hexyl {file_path} 2>&1 | ./terminal-to-html-3.14.0-linux-amd64 -preview"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout
    except Exception as e:
        return str(e)


class FilterWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Input ID")
        self.search_input.returnPressed.connect(self.search)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search)

        self.result_list = QListWidget()
        self.result_list.currentItemChanged.connect(self.select_item)

        layout.addWidget(self.search_input)
        layout.addWidget(self.search_button)
        layout.addWidget(self.result_list)

        self.setLayout(layout)

    def search(self):
        search_term = self.search_input.text()
        self.result_list.clear()

        if search_term:
            try:
                matching_items = [file_dict for file_dict in self.main_window.parsed_files if
                                  search_term in str(file_dict.get('id', ''))]

                for item in matching_items:
                    self.result_list.addItem(f"{item['folder']}: {item['id']}")

            except ValueError as e:
                print(f"Search error {e}")

    def select_item(self, item):
        if item:
            folder, item_id = item.text().split(': ')
            item_id = int(item_id)
            self.main_window.select_item_in_tree(folder, item_id)


class MainWindow(QMainWindow):
    def __init__(self, parsed_files):
        super().__init__()
        self.setWindowTitle("AFL++ output list")
        self.setGeometry(300, 200, 1200, 700)
        self.parsed_files = parsed_files
        self.id_to_element = {file_dict['id']: file_dict for file_dict in parsed_files}

        self.tree = QTreeWidget()
        self.info_dock = InfoDockWidget()
        self.hex_dump_dock = HexDumpDockWidget()
        self.filter_dock = QDockWidget("Filter", self)
        self.filter_widget = FilterWidget(self)

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        self.tree.setHeaderLabels(["ID", "Src", "Index"])
        self.populate_tree(self.parsed_files)
        main_layout.addWidget(self.tree)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        self.addDockWidget(Qt.RightDockWidgetArea, self.info_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.hex_dump_dock)

        self.filter_dock.setWidget(self.filter_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.filter_dock)

        self.tree.currentItemChanged.connect(self.show_item_info)
        self.create_menu()

    def create_menu(self):
        menubar = self.menuBar()
        run_menu = menubar.addMenu("Run widgets")

        info_action = QAction("Info", self)
        info_action.triggered.connect(self.show_info_dock)
        run_menu.addAction(info_action)

        hex_dump_action = QAction("Hex Dump", self)
        hex_dump_action.triggered.connect(self.show_hex_dump_dock)
        run_menu.addAction(hex_dump_action)

        filter_action = QAction("Filter", self)
        filter_action.triggered.connect(self.show_filter_dock)
        run_menu.addAction(filter_action)

    def show_info_dock(self):
        self.info_dock.setVisible(True)

    def show_hex_dump_dock(self):
        self.hex_dump_dock.setVisible(True)

    def show_filter_dock(self):
        self.filter_dock.setVisible(True)

    def populate_tree(self, parsed_files):
        folder_items = {'queue': {}, 'crashes': {}, 'hangs': {}}
        index_map = {'queue': 'Q', 'crashes': 'C', 'hangs': 'H'}

        for file_dict in parsed_files:
            index = index_map[file_dict['folder']]
            tree_item = QTreeWidgetItem([str(file_dict["id"]), ', '.join(map(str, file_dict.get("src", []))), index])
            folder_items[file_dict['folder']][file_dict["id"]] = tree_item

        for file_dict in parsed_files:
            if not file_dict.get("src") or file_dict['folder'] in ['crashes', 'hangs']:
                self.tree.addTopLevelItem(folder_items[file_dict['folder']][file_dict["id"]])

        for file_dict in parsed_files:
            if file_dict['folder'] not in ['crashes', 'hangs']:
                tree_item = folder_items[file_dict['folder']][file_dict["id"]]
                for parent_id in file_dict.get("src", []):
                    parent_item = folder_items['queue'].get(parent_id)
                    if parent_item:
                        parent_item.addChild(tree_item)

    def show_item_info(self, item):
        try:
            item_id = int(item.text(0))
            index = item.text(2)
            folder = {'Q': 'queue', 'C': 'crashes', 'H': 'hangs'}[index]

            file_dict = None
            for d in self.parsed_files:
                if d["id"] == item_id and d['folder'] == folder:
                    file_dict = d
                    break

            if file_dict:
                self.info_dock.update_info(file_dict)
                if 'filename' in file_dict:
                    file_path = os.path.join(folder_path, file_dict['folder'], file_dict['filename'])
                    hex_dump_html = generate_hex_dump(file_path)
                    self.hex_dump_dock.update_hex_dump(hex_dump_html)
        except Exception as e:
            print(f"Error in displaying item information: {e}")

    def select_item_in_tree(self, folder, item_id):
        items = self.tree.findItems(str(item_id), Qt.MatchExactly | Qt.MatchRecursive, 0)
        if items:
            for item in items:
                if item.text(2) == {'queue': 'Q', 'crashes': 'C', 'hangs': 'H'}[folder]:
                    self.tree.setCurrentItem(item)
                    self.show_item_info(item)
                    break


if __name__ == '__main__':
    app = QApplication(sys.argv)

    if len(sys.argv) != 2:
        print('Use: python3 Try.py /path/to/folder')
        sys.exit(1)

    folder_path = sys.argv[1]

    try:
        parsed_files = parse_filename(folder_path)
        reformatted_files = reformat_dict(parsed_files)
    except Exception as e:
        print(f"Error during file processing: {e}")
        sys.exit(1)

    main_win = MainWindow(reformatted_files)
    main_win.show()

    sys.exit(app.exec_())
