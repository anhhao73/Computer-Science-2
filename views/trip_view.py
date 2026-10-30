"""Điều phối chuyến; chỉ dùng API TMSService và một luồng Tkinter."""
from views.main_window import DataTable
import logging
import re
import tkinter as tk
from datetime import date
from tkinter import ttk, messagebox
from models import BusinessError


class TripView(ttk.Frame):
    STATUSES = {'PENDING': 'Chờ khởi hành', 'IN_TRANSIT': 'Đang vận chuyển', 'COMPLETED': 'Hoàn thành'}

    def __init__(self, parent, service=None, on_changed=None):
        super().__init__(parent, padding=12)
        self.service, self.on_changed = service, on_changed
        self.loaded = False
        self.detail = None
        self.vehicles, self.drivers, self.trips = {}, {}, {}
        self.vehicle_ids, self.driver_ids = {}, {}
        self.vehicle_label, self.driver_label = tk.StringVar(self), tk.StringVar(self)
        self.departure = tk.StringVar(self, value=date.today().isoformat())
        self.summary = tk.StringVar(self, value='Chọn một chuyến để xem chi tiết.')
        self.notice = tk.StringVar(self, value='Chưa nạp dữ liệu.')
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1, minsize=150)
        self.rowconfigure(3, weight=2)
        form = ttk.LabelFrame(self, text='Tạo chuyến • Ngày theo YYYY-MM-DD', padding=10)
        form.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        ttk.Label(form, text='Xe:').grid(row=0, column=0, padx=5)
        self.vehicle_combo = ttk.Combobox(form, textvariable=self.vehicle_label, state='readonly', width=24)
        self.vehicle_combo.grid(row=0, column=1, sticky='ew')
        ttk.Label(form, text='Tài xế:').grid(row=0, column=2, padx=5)
        self.driver_combo = ttk.Combobox(form, textvariable=self.driver_label, state='readonly', width=20)
        self.driver_combo.grid(row=0, column=3, sticky='ew')
        ttk.Label(form, text='Ngày:').grid(row=0, column=4, padx=5)
        ttk.Entry(form, textvariable=self.departure, width=12).grid(row=0, column=5)
        self.create_button = ttk.Button(form, text='Tạo chuyến', style='Primary.TButton', command=self.create_trip)
        self.create_button.grid(row=0, column=6, padx=(10, 0))
        self.trip_table = self._table(self, 'Danh sách chuyến xe', ('id', 'vehicle', 'driver', 'date', 'status'),
                                      ('Mã chuyến', 'Xe', 'Tài xế', 'Ngày đi', 'Trạng thái'), 1, 3)
        self.trip_table.bind('<<TreeviewSelect>>', self.select_trip)
        ttk.Label(self, textvariable=self.summary, style='Subtitle.TLabel').grid(row=2, column=0, sticky='w', pady=10)
        lists = ttk.Frame(self)
        lists.grid(row=3, column=0, sticky='nsew')
        lists.columnconfigure(0, weight=1, uniform='orders')
        lists.columnconfigure(2, weight=1, uniform='orders')
        lists.rowconfigure(0, weight=1)
        cols, titles = ('id', 'customer', 'weight'), ('Mã đơn', 'Mã khách hàng', 'Khối lượng (kg)')
        self.available_table = self._table(lists, 'Đơn chưa phân công', cols, titles, 0, 5, 0)
        self.assigned_table = self._table(lists, 'Đơn trong chuyến được chọn', cols, titles, 0, 5, 2)
        controls = ttk.Frame(lists, padding=8)
        controls.grid(row=0, column=1)
        self.assign_button = ttk.Button(controls, text='Thêm vào →', command=lambda: self.change_order(True))
        self.assign_button.pack(pady=5)
        self.remove_button = ttk.Button(controls, text='← Bỏ khỏi', command=lambda: self.change_order(False))
        self.remove_button.pack(pady=5)
        for table in (self.available_table, self.assigned_table):
            table.bind('<<TreeviewSelect>>', lambda event: self._buttons())
        actions = ttk.Frame(self)
        actions.grid(row=4, column=0, sticky='ew', pady=10)
        self.start_button = ttk.Button(actions, text='Khởi hành', style='Primary.TButton', command=lambda: self.transition('start'))
        self.start_button.pack(side='left')
        self.complete_button = ttk.Button(actions, text='Hoàn thành', command=lambda: self.transition('complete'))
        self.complete_button.pack(side='left', padx=8)
        self.refresh_button = ttk.Button(actions, text='Làm mới', command=self.refresh)
        self.refresh_button.pack(side='left')
        ttk.Label(actions, text='Chờ khởi hành → Đang vận chuyển → Hoàn thành', style='Muted.TLabel').pack(side='right')
        ttk.Label(self, textvariable=self.notice, style='Muted.TLabel').grid(row=5, column=0, sticky='w')
        self._buttons()

    def _table(self, parent, title, columns, titles, row, height, column=0):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=row, column=column, sticky='nsew')
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        table = DataTable(frame, columns=columns, show='headings', selectmode='browse', height=height)
        for key, label in zip(columns, titles):
            table.heading(key, text=label)
            table.column(key, width=70 if key == 'id' else 135, minwidth=60)
        table.grid(row=0, column=0, sticky='nsew')
        for orient, command, r, c, sticky in [('vertical', table.yview, 0, 1, 'ns'), ('horizontal', table.xview, 1, 0, 'ew')]:
            bar = ttk.Scrollbar(frame, orient=orient, command=command)
            bar.grid(row=r, column=c, sticky=sticky)
            table.configure(**{('yscrollcommand' if orient == 'vertical' else 'xscrollcommand'): bar.set})
        return table

    def _buttons(self):
        connected = self.service is not None
        pending = connected and self.detail is not None and self.detail.status == 'PENDING'
        for button, enabled in [(self.create_button, connected), (self.refresh_button, connected),
            (self.assign_button, pending and bool(self.available_table.selection())),
            (self.remove_button, pending and bool(self.assigned_table.selection())),
            (self.start_button, pending and bool(self.detail.orders)),
            (self.complete_button, connected and self.detail is not None and self.detail.status == 'IN_TRANSIT')]:
            button.configure(state='normal' if enabled else 'disabled')

    def _error(self, error):
        if isinstance(error, (BusinessError, ValueError)):
            messagebox.showwarning('Không thể thực hiện', str(error), parent=self)
        else:
            logging.getLogger(__name__).error('Thao tác chuyến thất bại (%s)', type(error).__name__)
            messagebox.showerror('Lỗi hệ thống', 'Không thể xử lý yêu cầu. Vui lòng thử lại.', parent=self)

    def set_service(self, service):
        self.service = service
        self.loaded = False
        self.detail = None
        self._buttons()

    def refresh_resources(self):
        if self.service is None:
            return False
        try:
            vehicles = self.service.list_vehicles()
            drivers = self.service.list_drivers()
            self._apply_resources(vehicles, drivers)
            self._summary()
            return True
        except Exception as error:
            self.loaded = False
            self.notice.set('Không tải được xe/tài xế. Hãy nhấn Làm mới.')
            self._error(error)
            return False

    def _apply_resources(self, vehicles, drivers):
        vid = self.vehicle_ids.get(self.vehicle_label.get())
        did = self.driver_ids.get(self.driver_label.get())
        self.vehicles, self.drivers = {v.id: v for v in vehicles}, {d.id: d for d in drivers}
        self.vehicle_ids = {f'#{v.id} — {v.plate_number} ({v.capacity_kg:.2f} kg)': v.id for v in vehicles}
        self.driver_ids = {f'#{d.id} — {d.name}': d.id for d in drivers}
        for combo, variable, mapping, ident in [(self.vehicle_combo, self.vehicle_label, self.vehicle_ids, vid), (self.driver_combo, self.driver_label, self.driver_ids, did)]:
            combo.configure(values=list(mapping))
            variable.set(next((label for label, value in mapping.items() if value == ident), ''))
        self._render_trips()

    @staticmethod
    def _replace(table, rows):
        children = table.get_children()
        if children:
            table.delete(*children)
        for ident, values in rows:
            table.insert('', 'end', iid=str(ident), values=values)

    def _render_trips(self):
        # Cập nhật tại chỗ để sự kiện chọn dòng không lặp khi đổi tên xe/tài xế.
        for iid in self.trip_table.get_children():
            if int(iid) not in self.trips:
                self.trip_table.delete(iid)
        for trip in self.trips.values():
            vehicle, driver = self.vehicles.get(trip.vehicle_id), self.drivers.get(trip.driver_id)
            values = (trip.id, vehicle.plate_number if vehicle else f'#{trip.vehicle_id}', driver.name if driver else f'#{trip.driver_id}', str(trip.departure_date), self.STATUSES.get(trip.status, trip.status))
            if self.trip_table.exists(str(trip.id)):
                self.trip_table.item(str(trip.id), values=values)
            else:
                self.trip_table.insert('', 'end', iid=str(trip.id), values=values)

    def _summary(self):
        if self.detail is None:
            self.summary.set('Chọn một chuyến để xem chi tiết.')
        else:
            vehicle = self.vehicles.get(self.detail.vehicle_id)
            capacity = f'{vehicle.capacity_kg:.2f}' if vehicle else '?'
            self.summary.set(f'Chuyến #{self.detail.id} • {self.STATUSES.get(self.detail.status, self.detail.status)} • Tổng tải: {self.detail.total_weight():.2f} / {capacity} kg')

    def refresh(self, trip_id=None):
        if self.service is None:
            return False
        selected = self.trip_table.selection()
        ident = trip_id if trip_id is not None else (int(selected[0]) if selected else None)
        try:
            vehicles, drivers = self.service.list_vehicles(), self.service.list_drivers()
            trips = self.service.list_trips()
            available = self.service.list_orders(unassigned_only=True)
            detail = self.service.get_trip_details(ident) if ident is not None and any(t.id == ident for t in trips) else None
        except Exception as error:
            self.loaded = False
            self.detail = None
            self._replace(self.assigned_table, [])
            self._summary()
            self._buttons()
            self.notice.set('Nạp thất bại; danh sách có thể đã cũ. Các thao tác chuyến đã khóa.')
            self._error(error)
            return False
        self.trips = {t.id: t for t in trips}
        self._apply_resources(vehicles, drivers)
        self.detail = detail
        self._replace(self.available_table, [(o.id, (o.id, f'#{o.customer_id}', f'{o.weight_kg:.2f}')) for o in available])
        self._replace(self.assigned_table, [(o.id, (o.id, f'#{o.customer_id}', f'{o.weight_kg:.2f}')) for o in detail.orders] if detail else [])
        if detail:
            self.trip_table.selection_set(str(detail.id))
        self.loaded = True
        self._summary()
        self._buttons()
        self.notice.set(f'{len(trips)} chuyến • {len(available)} đơn chưa phân công.')
        return True

    def select_trip(self, event=None):
        if getattr(self.winfo_toplevel(), 'io_busy', False):
            return
        selected = self.trip_table.selection()
        if not selected:
            self.detail = None
            self._replace(self.assigned_table, [])
            self._summary()
            self._buttons()
        elif self.detail is None or self.detail.id != int(selected[0]):
            try:
                detail = self.service.get_trip_details(int(selected[0]))
            except Exception as error:
                self.detail = None
                self._replace(self.assigned_table, [])
                self._summary()
                self._buttons()
                self._error(error)
                return
            self.detail = detail
            self._replace(self.assigned_table, [(o.id, (o.id, f'#{o.customer_id}', f'{o.weight_kg:.2f}')) for o in detail.orders])
            self._summary()
            self._buttons()

    def _saved(self, trip_id):
        ok = self.refresh(trip_id)
        self.notice.set(('Đã lưu. ' + self.notice.get()) if ok else 'Đã lưu nhưng chưa tải lại được dữ liệu. Hãy nhấn Làm mới.')
        if self.on_changed:
            self.on_changed()

    def create_trip(self):
        if self.service is None:
            return
        try:
            vid, did = self.vehicle_ids.get(self.vehicle_label.get()), self.driver_ids.get(self.driver_label.get())
            if vid is None or did is None:
                raise ValueError('Hãy chọn xe và tài xế trong danh sách.')
            text = self.departure.get().strip()
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', text):
                raise ValueError('Ngày phải có dạng YYYY-MM-DD.')
            try:
                departure = date.fromisoformat(text)
            except ValueError:
                raise ValueError('Ngày khởi hành không tồn tại.') from None
            ident = self.service.create_trip(vid, did, departure)
        except Exception as error:
            self._error(error)
            return
        self.vehicle_label.set('')
        self.driver_label.set('')
        self._saved(ident)

    def change_order(self, assign):
        if self.service is None:
            return
        try:
            if self.detail is None or self.detail.status != 'PENDING':
                raise ValueError('Hãy chọn chuyến đang chờ để thêm/bỏ đơn.')
            table = self.available_table if assign else self.assigned_table
            selection = table.selection()
            if not selection:
                raise ValueError('Hãy chọn đơn cần thao tác.')
            ident = self.detail.id
            method = self.service.assign_order_to_trip if assign else self.service.remove_order_from_trip
            method(int(selection[0]), ident)
        except Exception as error:
            self._error(error)
            return
        self._saved(ident)

    def transition(self, action):
        if self.service is None:
            return
        try:
            starting = action == 'start'
            expected = 'PENDING' if starting else 'IN_TRANSIT'
            if self.detail is None or self.detail.status != expected:
                raise ValueError('Trạng thái chuyến không cho phép thao tác này.')
            if starting and not self.detail.orders:
                raise ValueError('Chuyến rỗng không được khởi hành.')
            ident = self.detail.id
            verb = 'Khởi hành' if starting else 'Hoàn thành'
            if not messagebox.askyesno('Xác nhận', f'{verb} chuyến #{ident}?', parent=self):
                return
            (self.service.start_trip if starting else self.service.complete_trip)(ident)
        except Exception as error:
            self._error(error)
            return
        self._saved(ident)
