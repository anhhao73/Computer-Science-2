"""Hai tab quản lý xe/tài xế; service quyết định ràng buộc duy nhất và tải."""
from views.main_window import DataTable
import logging
import re
import tkinter as tk
from decimal import Decimal
from tkinter import ttk, messagebox
from models import Vehicle, Driver, BusinessError


class FleetPanel(ttk.Frame):
    def __init__(self, parent, kind, service=None, on_changed=None):
        super().__init__(parent, padding=12)
        self.kind, self.service, self.on_changed = kind, service, on_changed
        self.loaded = False
        self.rows = {}
        self.selected_id = None
        self.spec = [('plate_number', 'Biển số'), ('capacity_kg', 'Tải trọng (kg)')] if kind == 'vehicle' else [('name', 'Họ tên'), ('phone', 'Điện thoại'), ('license_number', 'Số bằng lái')]
        self.fields = {key: tk.StringVar(self) for key, _ in self.spec}
        self.notice = tk.StringVar(self, value='Chưa nạp dữ liệu.')
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)
        holder = ttk.LabelFrame(self, text='Danh sách xe' if kind == 'vehicle' else 'Danh sách tài xế', padding=10)
        holder.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        columns = ['id'] + list(self.fields)
        self.table = DataTable(holder, columns=columns, show='headings', selectmode='browse', height=8)
        for key, title in [('id', 'ID')] + self.spec:
            self.table.heading(key, text=title)
            self.table.column(key, width=60 if key == 'id' else 145, minwidth=60, anchor='w')
        self.table.grid(row=0, column=0, sticky='nsew')
        for orient, command, row, col, sticky in [('vertical', self.table.yview, 0, 1, 'ns'), ('horizontal', self.table.xview, 1, 0, 'ew')]:
            bar = ttk.Scrollbar(holder, orient=orient, command=command)
            bar.grid(row=row, column=col, sticky=sticky)
            self.table.configure(**{('yscrollcommand' if orient == 'vertical' else 'xscrollcommand'): bar.set})
        self.table.bind('<<TreeviewSelect>>', self.select_row)
        form = ttk.LabelFrame(self, text='Thông tin xe' if kind == 'vehicle' else 'Thông tin tài xế', padding=12)
        form.grid(row=0, column=1, sticky='nsew')
        form.columnconfigure(0, weight=1)
        for index, (key, title) in enumerate(self.spec):
            ttk.Label(form, text=title + ':').grid(row=index*2, column=0, sticky='w', pady=(8, 4))
            ttk.Entry(form, textvariable=self.fields[key]).grid(row=index*2+1, column=0, sticky='ew')
        actions = ttk.Frame(form)
        actions.grid(row=6, column=0, sticky='w', pady=16)
        self.add_button = ttk.Button(actions, text='Thêm', style='Primary.TButton', command=lambda: self.save(False))
        self.add_button.pack(side='left')
        self.update_button = ttk.Button(actions, text='Cập nhật', command=lambda: self.save(True))
        self.update_button.pack(side='left', padx=6)
        self.refresh_button = ttk.Button(actions, text='Làm mới', command=self.reset)
        self.refresh_button.pack(side='left')
        help_text = 'Tải trọng dùng dấu chấm thập phân, không phân cách hàng nghìn.\nKhông thể giảm tải trọng thấp hơn lượng hàng của chuyến đang chờ hoặc đang chạy.' if kind == 'vehicle' else 'Điện thoại giữ nguyên số 0 đầu.\nSố bằng lái phải duy nhất.'
        ttk.Label(form, text=help_text, wraplength=300, style='Muted.TLabel').grid(row=7, column=0, sticky='w')
        ttk.Label(self, textvariable=self.notice, style='Muted.TLabel').grid(row=1, column=0, columnspan=2, sticky='w', pady=10)
        self._buttons()

    def _buttons(self):
        self.add_button.configure(state='normal' if self.service is not None else 'disabled')
        self.update_button.configure(state='normal' if self.service is not None and self.selected_id is not None else 'disabled')

    def _error(self, error):
        if isinstance(error, (BusinessError, ValueError)):
            messagebox.showwarning('Không thể thực hiện', str(error), parent=self)
        else:
            logging.getLogger(__name__).error('Thao tác %s thất bại (%s)', self.kind, type(error).__name__)
            messagebox.showerror('Lỗi hệ thống', 'Không thể xử lý yêu cầu. Vui lòng thử lại.', parent=self)

    def refresh(self):
        if self.service is None:
            return False
        try:
            items = getattr(self.service, 'list_' + self.kind + 's')()
        except Exception as error:
            self.loaded = False
            self.notice.set('Nạp thất bại; dữ liệu hiển thị có thể đã cũ.')
            self._error(error)
            return False
        self.rows = {item.id: item for item in items}
        self.selected_id = None
        children = self.table.get_children()
        if children:
            self.table.delete(*children)
        for item in items:
            values = [item.id] + [format(getattr(item, key), '.2f') if key == 'capacity_kg' else getattr(item, key) for key in self.fields]
            self.table.insert('', 'end', iid=str(item.id), values=values)
        self.loaded = True
        self.notice.set(f'Hiển thị {len(items)} bản ghi. Chọn một dòng để cập nhật.')
        self._buttons()
        return True

    def select_row(self, event=None):
        selection = self.table.selection()
        item = self.rows.get(int(selection[0])) if selection else None
        self.selected_id = item.id if item is not None else None
        if item is not None:
            for key, variable in self.fields.items():
                variable.set(str(getattr(item, key)))
        self._buttons()

    def clear_form(self):
        self.selected_id = None
        self.table.selection_remove(*self.table.selection())
        for variable in self.fields.values():
            variable.set('')
        self._buttons()

    def reset(self):
        if self.service is None or self.refresh():
            self.clear_form()

    def save(self, update=False):
        if self.service is None:
            return
        try:
            if update and self.selected_id is None:
                raise ValueError('Hãy chọn một dòng để cập nhật.')
            data = {key: variable.get() for key, variable in self.fields.items()}
            if self.kind == 'vehicle':
                value = data['capacity_kg'].strip()
                if not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?', value):
                    raise ValueError('Tải trọng phải là số, dùng dấu chấm thập phân và không phân cách hàng nghìn.')
                data['capacity_kg'] = Decimal(value)
                item = Vehicle(self.selected_id or 0, **data)
            else:
                item = Driver(self.selected_id or 0, **data)
            args = [getattr(item, key) for key in self.fields]
            if update:
                args.insert(0, self.selected_id)
            getattr(self.service, ('update_' if update else 'create_') + self.kind)(*args)
        except Exception as error:
            self._error(error)
            return
        self.clear_form()
        if self.refresh():
            self.notice.set('Đã lưu. ' + self.notice.get())
        else:
            self.notice.set('Đã lưu nhưng chưa tải lại được danh sách. Hãy nhấn Làm mới.')
        self.event_generate('<<FleetChanged>>', when='tail')
        if self.on_changed:
            self.on_changed()


class FleetView(ttk.Frame):
    def __init__(self, parent, service=None, on_changed=None):
        super().__init__(parent, padding=12)
        self.loaded = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        ttk.Label(self, text='Xe và tài xế', style='Title.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 12))
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky='nsew')
        self.vehicle_panel = FleetPanel(self.notebook, 'vehicle', service, on_changed)
        self.driver_panel = FleetPanel(self.notebook, 'driver', service, on_changed)
        self.notebook.add(self.vehicle_panel, text='Xe')
        self.notebook.add(self.driver_panel, text='Tài xế')

    def set_service(self, service):
        self.loaded = False
        for panel in (self.vehicle_panel, self.driver_panel):
            panel.service = service
            panel.loaded = False
            panel._buttons()

    def refresh(self):
        vehicles = self.vehicle_panel.refresh()
        drivers = self.driver_panel.refresh()
        self.loaded = vehicles and drivers
        return self.loaded
