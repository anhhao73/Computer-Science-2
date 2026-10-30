"""Quản lý đơn vận chuyển qua TMSService, không truy vấn SQL từ giao diện."""
from views.main_window import DataTable

import logging
import re
import tkinter as tk
from decimal import Decimal
from tkinter import messagebox, ttk

from models import BusinessError, TransportOrder


class OrderView(ttk.Frame):
    STATUSES = {'PENDING': 'Chờ khởi hành', 'IN_TRANSIT': 'Đang vận chuyển', 'COMPLETED': 'Hoàn thành'}

    def __init__(self, parent, service=None, on_changed=None):
        super().__init__(parent, padding=16)
        self.service = service
        self.on_changed = on_changed
        self.loaded = False
        self.orders = {}
        self.customers = {}
        self.customer_ids = {}
        self.trips = {}
        self.selected_id = None
        self.unassigned = tk.BooleanVar(self, False)
        self.customer_label = tk.StringVar(self)
        self.fields = {key: tk.StringVar(self) for key in ('pickup_address', 'delivery_address', 'weight_kg', 'freight_amount')}
        self.notice = tk.StringVar(self, value='Chưa nạp dữ liệu.')
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(self, text='Đơn vận chuyển', style='Title.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 10))
        toolbar = ttk.Frame(self)
        toolbar.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        self.filter_button = ttk.Checkbutton(toolbar, text='Chỉ đơn chưa phân công', variable=self.unassigned, command=self.refresh)
        self.filter_button.pack(side='left')
        self.refresh_button = ttk.Button(toolbar, text='Làm mới', command=self.refresh)
        self.refresh_button.pack(side='right')
        holder = ttk.Frame(self)
        holder.grid(row=2, column=0, sticky='nsew')
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        columns = ('id', 'customer', 'weight', 'freight', 'trip', 'status')
        self.table = DataTable(holder, columns=columns, show='headings', selectmode='browse', height=5)
        for key, title, width in zip(columns, ('Mã đơn', 'Khách hàng', 'Khối lượng (kg)', 'Giá cước (VND)', 'Chuyến', 'Trạng thái'), (70, 250, 130, 150, 80, 170)):
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=65, anchor='w')
        self.table.grid(row=0, column=0, sticky='nsew')
        for orient, command, row, column, sticky in [('vertical', self.table.yview, 0, 1, 'ns'), ('horizontal', self.table.xview, 1, 0, 'ew')]:
            bar = ttk.Scrollbar(holder, orient=orient, command=command)
            bar.grid(row=row, column=column, sticky=sticky)
            self.table.configure(**{('yscrollcommand' if orient == 'vertical' else 'xscrollcommand'): bar.set})
        self.table.bind('<<TreeviewSelect>>', self.select_order)
        ttk.Label(self, textvariable=self.notice, style='Muted.TLabel').grid(row=3, column=0, sticky='w', pady=8)
        form = ttk.LabelFrame(self, text='Thông tin đơn vận chuyển', padding=12)
        form.grid(row=4, column=0, sticky='ew')
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        ttk.Label(form, text='Khách hàng:').grid(row=0, column=0, sticky='w', padx=(0, 14), pady=5)
        self.customer_combo = ttk.Combobox(form, textvariable=self.customer_label, state='readonly')
        self.customer_combo.grid(row=0, column=1, columnspan=3, sticky='ew', pady=5)
        for key, title, row, col in (
            ('pickup_address', 'Địa chỉ lấy hàng:', 1, 0),
            ('delivery_address', 'Địa chỉ giao hàng:', 1, 2),
            ('weight_kg', 'Khối lượng (kg):', 2, 0),
            ('freight_amount', 'Giá cước (VND):', 2, 2),
        ):
            ttk.Label(form, text=title).grid(row=row, column=col, sticky='w', padx=(12 if col else 0, 10), pady=5)
            ttk.Entry(form, textvariable=self.fields[key], width=18).grid(row=row, column=col+1, sticky='ew', pady=5)
        actions = ttk.Frame(form)
        actions.grid(row=3, column=0, columnspan=4, sticky='w', pady=8)
        self.create_button = ttk.Button(actions, text='Tạo đơn', style='Primary.TButton', command=lambda: self.save(False))
        self.create_button.pack(side='left')
        self.update_button = ttk.Button(actions, text='Cập nhật', command=lambda: self.save(True))
        self.update_button.pack(side='left', padx=8)
        ttk.Button(actions, text='Làm mới', command=self.reset).pack(side='left')
        ttk.Label(form, text='Chỉ sửa đơn chưa phân công. Số nhập không có dấu phân cách hàng nghìn.', style='Muted.TLabel').grid(row=4, column=0, columnspan=4, sticky='w')
        self._buttons()

    def _buttons(self):
        connected = self.service is not None
        for button in (self.create_button, self.refresh_button, self.filter_button):
            button.configure(state='normal' if connected else 'disabled')
        item = self.orders.get(self.selected_id)
        self.update_button.configure(state='normal' if connected and item is not None and item.trip_id is None else 'disabled')

    def set_service(self, service):
        self.service = service
        self.loaded = False
        self._buttons()
        self.refresh_customers()

    def _error(self, error):
        if isinstance(error, (BusinessError, ValueError)):
            messagebox.showwarning('Không thể thực hiện', str(error), parent=self)
        else:
            logging.getLogger(__name__).error('Thao tác đơn thất bại (%s)', type(error).__name__)
            messagebox.showerror('Lỗi hệ thống', 'Không thể xử lý yêu cầu. Vui lòng thử lại.', parent=self)

    def _apply_customers(self, rows):
        chosen_id = self.customer_ids.get(self.customer_label.get())
        self.customers = {item.id: item for item in rows}
        self.customer_ids = {f'#{item.id} — {item.name}': item.id for item in rows}
        self.customer_combo.configure(values=list(self.customer_ids))
        self.customer_label.set(next((label for label, ident in self.customer_ids.items() if ident == chosen_id), ''))

    def refresh_customers(self):
        if self.service is None:
            return False
        try:
            rows = self.service.list_customers()
            self._apply_customers(rows)
            self._render()
            return True
        except Exception as error:
            self.loaded = False
            self.notice.set('Chưa cập nhật được danh sách khách hàng; hãy nhấn Làm mới.')
            self._error(error)
            return False

    def _render(self):
        # Cập nhật hàng tại chỗ để đổi tên khách hàng không mất form đang nhập.
        for iid in self.table.get_children():
            if int(iid) not in self.orders:
                self.table.delete(iid)
        for item in self.orders.values():
            customer = self.customers.get(item.customer_id)
            label = f'#{item.customer_id} — {customer.name}' if customer else f'#{item.customer_id} (không tìm thấy)'
            trip = self.trips.get(item.trip_id)
            status = 'Chưa phân công' if item.trip_id is None else self.STATUSES.get(trip.status if trip else None, 'Không rõ trạng thái')
            values = (item.id, label, f'{item.weight_kg:.2f}', f'{item.freight_amount:.2f}', '—' if item.trip_id is None else f'#{item.trip_id}', status)
            if self.table.exists(str(item.id)):
                self.table.item(str(item.id), values=values)
            else:
                self.table.insert('', 'end', iid=str(item.id), values=values)

    def refresh(self):
        if self.service is None:
            return False
        try:
            customers = self.service.list_customers()
            orders = self.service.list_orders(unassigned_only=self.unassigned.get())
            trips = self.service.list_trips()
        except Exception as error:
            self.loaded = False
            self.selected_id = None
            self._buttons()
            self.notice.set('Nạp thất bại; danh sách đang hiển thị có thể đã cũ.')
            self._error(error)
            return False
        self._apply_customers(customers)
        self.orders = {item.id: item for item in orders}
        self.trips = {item.id: item for item in trips}
        if self.selected_id not in self.orders:
            self.selected_id = None
        self._render()
        self.loaded = True
        self.notice.set(f'Hiển thị {len(orders)} đơn vận chuyển.')
        self._buttons()
        return True

    def select_order(self, event=None):
        selection = self.table.selection()
        if not selection:
            self.selected_id = None
            self._buttons()
            return
        item = self.orders.get(int(selection[0]))
        if item is None:
            return
        # Bỏ qua sự kiện lặp khi chỉ cập nhật tên khách hàng trên bảng.
        if self.selected_id == item.id:
            return
        self.selected_id = item.id
        self.customer_label.set(next((label for label, ident in self.customer_ids.items() if ident == item.customer_id), ''))
        for key, variable in self.fields.items():
            variable.set(str(getattr(item, key)))
        self.notice.set(f'Đang chọn đơn #{item.id}.' + (' Đơn đã phân công, không được cập nhật.' if item.trip_id is not None else ''))
        self._buttons()

    @staticmethod
    def _number(text, label):
        text = text.strip()
        if not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?', text):
            raise ValueError(f'{label}: nhập số dùng dấu chấm thập phân, không phân cách hàng nghìn.')
        return Decimal(text)

    def clear_form(self):
        self.selected_id = None
        self.table.selection_remove(*self.table.selection())
        self.customer_label.set('')
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
            if update:
                selected = self.orders.get(self.selected_id)
                if selected is None:
                    raise ValueError('Hãy chọn đơn cần cập nhật.')
                if selected.trip_id is not None:
                    raise ValueError('Chỉ được sửa đơn chưa phân công.')
            customer_id = self.customer_ids.get(self.customer_label.get())
            if customer_id is None:
                raise ValueError('Hãy chọn khách hàng trong danh sách.')
            item = TransportOrder(0, customer_id,
                                  self.fields['pickup_address'].get(), self.fields['delivery_address'].get(),
                                  self._number(self.fields['weight_kg'].get(), 'Khối lượng'),
                                  self._number(self.fields['freight_amount'].get(), 'Giá cước'))
            args = (customer_id, item.pickup_address, item.delivery_address, item.weight_kg, item.freight_amount)
            if update:
                self.service.update_order(self.selected_id, *args)
            else:
                self.service.create_order(*args)
        except Exception as error:
            self._error(error)
            return
        self.clear_form()
        if self.refresh():
            self.notice.set('Đã lưu đơn. ' + self.notice.get())
        else:
            self.notice.set('Đã lưu đơn nhưng chưa tải lại được danh sách. Hãy nhấn Làm mới.')
        self.event_generate('<<OrdersChanged>>', when='tail')
        if self.on_changed is not None:
            self.on_changed()
