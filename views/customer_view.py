"""Màn hình khách hàng; mọi dữ liệu đều đi qua TMSService."""
from views.main_window import DataTable

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from models import BusinessError, Customer


class CustomerView(ttk.Frame):
    def __init__(self, parent, service=None, on_changed=None):
        super().__init__(parent, padding=16)
        self.service = service
        self.on_changed = on_changed
        self.customers = {}
        self.selected_id = None
        self.loaded = False
        self.keyword = tk.StringVar(self)
        self.fields = {key: tk.StringVar(self) for key in ('name', 'phone', 'address')}
        self.notice = tk.StringVar(self, value="Chưa kết nối dữ liệu.")
        self.selection_note = tk.StringVar(self, value="Nhập thông tin để thêm khách hàng mới.")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        ttk.Label(self, text="Khách hàng", style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))
        search = ttk.Frame(self)
        search.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Tên hoặc số điện thoại:").grid(row=0, column=0, padx=(0, 12))
        self.search_entry = ttk.Entry(search, textvariable=self.keyword)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind('<Return>', lambda event: self.refresh())
        self.search_button = ttk.Button(search, text="Tìm kiếm", command=self.refresh)
        self.search_button.grid(row=0, column=2, padx=8)
        self.refresh_button = ttk.Button(search, text="Làm mới", command=self.reset)
        self.refresh_button.grid(row=0, column=3)

        table_frame = ttk.Frame(self)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table = DataTable(table_frame, columns=('id', 'name', 'phone', 'address'),
                                  show='headings', selectmode='browse', height=6)
        for key, label, width in [('id', 'ID', 70), ('name', 'Họ tên / Tên đơn vị', 230),
                                  ('phone', 'Điện thoại', 150), ('address', 'Địa chỉ', 380)]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=60, anchor='w')
        self.table.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.bind('<<TreeviewSelect>>', self.select_customer)
        ttk.Label(self, textvariable=self.notice, style='Muted.TLabel').grid(row=3, column=0, sticky='w', pady=8)

        form = ttk.LabelFrame(self, text="Thông tin khách hàng", padding=14)
        form.grid(row=4, column=0, sticky='ew')
        form.columnconfigure(1, weight=1)
        self.entries = {}
        for row, (key, label) in enumerate([('name', 'Họ tên / Tên đơn vị:'), ('phone', 'Điện thoại:'), ('address', 'Địa chỉ:')]):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', padx=(0, 16), pady=6)
            entry = ttk.Entry(form, textvariable=self.fields[key])
            entry.grid(row=row, column=1, sticky='ew', pady=6)
            self.entries[key] = entry
        actions = ttk.Frame(form)
        actions.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(12, 0))
        self.add_button = ttk.Button(actions, text='Thêm', style='Primary.TButton', command=lambda: self.save(False))
        self.add_button.pack(side='left')
        self.update_button = ttk.Button(actions, text='Cập nhật', command=lambda: self.save(True))
        self.update_button.pack(side='left', padx=8)
        ttk.Button(actions, text='Làm mới', command=self.reset).pack(side='left')
        ttk.Label(form, textvariable=self.selection_note, style='Muted.TLabel').grid(row=4, column=0, columnspan=2, sticky='w', pady=(10, 0))
        self._buttons()

    def _buttons(self):
        state = 'normal' if self.service is not None else 'disabled'
        for button in (self.add_button, self.search_button, self.refresh_button):
            button.configure(state=state)
        self.update_button.configure(state='normal' if self.service is not None and self.selected_id is not None else 'disabled')

    def set_service(self, service):
        self.service = service
        self._buttons()
        self.refresh()

    def _error(self, error):
        if isinstance(error, (BusinessError, ValueError)):
            messagebox.showwarning('Không thể thực hiện', str(error), parent=self)
        else:
            logging.getLogger(__name__).error('Thao tác khách hàng thất bại (%s)', type(error).__name__)
            messagebox.showerror('Lỗi hệ thống', 'Không thể xử lý yêu cầu. Vui lòng thử lại.', parent=self)

    def refresh(self):
        if self.service is None:
            return False
        try:
            rows = self.service.list_customers(self.keyword.get().strip())
            customers = {item.id: item for item in rows}
        except Exception as error:
            self.loaded = False
            self.notice.set('Nạp dữ liệu thất bại; danh sách đang hiển thị có thể đã cũ.')
            self._error(error)
            return False
        self.customers = customers
        self.selected_id = None
        children = self.table.get_children()
        if children:
            self.table.delete(*children)
        for item in rows:
            self.table.insert('', 'end', iid=str(item.id), values=(item.id, item.name, item.phone, item.address))
        self.loaded = True
        self.selection_note.set('Chọn một dòng để cập nhật. Các trường đều bắt buộc.')
        self.notice.set(f'Hiển thị {len(rows)} khách hàng.' if rows else 'Không có khách hàng phù hợp.')
        self._buttons()
        return True

    def select_customer(self, event=None):
        selection = self.table.selection()
        if not selection:
            self.selected_id = None
            self._buttons()
            return
        item = self.customers.get(int(selection[0]))
        if item is None:
            return
        self.selected_id = item.id
        for key, variable in self.fields.items():
            variable.set(getattr(item, key))
        self.selection_note.set(f'Đang chọn khách hàng #{item.id}.')
        self._buttons()

    def clear_form(self):
        self.selected_id = None
        self.table.selection_remove(*self.table.selection())
        for variable in self.fields.values():
            variable.set('')
        self.selection_note.set('Nhập thông tin để thêm khách hàng mới.')
        self._buttons()

    def reset(self):
        self.keyword.set('')
        if self.service is None or self.refresh():
            self.clear_form()
            self.entries['name'].focus_set()

    def save(self, update=False):
        if self.service is None:
            return
        if update and self.selected_id is None:
            messagebox.showwarning('Chưa chọn khách hàng', 'Hãy chọn một dòng để cập nhật.', parent=self)
            return
        try:
            item = Customer(self.selected_id or 0, **{key: value.get() for key, value in self.fields.items()})
            if update:
                self.service.update_customer(self.selected_id, item.name, item.phone, item.address)
            else:
                self.service.create_customer(item.name, item.phone, item.address)
        except Exception as error:
            self._error(error)
            return
        # Chỉ thay đổi form sau khi service đã lưu thành công.
        self.clear_form()
        self.keyword.set('')
        refreshed = self.refresh()
        if refreshed:
            self.notice.set('Đã lưu khách hàng. ' + self.notice.get())
        else:
            self.notice.set('Đã lưu khách hàng, nhưng chưa tải lại được danh sách. Hãy nhấn Làm mới.')
        self.event_generate('<<CustomersChanged>>', when='tail')
        if self.on_changed is not None:
            self.on_changed()
