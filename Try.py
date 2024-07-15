import os
import sys
import subprocess

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QDockWidget,
                             QTextBrowser, QLineEdit, QPushButton, QListWidget, QHBoxLayout, QMenuBar, QMenu, QAction)


def parse_filename(folder_path):
    if not os.path.isdir(folder_path):
        print(f"Ошибка при указании пути '{folder_path}'")
        return []

    parsed_files = []

    for subfolder in ['queue', 'crashes', 'hangs']:
        subfolder_path = os.path.join(folder_path, subfolder)
        if not os.path.isdir(subfolder_path):
            continue

        files = sorted(os.listdir(subfolder_path))
        for filename in files:
            parts = filename.split(',')
            file_dict = {}

            for part in parts:
                key_value = part.split(':')
                if len(key_value) == 2:
                    key = key_value[0].strip()
                    value = key_value[1].strip()

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
    id_to_element = {}

    for file_dict in parsed_files:
        id_value = file_dict.get('id')
        id_to_element[id_value] = file_dict

    for file_dict in parsed_files:
        src_values = file_dict.get('src')
        if src_values is None or file_dict.get('folder') in ['crashes', 'hangs']:
            continue

        for src_value in src_values:
            try:
                parent_element = id_to_element.get(src_value)
                if parent_element:
                    if 'children' not in parent_element:
                        parent_element['children'] = [file_dict['id']]
                    else:
                        parent_element['children'].append(file_dict['id'])
            except ValueError:
                continue

    return parsed_files


def print_hierarchy(node, node_dict, level=0):
    indent = "--" * level
    #print(f"{indent}'id': {node['id']}")
    children = node.get('children', [])
    for child_id in children:
        child_node = node_dict[child_id]
        print_hierarchy(child_node, node_dict, level + 1)


# Класс для дополнительного окна (вывод параметров)
class InfoDockWidget(QDockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Info')
        self.setWidget(QTextBrowser())
        self.text_browser = self.widget()

    def update_info(self, file_dict):
        self.text_browser.clear()
        if file_dict:
            if file_dict.get('orig'):
                self.text_browser.append(f"Orig: {file_dict.get('orig')}")
            if file_dict.get('id'):
                self.text_browser.append(f"ID: {file_dict.get('id')}")
            if file_dict.get('src'):
                self.text_browser.append(f"Src: {file_dict.get('src')}")
            if file_dict.get('time'):
                self.text_browser.append(f"Time: {file_dict.get('time')}")
            if file_dict.get('execs'):
                self.text_browser.append(f"Execs: {file_dict.get('execs')}")
            if file_dict.get('op'):
                self.text_browser.append(f"Op: {file_dict.get('op')}")
            if file_dict.get('rep'):
                self.text_browser.append(f"Rep: {file_dict.get('rep')}")


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
                    self.result_list.addItem(str(item['id']))

            except ValueError:
                pass

    def select_item(self, item):
        item_id = int(item.text())
        self.main_window.select_item_in_tree(item_id)


class MainWindow(QMainWindow):
    def __init__(self, parsed_files):
        super().__init__()
        self.setWindowTitle("Список queue")
        self.setGeometry(300, 200, 1200, 700)

        self.parsed_files = parsed_files

        main_widget = QWidget()
        main_layout = QVBoxLayout()

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["ID", "Src", "Index"])

        self.id_to_element = {file_dict['id']: file_dict for file_dict in parsed_files}
        self.populate_tree(parsed_files)

        main_layout.addWidget(self.tree)
        main_widget.setLayout(main_layout)

        self.setCentralWidget(main_widget)

        self.info_dock = InfoDockWidget()
        self.addDockWidget(Qt.RightDockWidgetArea, self.info_dock)

        self.hex_dump_dock = HexDumpDockWidget()
        self.addDockWidget(Qt.RightDockWidgetArea, self.hex_dump_dock)

        self.filter_dock = QDockWidget("Filter", self)
        self.filter_widget = FilterWidget(self)
        self.filter_dock.setWidget(self.filter_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.filter_dock)

        self.tree.currentItemChanged.connect(self.show_item_info)

        # Добавляем меню
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
        c_top_level_items = {}
        h_top_level_items = {}
        q_top_level_items = {}

        for file_dict in parsed_files:
            index = {'queue': 'Q', 'crashes': 'C', 'hangs': 'H'}[file_dict['folder']]
            tree_item = QTreeWidgetItem([str(file_dict["id"]), ', '.join(map(str, file_dict.get("src", []))), index])
            if file_dict['folder'] == 'queue':
                q_top_level_items[file_dict["id"]] = tree_item
            elif file_dict['folder'] == 'crashes':
                c_top_level_items[file_dict["id"]] = tree_item
            elif file_dict['folder'] == 'hangs':
                h_top_level_items[file_dict["id"]] = tree_item

        for file_dict in parsed_files:
            if file_dict['folder'] == 'queue':
                if not file_dict.get("src"):
                    self.tree.addTopLevelItem(q_top_level_items[file_dict["id"]])
            elif file_dict['folder'] == 'crashes':
                self.tree.addTopLevelItem(c_top_level_items[file_dict["id"]])
            elif file_dict['folder'] == 'hangs':
                self.tree.addTopLevelItem(h_top_level_items[file_dict["id"]])

        for file_dict in parsed_files:
            if file_dict['folder'] not in ['crashes', 'hangs']:
                tree_item = q_top_level_items[file_dict["id"]]
                for parent_id in file_dict.get("src", []):
                    parent_item = q_top_level_items[parent_id]
                    parent_item.addChild(tree_item)

    def show_item_info(self, item):
        item_id = int(item.text(0))
        file_dict = next((d for d in self.parsed_files if d["id"] == item_id), None)
        self.info_dock.update_info(file_dict)
        if file_dict and 'filename' in file_dict:
            file_path = os.path.join(folder_path, file_dict['folder'], file_dict['filename'])
            hex_dump_html = generate_hex_dump(file_path)
            self.hex_dump_dock.update_hex_dump(hex_dump_html)

    def select_item_in_tree(self, item_id):
        items = self.tree.findItems(str(item_id), Qt.MatchExactly | Qt.MatchRecursive, 0)
        if items:
            item = items[0]
            self.tree.setCurrentItem(item)
            self.show_item_info(item)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Проверка наличия одного аргумента
    if len(sys.argv) != 2:
        print('Используйте: python3 Try.py /path/to/folder')
        sys.exit(1)

    folder_path = sys.argv[1]
    parsed_files = parse_filename(folder_path)
    # if not parsed_files:
    #     sys.exit(1)
    reformatted_files = reformat_dict(parsed_files)

    main_win = MainWindow(reformatted_files)
    main_win.show()

    # Вывод
    # for file_dict in reformatted_files:
    #     print(file_dict)

    root_node = reformatted_files[0]

    print_hierarchy(root_node, reformatted_files)

    sys.exit(app.exec_())