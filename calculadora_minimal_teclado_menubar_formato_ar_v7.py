
import json
import math
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

APP_TITLE = "Calc"
DATA_FILE = "calculadora_teclado_data.json"


class DecimalLineEdit(QLineEdit):
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Period:
            mods = event.modifiers()
            if not (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
                self.insert(",")
                return
        super().keyPressEvent(event)


@dataclass
class HistoryItem:
    expression: str
    result: str
    timestamp: str
    raw_result: float = 0.0


class Storage:
    @staticmethod
    def default_data():
        return {
            "memories": {},
            "variables": {"a": 0, "b": 0, "c": 0},
            "history": [],
            "theme": "light",
            "display_decimals": 2,
        }

    @staticmethod
    def load():
        if not os.path.exists(DATA_FILE):
            return Storage.default_data()
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            defaults = Storage.default_data()
            defaults.update(data)
            return defaults
        except Exception:
            return Storage.default_data()

    @staticmethod
    def save(memories, variables, history, theme, display_decimals):
        payload = {
            "memories": memories,
            "variables": variables,
            "history": [asdict(item) for item in history],
            "theme": theme,
            "display_decimals": display_decimals,
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


class NumberFormatter:
    @staticmethod
    def format_int_digits(digits: str) -> str:
        digits = digits or "0"
        parts = []
        while len(digits) > 3:
            parts.insert(0, digits[-3:])
            digits = digits[:-3]
        parts.insert(0, digits)
        return ".".join(parts)

    @staticmethod
    def format_display_number(token: str, complete_decimal=False) -> str:
        if not token:
            return token

        has_decimal = "," in token
        if has_decimal:
            last_comma = token.rfind(",")
            int_raw = token[:last_comma]
            dec_raw = token[last_comma + 1:]
            int_digits = "".join(ch for ch in int_raw if ch.isdigit())
            dec_digits = "".join(ch for ch in dec_raw if ch.isdigit())
            if complete_decimal:
                if dec_digits == "":
                    dec_digits = "00"
                elif len(dec_digits) == 1:
                    dec_digits = dec_digits + "0"
            int_fmt = NumberFormatter.format_int_digits(int_digits)
            return int_fmt + "," + dec_digits

        int_digits = "".join(ch for ch in token if ch.isdigit())
        return NumberFormatter.format_int_digits(int_digits)

    @staticmethod
    def to_eval_number(token: str) -> str:
        if not token:
            return token

        if "," in token:
            last_comma = token.rfind(",")
            int_raw = token[:last_comma]
            dec_raw = token[last_comma + 1:]
            int_digits = "".join(ch for ch in int_raw if ch.isdigit()) or "0"
            dec_digits = "".join(ch for ch in dec_raw if ch.isdigit())
            if dec_digits:
                return int_digits + "." + dec_digits
            return int_digits + ".0"

        int_digits = "".join(ch for ch in token if ch.isdigit()) or "0"
        return int_digits

    @staticmethod
    def format_expression_for_display(expr: str, complete_decimal=False) -> str:
        parts = []
        i = 0
        while i < len(expr):
            ch = expr[i]

            if ch.isalpha() or ch == "_":
                j = i + 1
                while j < len(expr) and (expr[j].isalnum() or expr[j] == "_"):
                    j += 1
                parts.append(expr[i:j])
                i = j
                continue

            if ch.isdigit():
                j = i + 1
                while j < len(expr) and (expr[j].isdigit() or expr[j] in ".,"):
                    j += 1
                parts.append(NumberFormatter.format_display_number(expr[i:j], complete_decimal=complete_decimal))
                i = j
                continue

            parts.append(ch)
            i += 1

        return "".join(parts)

    @staticmethod
    def normalize_expression_for_eval(expr: str) -> str:
        parts = []
        i = 0
        while i < len(expr):
            ch = expr[i]

            if ch.isalpha() or ch == "_":
                j = i + 1
                while j < len(expr) and (expr[j].isalnum() or expr[j] == "_"):
                    j += 1
                parts.append(expr[i:j])
                i = j
                continue

            if ch.isdigit():
                j = i + 1
                while j < len(expr) and (expr[j].isdigit() or expr[j] in ".,"):
                    j += 1
                parts.append(NumberFormatter.to_eval_number(expr[i:j]))
                i = j
                continue

            parts.append(ch)
            i += 1

        normalized = "".join(parts).replace("^", "**")
        normalized = re.sub(r"(\d+(?:\.\d+)?)%", r"(\1/100)", normalized)
        return normalized

    @staticmethod
    def format_result(value, decimals=2):
        try:
            numeric = float(value)
        except Exception:
            return str(value)

        if abs(numeric) < 0.0000000001:
            numeric = 0.0

        decimals = max(0, int(decimals))
        negative = numeric < 0
        numeric = abs(numeric)

        text = f"{numeric:.{decimals}f}"
        if "." in text:
            int_part, dec_part = text.split(".", 1)
            result = NumberFormatter.format_int_digits(int_part)
            if decimals > 0:
                result += "," + dec_part
        else:
            result = NumberFormatter.format_int_digits(text)

        zero_text = "0" if decimals == 0 else ("0," + ("0" * decimals))
        if negative and result != zero_text:
            result = "-" + result
        return result


class Engine:
    ALLOWED_PATTERN = re.compile(r"^[0-9a-zA-Z_\s\+\-\*/\(\)\.,\^%]+$")
    NAME_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")

    @staticmethod
    def validate(expr: str):
        if not expr:
            raise ValueError("La expresión está vacía.")
        if not Engine.ALLOWED_PATTERN.match(expr):
            raise ValueError("Hay caracteres no permitidos.")

    @staticmethod
    def safe_context():
        return {
            "pi": math.pi,
            "e": math.e,
            "sqrt": math.sqrt,
            "abs": abs,
            "round": round,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
        }

    @staticmethod
    def evaluate(expr: str, variables: dict, memories: dict):
        Engine.validate(expr)
        expr = NumberFormatter.normalize_expression_for_eval(expr)

        context = {}
        context.update(Engine.safe_context())
        context.update(variables)
        context.update(memories)

        names = set(Engine.NAME_PATTERN.findall(expr))
        unknown = [n for n in names if n not in context]
        if unknown:
            raise ValueError(f"No definido: {', '.join(unknown)}")

        try:
            value = eval(expr, {"__builtins__": {}}, context)
        except ZeroDivisionError:
            raise ValueError("No se puede dividir por cero.")
        except Exception as e:
            raise ValueError(f"Expresión inválida: {e}")

        if isinstance(value, complex):
            raise ValueError("No se permiten complejos.")
        return value


class NameValueDialog(QDialog):
    def __init__(self, title, name_text="", value_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedWidth(260)

        self.name_edit = QLineEdit(name_text)
        self.value_edit = DecimalLineEdit(value_text)
        self._formatting = False
        self.value_edit.textEdited.connect(self.on_value_edited)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Nombre", self.name_edit)
        form.addRow("Valor", self.value_edit)
        layout.addLayout(form)

        row = QHBoxLayout()
        ok = QPushButton("Aceptar")
        cancel = QPushButton("Cancelar")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        layout.addLayout(row)

    def on_value_edited(self, _text):
        if self._formatting:
            return

        current = self.value_edit.text()
        cursor = self.value_edit.cursorPosition()
        prefix = current[:cursor]

        formatted_all = NumberFormatter.format_expression_for_display(current)
        formatted_prefix = NumberFormatter.format_expression_for_display(prefix)
        new_cursor = len(formatted_prefix)

        self._formatting = True
        with QSignalBlocker(self.value_edit):
            self.value_edit.setText(formatted_all)
            self.value_edit.setCursorPosition(min(new_cursor, len(formatted_all)))
        self._formatting = False

    def values(self):
        name = self.name_edit.text().strip()
        value = NumberFormatter.format_expression_for_display(
            self.value_edit.text().strip(),
            complete_decimal=True,
        )
        return name, value


class CompactListDialog(QDialog):
    def __init__(self, title, items: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(290, 350)
        self.selected_name = None
        self._items_ref = items

        self.list_widget = QListWidget()
        self.refresh()
        self.list_widget.itemDoubleClicked.connect(self.use_selected)

        insert_btn = QPushButton("Insertar")
        edit_btn = QPushButton("Editar")
        delete_btn = QPushButton("Borrar")
        close_btn = QPushButton("Cerrar")

        insert_btn.clicked.connect(self.use_selected)
        edit_btn.clicked.connect(self.edit_selected)
        delete_btn.clicked.connect(self.delete_selected)
        close_btn.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        row.addWidget(insert_btn)
        row.addWidget(edit_btn)
        row.addWidget(delete_btn)
        layout.addLayout(row)
        layout.addWidget(close_btn)

    def _fmt(self, value):
        decimals = getattr(self.parent(), "display_decimals", 2)
        return NumberFormatter.format_result(value, decimals)

    def current_name(self):
        item = self.list_widget.currentItem()
        if not item:
            return None
        return item.text().split("=")[0].strip()

    def use_selected(self):
        name = self.current_name()
        if name:
            self.selected_name = name
            self.accept()

    def edit_selected(self):
        name = self.current_name()
        if not name:
            return
        current = self._items_ref[name]
        dlg = NameValueDialog("Editar", name, self._fmt(current), self)
        if dlg.exec():
            new_name, new_value = dlg.values()
            if not new_name:
                return
            try:
                val = float(Engine.evaluate(new_value, {}, {}))
            except Exception:
                QMessageBox.warning(self, "Error", "Valor inválido.")
                return
            if new_name != name:
                del self._items_ref[name]
            self._items_ref[new_name] = val
            self.refresh()

    def delete_selected(self):
        name = self.current_name()
        if not name:
            return
        del self._items_ref[name]
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        for name, value in sorted(self._items_ref.items()):
            self.list_widget.addItem(f"{name} = {self._fmt(value)}")


class HistoryDialog(QDialog):
    def __init__(self, history: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historial")
        self.setModal(True)
        self.setFixedSize(300, 360)
        self.history = history
        self.selected_expression = None
        self.selected_result = None

        self.list_widget = QListWidget()
        self.refresh()

        use_expr = QPushButton("Usar expr.")
        use_res = QPushButton("Usar res.")
        clear_btn = QPushButton("Vaciar")
        close_btn = QPushButton("Cerrar")

        use_expr.clicked.connect(self.use_expression)
        use_res.clicked.connect(self.use_result)
        clear_btn.clicked.connect(self.clear_history)
        close_btn.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        row.addWidget(use_expr)
        row.addWidget(use_res)
        row.addWidget(clear_btn)
        layout.addLayout(row)
        layout.addWidget(close_btn)

    def refresh(self):
        self.list_widget.clear()
        decimals = getattr(self.parent(), "display_decimals", 2)
        for item in self.history:
            if hasattr(item, "raw_result"):
                item.result = NumberFormatter.format_result(item.raw_result, decimals)
            self.list_widget.addItem(f"{item.expression} = {item.result}")

    def current_index(self):
        return self.list_widget.currentRow()

    def use_expression(self):
        i = self.current_index()
        if i < 0 or i >= len(self.history):
            return
        self.selected_expression = self.history[i].expression
        self.accept()

    def use_result(self):
        i = self.current_index()
        if i < 0 or i >= len(self.history):
            return
        decimals = getattr(self.parent(), "display_decimals", 2)
        current_item = self.history[i]
        if hasattr(current_item, "raw_result"):
            formatted_result = NumberFormatter.format_result(current_item.raw_result, decimals)
            current_item.result = formatted_result
            self.selected_result = formatted_result
        else:
            self.selected_result = current_item.result
        self.accept()

    def clear_history(self):
        self.history.clear()
        self.refresh()


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayuda")
        self.setModal(True)
        self.setFixedSize(340, 320)

        text = QLabel(
            "Ingreso por teclado\n\n"
            "Enter  → calcular\n"
            "Esc    → limpiar operación\n"
            "F1     → ayuda\n"
            "Alt+A  → abrir menú Acciones\n"
            "Alt+T  → abrir menú Tema\n"
            "Alt+Y  → abrir menú Ayuda\n"
            "Ctrl+M → memorias\n"
            "Ctrl+Shift+V → variables\n"
            "Ctrl+H → historial\n"
            "Ctrl+G → guardar resultado en memoria\n"
            "Ctrl+Shift+G → guardar resultado en variable\n\n"
            "Formato numérico\n"
            "Miles: punto     1.234.567\n"
            "Decimales: coma  123,45\n"
            "12, se completa como 12,00\n"
            "Decimales visibles configurables\n\n"
            "Operadores y funciones\n"
            "+  -  *  /\n"
            "^  potencia   Ej: 2^3\n"
            "sqrt(x) raíz  Ej: sqrt(25)\n"
            "%  porcentaje Ej: 50%\n"
            "() paréntesis"
        )
        text.setWordWrap(True)

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addWidget(close_btn)


class MainWindow(QMainWindow):
    THEMES = {
        "light": {
            "bg": "#ffffff",
            "fg": "#111111",
            "muted": "#777777",
            "soft": "#666666",
            "border": "#dddddd",
            "field": "#fbfbfb",
            "button": "#f6f6f6",
            "button_hover": "#ededed",
        },
        "dark": {
            "bg": "#171717",
            "fg": "#f3f3f3",
            "muted": "#b1b1b1",
            "soft": "#9a9a9a",
            "border": "#3a3a3a",
            "field": "#222222",
            "button": "#252525",
            "button_hover": "#303030",
        },
        "gray": {
            "bg": "#e6e6e6",
            "fg": "#1f1f1f",
            "muted": "#5f5f5f",
            "soft": "#4f4f4f",
            "border": "#b9b9b9",
            "field": "#f0f0f0",
            "button": "#dcdcdc",
            "button_hover": "#d2d2d2",
        },
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(320, 185)

        data = Storage.load()
        self.memories = data.get("memories", {})
        self.variables = data.get("variables", {"a": 0, "b": 0, "c": 0})
        self.history = []
        for h in data.get("history", []):
            if "raw_result" not in h:
                try:
                    h["raw_result"] = float(Engine.evaluate(h.get("result", "0"), {}, {}))
                except Exception:
                    h["raw_result"] = 0.0
            self.history.append(HistoryItem(**h))
        self.theme = data.get("theme", "light")
        self.display_decimals = int(data.get("display_decimals", 2))
        self._formatting = False

        self._build_ui()
        self._build_menus()
        self.apply_theme()
        self.setup_shortcuts()

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(10, 4, 10, 10)
        root.setSpacing(6)

        top = QHBoxLayout()
        self.title_label = QLabel("Calculadora")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.status_label = QLabel(self.summary_text())
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top.addWidget(self.title_label, 1)
        top.addWidget(self.status_label, 0)
        root.addLayout(top)

        self.operation_line = DecimalLineEdit()
        self.operation_line.setPlaceholderText("Escribí la operación y presioná Enter")
        self.operation_line.returnPressed.connect(self.calculate)
        self.operation_line.textEdited.connect(self.on_operation_edited)
        self.operation_line.editingFinished.connect(self.on_operation_finished)
        root.addWidget(self.operation_line)

        self.result_line = QLabel("0")
        self.result_line.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        root.addWidget(self.result_line)

        self.help_hint = QLabel("F1 ayuda  |  Alt+A acciones  |  Ctrl+M memorias  |  Ctrl+Shift+V variables")
        self.help_hint.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(self.help_hint)

    def _build_menus(self):
        menubar = self.menuBar()

        self.menu_actions = menubar.addMenu("&Acciones")
        self.menu_theme = menubar.addMenu("&Tema")
        self.menu_format = menubar.addMenu("&Formato")
        self.menu_help = menubar.addMenu("A&yuda")

        self.act_add_mem = QAction("Nueva memoria", self)
        self.act_add_var = QAction("Nueva variable", self)
        self.act_open_mem = QAction("Ver memorias", self)
        self.act_open_var = QAction("Ver variables", self)
        self.act_open_hist = QAction("Ver historial", self)
        self.act_save_mem = QAction("Guardar resultado en memoria", self)
        self.act_save_var = QAction("Guardar resultado en variable", self)
        self.act_clear = QAction("Limpiar operación", self)

        self.act_add_mem.triggered.connect(self.add_memory)
        self.act_add_var.triggered.connect(self.add_variable)
        self.act_open_mem.triggered.connect(self.open_memories)
        self.act_open_var.triggered.connect(self.open_variables)
        self.act_open_hist.triggered.connect(self.open_history)
        self.act_save_mem.triggered.connect(self.save_result_to_memory)
        self.act_save_var.triggered.connect(self.save_result_to_variable)
        self.act_clear.triggered.connect(self.clear_operation)

        self.menu_actions.addAction(self.act_add_mem)
        self.menu_actions.addAction(self.act_add_var)
        self.menu_actions.addSeparator()
        self.menu_actions.addAction(self.act_open_mem)
        self.menu_actions.addAction(self.act_open_var)
        self.menu_actions.addAction(self.act_open_hist)
        self.menu_actions.addSeparator()
        self.menu_actions.addAction(self.act_save_mem)
        self.menu_actions.addAction(self.act_save_var)
        self.menu_actions.addSeparator()
        self.menu_actions.addAction(self.act_clear)

        self.act_theme_light = QAction("Claro", self)
        self.act_theme_dark = QAction("Oscuro", self)
        self.act_theme_gray = QAction("Gris", self)

        self.act_theme_light.triggered.connect(lambda: self.set_theme("light"))
        self.act_theme_dark.triggered.connect(lambda: self.set_theme("dark"))
        self.act_theme_gray.triggered.connect(lambda: self.set_theme("gray"))

        self.menu_theme.addAction(self.act_theme_light)
        self.menu_theme.addAction(self.act_theme_dark)
        self.menu_theme.addAction(self.act_theme_gray)

        self.act_decimals = QAction("Decimales a mostrar", self)
        self.act_decimals.triggered.connect(self.change_display_decimals)
        self.menu_format.addAction(self.act_decimals)

        self.act_help = QAction("Ayuda", self)
        self.act_help.triggered.connect(self.show_help)
        self.menu_help.addAction(self.act_help)

    def setup_shortcuts(self):
        self.sc_mem = QShortcut(QKeySequence("Ctrl+M"), self)
        self.sc_mem.activated.connect(self.open_memories)

        self.sc_var = QShortcut(QKeySequence("Ctrl+Shift+V"), self)
        self.sc_var.activated.connect(self.open_variables)

        self.sc_hist = QShortcut(QKeySequence("Ctrl+H"), self)
        self.sc_hist.activated.connect(self.open_history)

        self.sc_save_mem = QShortcut(QKeySequence("Ctrl+G"), self)
        self.sc_save_mem.activated.connect(self.save_result_to_memory)

        self.sc_save_var = QShortcut(QKeySequence("Ctrl+Shift+G"), self)
        self.sc_save_var.activated.connect(self.save_result_to_variable)

        self.sc_clear = QShortcut(QKeySequence("Esc"), self)
        self.sc_clear.activated.connect(self.clear_operation)

        self.sc_help = QShortcut(QKeySequence("F1"), self)
        self.sc_help.activated.connect(self.show_help)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(self.act_add_mem)
        menu.addAction(self.act_add_var)
        menu.addSeparator()
        menu.addAction(self.act_open_mem)
        menu.addAction(self.act_open_var)
        menu.addAction(self.act_open_hist)
        menu.addSeparator()
        submenu_theme = menu.addMenu("Tema")
        submenu_theme.addAction(self.act_theme_light)
        submenu_theme.addAction(self.act_theme_dark)
        submenu_theme.addAction(self.act_theme_gray)
        submenu_format = menu.addMenu("Formato")
        submenu_format.addAction(self.act_decimals)
        menu.addSeparator()
        menu.addAction(self.act_help)
        menu.exec(self.mapToGlobal(pos))

    def apply_theme(self):
        c = self.THEMES.get(self.theme, self.THEMES["light"])
        self.setStyleSheet(f"""
            QWidget {{
                background: {c["bg"]};
                color: {c["fg"]};
                font-family: Segoe UI, Arial, sans-serif;
                font-size: 12px;
            }}
            QMenuBar {{
                background: {c["bg"]};
                color: {c["fg"]};
            }}
            QMenuBar::item:selected {{
                background: {c["button_hover"]};
                border-radius: 4px;
            }}
            QLineEdit {{
                border: 1px solid {c["border"]};
                border-radius: 8px;
                padding: 8px 10px;
                background: {c["field"]};
                color: {c["fg"]};
            }}
            QLabel {{
                background: transparent;
                color: {c["fg"]};
            }}
            QPushButton {{
                border: 1px solid {c["border"]};
                border-radius: 8px;
                background: {c["button"]};
                color: {c["fg"]};
                padding: 6px;
            }}
            QPushButton:hover {{
                background: {c["button_hover"]};
            }}
            QListWidget {{
                border: 1px solid {c["border"]};
                border-radius: 8px;
                background: {c["field"]};
                color: {c["fg"]};
            }}
            QMenu {{
                background: {c["field"]};
                color: {c["fg"]};
                border: 1px solid {c["border"]};
            }}
            QMenu::item:selected {{
                background: {c["button_hover"]};
            }}
        """)
        self.title_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {c['fg']};")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {c['soft']};")
        self.help_hint.setStyleSheet(f"font-size: 11px; color: {c['muted']};")
        self.operation_line.setStyleSheet(
            f"border: 1px solid {c['border']}; border-radius: 8px; padding: 8px 10px; "
            f"background: {c['field']}; color: {c['fg']}; font-size: 15px;"
        )
        self.result_line.setStyleSheet(f"font-size: 26px; font-weight: 700; padding: 2px 2px 4px 2px; color: {c['fg']};")

    def set_theme(self, theme_name):
        self.theme = theme_name
        self.apply_theme()
        self.save_all()

    def _apply_format_to_lineedit(self, lineedit, complete_decimal=False):
        current = lineedit.text()
        cursor = lineedit.cursorPosition()
        prefix = current[:cursor]

        formatted_all = NumberFormatter.format_expression_for_display(current, complete_decimal=complete_decimal)
        formatted_prefix = NumberFormatter.format_expression_for_display(prefix, complete_decimal=False)
        new_cursor = len(formatted_prefix)

        with QSignalBlocker(lineedit):
            lineedit.setText(formatted_all)
            lineedit.setCursorPosition(min(new_cursor, len(formatted_all)))

    def on_operation_edited(self, _text):
        if self._formatting:
            return
        self._formatting = True
        self._apply_format_to_lineedit(self.operation_line, complete_decimal=False)
        self._formatting = False

    def on_operation_finished(self):
        if self._formatting:
            return
        self._formatting = True
        self._apply_format_to_lineedit(self.operation_line, complete_decimal=True)
        self._formatting = False

    def calculate(self):
        expression = self.operation_line.text().strip()
        try:
            value = Engine.evaluate(expression, self.variables, self.memories)
            result_text = NumberFormatter.format_result(value, self.display_decimals)
            expr_display = NumberFormatter.format_expression_for_display(expression, complete_decimal=True)
            self.operation_line.setText(expr_display)
            self.result_line.setText(result_text)
            self.history.insert(0, HistoryItem(expr_display, result_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), float(value)))
            self.save_all()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))

    def clear_operation(self):
        self.operation_line.clear()

    def show_help(self):
        HelpDialog(self).exec()

    def add_memory(self):
        name = self.next_memory_name()
        dlg = NameValueDialog("Nueva memoria", name, self.result_line.text(), self)
        if dlg.exec():
            n, v = dlg.values()
            self.store_name_value(self.memories, self.variables, n, v, "memoria")
            self.refresh_status()

    def add_variable(self):
        dlg = NameValueDialog("Nueva variable", "a", self.result_line.text(), self)
        if dlg.exec():
            n, v = dlg.values()
            self.store_name_value(self.variables, self.memories, n, v, "variable")
            self.refresh_status()

    def store_name_value(self, target, other, name, value_text, kind):
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name or ""):
            QMessageBox.warning(self, "Error", f"Nombre de {kind} inválido.")
            return
        if name in other:
            QMessageBox.warning(self, "Error", f"Ese nombre ya existe en {'variables' if kind == 'memoria' else 'memorias'}.")
            return
        if kind == "variable" and name in Engine.safe_context():
            QMessageBox.warning(self, "Error", "Nombre reservado.")
            return
        try:
            value = float(Engine.evaluate(value_text, self.variables, self.memories))
        except Exception:
            QMessageBox.warning(self, "Error", "Valor inválido.")
            return
        target[name] = value
        self.save_all()

    def open_memories(self):
        dlg = CompactListDialog("Memorias", self.memories, self)
        if dlg.exec() and dlg.selected_name:
            self.operation_line.insert(dlg.selected_name)
        self.refresh_status()
        self.save_all()

    def open_variables(self):
        dlg = CompactListDialog("Variables", self.variables, self)
        if dlg.exec() and dlg.selected_name:
            self.operation_line.insert(dlg.selected_name)
        self.refresh_status()
        self.save_all()

    def open_history(self):
        dlg = HistoryDialog(self.history, self)
        if dlg.exec():
            if dlg.selected_expression:
                self.operation_line.setText(dlg.selected_expression)
            elif dlg.selected_result:
                self.operation_line.insert(dlg.selected_result)
        self.save_all()

    def save_result_to_memory(self):
        default_value = NumberFormatter.format_expression_for_display(self.result_line.text(), complete_decimal=True)
        name, ok = QInputDialog.getText(self, "Guardar", "Nombre de memoria:", text=self.next_memory_name())
        if ok and name.strip():
            self.store_name_value(self.memories, self.variables, name.strip(), default_value, "memoria")
            self.refresh_status()

    def save_result_to_variable(self):
        default_value = NumberFormatter.format_expression_for_display(self.result_line.text(), complete_decimal=True)
        name, ok = QInputDialog.getText(self, "Guardar", "Nombre de variable:", text="a")
        if ok and name.strip():
            self.store_name_value(self.variables, self.memories, name.strip(), default_value, "variable")
            self.refresh_status()

    def next_memory_name(self):
        i = 1
        while f"M{i}" in self.memories:
            i += 1
        return f"M{i}"

    def summary_text(self):
        return f"M:{len(self.memories)} V:{len(self.variables)}"

    def refresh_status(self):
        self.status_label.setText(self.summary_text())

    def change_display_decimals(self):
        value, ok = QInputDialog.getInt(
            self,
            "Decimales",
            "Cantidad de decimales a mostrar:",
            value=self.display_decimals,
            minValue=0,
            maxValue=8,
            step=1,
        )
        if ok:
            self.display_decimals = value
            self.refresh_display_formats()
            self.save_all()

    def refresh_display_formats(self):
        current_expr = self.operation_line.text().strip()
        if current_expr:
            self.operation_line.setText(
                NumberFormatter.format_expression_for_display(current_expr, complete_decimal=True)
            )

        result_value = self.result_line.text().strip()
        if result_value:
            try:
                numeric = Engine.evaluate(result_value, {}, {})
                self.result_line.setText(NumberFormatter.format_result(numeric, self.display_decimals))
            except Exception:
                pass

        for item in self.history:
            if hasattr(item, "raw_result"):
                item.result = NumberFormatter.format_result(item.raw_result, self.display_decimals)

    def save_all(self):
        Storage.save(self.memories, self.variables, self.history, self.theme, self.display_decimals)

    def closeEvent(self, event):
        self.save_all()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
