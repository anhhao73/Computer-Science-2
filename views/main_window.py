"""Khung Trang chủ và bốn màn hình nghiệp vụ dùng cùng TMSService.

Trang chủ nạp dữ liệu thật qua service; các tab làm mới qua callback.
"""

import tkinter as tk
import logging
from tkinter import ttk


from tkinter import ttk

BG = '#f3f6fb'
SURFACE = '#ffffff'
INK = '#152b49'
MUTED = '#52657c'
BORDER = '#dce4ef'
BLUE = '#2563eb'


def configure_theme(root):
    s = ttk.Style(root)
    s.theme_use('clam')
    s.configure('.', font=('Segoe UI', 10), foreground=INK, background=BG)
    s.configure('TFrame', background=BG)
    s.configure('TLabel', foreground=INK, background=BG)
    s.configure('Muted.TLabel', foreground=MUTED)
    s.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
    s.configure('Brand.TLabel', font=('Segoe UI', 25, 'bold'))
    s.configure('Subtitle.TLabel', font=('Segoe UI', 11))
    s.configure('Panel.TFrame', background=SURFACE, bordercolor=BORDER, borderwidth=1, relief='solid')
    s.configure('PanelInner.TFrame', background=SURFACE)
    s.configure('Panel.TLabel', background=SURFACE)
    s.configure('PanelMuted.TLabel', background=SURFACE, foreground=MUTED)
    s.configure('PanelTitle.TLabel', background=SURFACE, font=('Segoe UI', 11, 'bold'))
    s.configure('Metric.TLabel', background=SURFACE, font=('Segoe UI', 27, 'bold'))
    s.configure('TLabelframe', background=SURFACE, bordercolor=BORDER, borderwidth=1, relief='solid')
    s.configure('TLabelframe.Label', background=BG, foreground=INK, font=('Segoe UI', 10, 'bold'))
    s.configure('TButton', padding=(12, 7), background=SURFACE, bordercolor=BORDER,
                lightcolor=SURFACE, darkcolor=SURFACE, focuscolor=BLUE)
    s.map('TButton', background=[('disabled', '#edf1f6'), ('pressed', '#dbeafe'), ('active', '#eaf1fd')],
          foreground=[('disabled', '#78869a')], bordercolor=[('focus', BLUE)])
    s.configure('Primary.TButton', background=BLUE, foreground='white', bordercolor=BLUE,
                font=('Segoe UI', 10, 'bold'), lightcolor=BLUE, darkcolor=BLUE, focuscolor='white')
    s.map('Primary.TButton', background=[('disabled', '#e3eaf4'), ('pressed', '#1e40af'), ('active', '#1d4ed8')],
          foreground=[('disabled', '#64748b'), ('!disabled', 'white')])
    for style in ('TEntry', 'TCombobox'):
        s.configure(style, padding=(7, 5), fieldbackground=SURFACE, background=SURFACE,
                    bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE, arrowsize=13)
        s.map(style, bordercolor=[('focus', BLUE)], fieldbackground=[('readonly', SURFACE), ('disabled', '#edf1f6')],
              foreground=[('disabled', '#78869a')])
    s.configure('TCheckbutton', background=BG, padding=(0, 4), focuscolor=BLUE)
    s.map('TCheckbutton', background=[('active', BG)])
    s.configure('Treeview', rowheight=30, borderwidth=0, background=SURFACE,
                fieldbackground=SURFACE, bordercolor=BORDER, foreground=INK)
    s.configure('Treeview.Heading', background='#eaf0f8', foreground=INK, relief='flat',
                font=('Segoe UI', 10, 'bold'), padding=(6, 6), bordercolor=BORDER)
    s.map('Treeview', background=[('selected', '#dbeafe')], foreground=[('selected', '#123f87')])
    s.configure('TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 8))
    s.configure('TNotebook.Tab', padding=(16, 8), background=BG, borderwidth=0)
    s.map('TNotebook.Tab', background=[('selected', SURFACE), ('active', '#e7eef9')],
          foreground=[('selected', BLUE)], lightcolor=[('selected', SURFACE)])
    s.configure('Horizontal.TProgressbar', background=BLUE, troughcolor='#e3eaf4', borderwidth=0)
    root.option_add('*TCombobox*Listbox.font', ('Segoe UI', 10))
    root.option_add('*TCombobox*Listbox.selectBackground', BLUE)


def polish_forms(widget, inside=False):
    inside = inside or isinstance(widget, ttk.LabelFrame)
    if inside:
        if isinstance(widget, ttk.Label):
            style = str(widget.cget('style'))
            widget.configure(style='PanelMuted.TLabel' if 'Muted' in style else 'Panel.TLabel')
        elif isinstance(widget, ttk.Frame):
            widget.configure(style='PanelInner.TFrame')
    for child in widget.winfo_children():
        polish_forms(child, inside)


class DataTable(ttk.Treeview):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tag_configure('even', background=SURFACE)
        self.tag_configure('odd', background='#f5f8fc')
        self._stripe = 0

    def insert(self, parent, index, iid=None, **kwargs):
        kwargs.setdefault('tags', ('odd' if self._stripe % 2 else 'even',))
        self._stripe += 1
        return super().insert(parent, index, iid=iid, **kwargs)


from decimal import Decimal
from datetime import datetime
from models import BusinessError
import logging


class DashboardMixin:
    STATUS_ITEMS = (
        ('PENDING', 'Chờ khởi hành', '#f0b323'),
        ('IN_TRANSIT', 'Đang vận chuyển', '#2985df'),
        ('COMPLETED', 'Hoàn thành', '#29a66a'),
    )

    def refresh_home(self):
        self.refresh_button.configure(state='normal' if self.service else 'disabled')
        if self.service is None:
            return False
        try:
            data = self.service.get_dashboard_data()
            counts, rows = data['counts'], data['rows']
        except Exception as error:
            message = str(error) if isinstance(error, BusinessError) else 'Không thể đọc dữ liệu tổng quan.'
            if not isinstance(error, BusinessError):
                logging.getLogger(__name__).error('Dashboard refresh failed (%s)', type(error).__name__)
            self.pending_note.set('Chưa cập nhật được. Số liệu đang hiển thị có thể đã cũ. ' + message)
            return False
        # Publish only after every read and calculation succeeds.
        self.dashboard_data = data
        for key, code in [('pending', 'PENDING'), ('in_transit', 'IN_TRANSIT'), ('completed', 'COMPLETED')]:
            self.metric_values[key].set(str(counts[code]))
        self.metric_values['unassigned'].set(str(data['unassigned']))
        selection = self.pending_table.selection()
        self.pending_table.delete(*self.pending_table.get_children())
        for ident, day, plate, driver, weight, capacity in rows:
            self.pending_table.insert('', 'end', iid=str(ident), values=(
                f'#{ident}', day, plate, driver, f'{weight:.2f} / {capacity:.2f} kg'))
        if selection and self.pending_table.exists(selection[0]):
            self.pending_table.selection_set(selection[0])
        self.pending_note.set(f'{len(rows)} chuyến đang chờ • Biểu đồ tải: {min(3, len(rows))} chuyến có ngày đi sớm nhất • Cập nhật {datetime.now():%H:%M:%S}')
        self.draw_status_chart()
        self.draw_load_chart()
        return True

    def draw_status_chart(self, event=None):
        canvas = self.status_canvas
        canvas.delete('all')
        width = canvas.winfo_width() if canvas.winfo_width() > 1 else canvas.winfo_reqwidth()
        height = canvas.winfo_height() if canvas.winfo_height() > 1 else canvas.winfo_reqheight()
        radius = max(20, min(height / 2 - 10, width * .22, 110))
        cx, cy = width * .23, height / 2
        bounds = (cx-radius, cy-radius, cx+radius, cy+radius)
        data = self.dashboard_data
        counts = data['counts'] if data else {}
        total = sum(counts.values())
        canvas.create_oval(*bounds, fill='#e5ebf2', outline='')
        start = 90
        for code, label, color in self.STATUS_ITEMS:
            count = counts.get(code, 0)
            if not count or not total:
                continue
            extent = 360 * count / total
            if count == total:
                canvas.create_oval(*bounds, fill=color, outline='')
            else:
                canvas.create_arc(*bounds, start=start, extent=-extent, fill=color, outline=self.SURFACE)
            start -= extent
        inner = radius * .55
        canvas.create_oval(cx-inner, cy-inner, cx+inner, cy+inner, fill=self.SURFACE, outline='')
        canvas.create_text(cx, cy-10, text=str(total) if data else '—', fill=self.INK, font=('Segoe UI', 24, 'bold'))
        canvas.create_text(cx, cy+20, text='chuyến', fill=self.INK, font=('Segoe UI', 10))
        x = width * .49
        for i, (code, label, color) in enumerate(self.STATUS_ITEMS):
            y = cy - 32 + i * 32
            canvas.create_rectangle(x, y-6, x+12, y+6, fill=color, outline='')
            canvas.create_text(x+22, y, text=f'{label}: {counts.get(code, 0)}' if data else label,
                               anchor='w', fill=self.INK, font=('Segoe UI', 10))

    def draw_load_chart(self, event=None):
        canvas = self.load_canvas
        canvas.delete('all')
        width = canvas.winfo_width() if canvas.winfo_width() > 1 else canvas.winfo_reqwidth()
        height = canvas.winfo_height() if canvas.winfo_height() > 1 else canvas.winfo_reqheight()
        rows = self.dashboard_data['rows'][:3] if self.dashboard_data else []
        if not rows:
            canvas.create_text(width/2, height/2, text='Không có chuyến đang chờ' if self.dashboard_data else 'Chưa nạp dữ liệu tải trọng',
                               fill=self.MUTED, font=('Segoe UI', 11))
            return
        for i, (ident, _, _, _, weight, capacity) in enumerate(rows):
            ratio = weight / capacity if capacity > 0 else Decimal('0')
            y = (i + .5) * height / 3
            left, right = 95, width - 65
            canvas.create_text(0, y, text=f'Chuyến #{ident}', anchor='w', fill=self.INK, font=('Segoe UI', 10))
            canvas.create_rectangle(left, y-11, right, y+11, fill='#e2e7ee', outline=self.BORDER)
            if ratio > 0:
                color = '#d74747' if ratio > 1 else '#f0b323' if ratio >= Decimal('.9') else '#2985df'
                canvas.create_rectangle(left, y-11, left+(right-left)*float(min(ratio, 1)), y+11, fill=color, outline='')
            canvas.create_text(width-2, y, text=f'{ratio * 100:.1f}%', anchor='e', fill=self.INK, font=('Segoe UI', 10))


class MainWindow(DashboardMixin, tk.Tk):
    """Một Tk gốc, chuyển giữa Trang chủ và Notebook nghiệp vụ."""

    BACKGROUND = BG
    SURFACE = SURFACE
    BORDER = BORDER
    INK = INK
    MUTED = MUTED
    BLUE = BLUE
    SECTIONS = (
        ("customers", "Khách hàng"),
        ("fleet", "Xe và tài xế"),
        ("orders", "Đơn vận chuyển"),
        ("trips", "Chuyến xe"),
    )

    def __init__(self, service=None, on_reconnect=None):
        super().__init__()
        self.service = service
        self.on_reconnect = on_reconnect
        self.io_busy = False
        self._busy_timer = None
        self.dashboard_data = None
        self.title("Mini TMS — Quản lý vận chuyển")
        self.geometry("1180x820")
        self.minsize(1000, 780)
        self.configure(background=self.BACKGROUND)
        self._configure_styles()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.content = ttk.Frame(self, padding=(20, 16, 20, 8))
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.home = ttk.Frame(self.content)
        self.workspace = ttk.Frame(self.content)
        self.home.grid(row=0, column=0, sticky="nsew")
        self.workspace.grid(row=0, column=0, sticky="nsew")
        self._build_home()
        self._build_workspace()
        polish_forms(self.content)

        self.status = tk.StringVar(
            self,
            value="Mini TMS • Đang chờ kết nối dữ liệu",
        )
        footer = ttk.Frame(self, padding=(20, 8, 20, 12))
        footer.grid(row=1, column=0, sticky='ew')
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status, style="Muted.TLabel").grid(row=0, column=0, sticky='w')
        self.reconnect_button = ttk.Button(footer, text='Kết nối lại', command=self.reconnect,
                                           state='normal' if on_reconnect else 'disabled')
        self.reconnect_button.grid(row=0, column=1, padx=(8, 0))
        self.io_progress = ttk.Progressbar(footer, mode='indeterminate', length=100)
        self.io_progress.grid(row=0, column=2, padx=(10, 0))
        self.io_progress.grid_remove()
        self.io_label = ttk.Label(footer, text='Đang xử lý…', style='Muted.TLabel')
        self.io_label.grid(row=0, column=3, padx=(8, 0))
        self.io_label.grid_remove()
        self.bind('<F5>', lambda event: self.refresh_visible())
        self.bind('<Alt-Home>', lambda event: None if self.io_busy else self.show_home())
        self.show_home()

    def refresh_visible(self):
        if self.io_busy:
            return
        if self.home.winfo_ismapped():
            self.refresh_home()
        else:
            for view in self.section_frames.values():
                if self.notebook.select() == str(view):
                    view.refresh()
                    break

    def set_io_busy(self, busy):
        self.io_busy = busy
        if busy:
            self.tk.call('tk', 'busy', 'hold', self.content)
            self.reconnect_button.state(['disabled'])
            self._busy_timer = self.after(120, self._show_io_progress)
        else:
            if self._busy_timer is not None:
                self.after_cancel(self._busy_timer)
                self._busy_timer = None
            self.io_progress.stop()
            self.io_progress.grid_remove()
            self.io_label.grid_remove()
            self.tk.call('tk', 'busy', 'forget', self.content)
            if self.on_reconnect:
                self.reconnect_button.state(['!disabled'])

    def _show_io_progress(self):
        self._busy_timer = None
        if self.io_busy:
            self.io_progress.grid()
            self.io_label.grid()
            self.io_progress.start(12)

    def reconnect(self):
        """Reconnect explicitly; never replay a failed write or clear a draft."""
        if self.on_reconnect is None:
            return
        self.reconnect_button.configure(state='disabled')
        self.status.set('Đang kết nối MySQL…')
        self.update_idletasks()
        try:
            self.on_reconnect()
        finally:
            self.reconnect_button.configure(state='normal')

    def refresh_after_reconnect(self):
        for view in self.section_frames.values():
            view.loaded = False
        # Existing refresh methods preserve form values.
        ok = self.refresh_home()
        for view in self.section_frames.values():
            if view.refresh() is False:
                ok = False
        self.status.set('Đã kết nối MySQL • Dữ liệu đã cập nhật' if ok else
                        'Đã kết nối MySQL • Một phần dữ liệu chưa tải được; hãy thử Làm mới.')

    def _configure_styles(self):
        configure_theme(self)

    def _panel(self, parent):
        return ttk.Frame(parent, style="Panel.TFrame", padding=12)

    def _build_home(self):
        self.home.columnconfigure(0, weight=1)
        self.home.rowconfigure(2, weight=3, minsize=215)
        self.home.rowconfigure(3, weight=2)

        header = ttk.Frame(self.home)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="MINI TMS", style="Brand.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Label(header, text="Tổng quan vận chuyển", style="Subtitle.TLabel").grid(
            row=1, column=0, sticky="w")
        self.scope = ttk.Combobox(header, values=("Tất cả dữ liệu",),
                                  state="readonly", width=19)
        self.scope.set("Tất cả dữ liệu")
        self.scope.grid(row=0, column=1, rowspan=2, padx=(12, 10))
        self.refresh_button = ttk.Button(header, text="Làm mới", state="disabled", command=self.refresh_home)
        self.refresh_button.grid(row=0, column=2, rowspan=2)

        metrics = ttk.Frame(self.home)
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.metric_values = {}
        labels = (
            ("unassigned", "Đơn chưa phân công"),
            ("pending", "Chuyến chờ khởi hành"),
            ("in_transit", "Chuyến đang vận chuyển"),
            ("completed", "Chuyến hoàn thành"),
        )
        for column, (key, label) in enumerate(labels):
            metrics.columnconfigure(column, weight=1, uniform="metrics")
            panel = self._panel(metrics)
            panel.grid(row=0, column=column, sticky="nsew",
                       padx=(0 if column == 0 else 6, 0 if column == 3 else 6))
            panel.columnconfigure(0, weight=1)
            ttk.Label(panel, text=label, style="Panel.TLabel", anchor="center").grid(
                row=0, column=0, sticky="ew")
            value = tk.StringVar(self, value="—")
            self.metric_values[key] = value
            ttk.Label(panel, textvariable=value, style="Metric.TLabel",
                      anchor="center").grid(row=1, column=0, sticky="ew", pady=(4, 0))

        charts = ttk.Frame(self.home)
        charts.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        charts.columnconfigure(0, weight=1, uniform="charts")
        charts.columnconfigure(1, weight=1, uniform="charts")
        charts.rowconfigure(0, weight=1)

        state_panel = self._panel(charts)
        state_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        state_panel.columnconfigure(0, weight=1)
        state_panel.rowconfigure(1, weight=1)
        ttk.Label(state_panel, text="TRẠNG THÁI CHUYẾN",
                  style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.status_canvas = tk.Canvas(state_panel, background=self.SURFACE,
                                       highlightthickness=0, width=400, height=145)
        self.status_canvas.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.status_canvas.bind("<Configure>", self.draw_status_chart)

        load_panel = self._panel(charts)
        load_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        load_panel.columnconfigure(0, weight=1)
        load_panel.rowconfigure(2, weight=1)
        ttk.Label(load_panel, text="MỨC SỬ DỤNG TẢI",
                  style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(load_panel, text="Các chuyến đang chờ",
                  style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.load_canvas = tk.Canvas(load_panel, background=self.SURFACE,
                                     highlightthickness=0, width=400, height=95)
        self.load_canvas.grid(row=2, column=0, sticky="nsew")
        self.load_canvas.bind("<Configure>", self.draw_load_chart)
        ttk.Label(load_panel, text="Tổng khối lượng đơn / Tải trọng xe",
                  style="PanelMuted.TLabel").grid(row=3, column=0, sticky="w")

        self._build_pending_table()
        navigation = ttk.Frame(self.home)
        navigation.grid(row=4, column=0, sticky="ew")
        self.navigation_buttons = {}
        for column, (key, label) in enumerate(self.SECTIONS):
            navigation.columnconfigure(column, weight=1, uniform="navigation")
            button = ttk.Button(navigation, text=label, style="Primary.TButton",
                                command=lambda section=key: self.show_section(section))
            button.grid(row=0, column=column, sticky="ew",
                        padx=(0 if column == 0 else 6, 0 if column == 3 else 6))
            self.navigation_buttons[key] = button

    def _build_pending_table(self):
        panel = self._panel(self.home)
        panel.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        ttk.Label(panel, text="CHUYẾN ĐANG CHỜ", style="PanelTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10))
        table_frame = ttk.Frame(panel)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = ("id", "date", "vehicle", "driver", "load")
        self.pending_table = DataTable(table_frame, columns=columns,
                                          show="headings", height=3, selectmode="browse")
        headings = ("Mã chuyến", "Ngày đi", "Xe", "Tài xế", "Tổng tải / Tải trọng")
        widths = (100, 140, 170, 210, 210)
        for key, heading, width in zip(columns, headings, widths):
            self.pending_table.heading(key, text=heading)
            self.pending_table.column(key, width=width, minwidth=90, anchor="center")
        self.pending_table.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table_frame, orient="vertical",
                                 command=self.pending_table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal",
                                   command=self.pending_table.xview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.pending_table.configure(yscrollcommand=vertical.set,
                                     xscrollcommand=horizontal.set)
        self.pending_note = tk.StringVar(self, value="Chưa nạp dữ liệu chuyến xe.")
        ttk.Label(panel, textvariable=self.pending_note,
                  style="PanelMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _build_workspace(self):
        from views.customer_view import CustomerView
        from views.order_view import OrderView
        from views.fleet_view import FleetView
        from views.trip_view import TripView
        self.workspace.columnconfigure(0, weight=1)
        self.workspace.rowconfigure(1, weight=1)
        self.home_button = ttk.Button(self.workspace, text="← Về trang chủ",
                                      command=self.show_home)
        self.home_button.grid(row=0, column=0, sticky="e", pady=(0, 8))
        self.notebook = ttk.Notebook(self.workspace)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.section_frames = {}
        for key, label in self.SECTIONS:
            if key == 'customers':
                frame = CustomerView(self.notebook, self.service, on_changed=self._customers_changed)
            elif key == 'orders':
                frame = OrderView(self.notebook, self.service, on_changed=self._orders_changed)
            elif key == 'fleet':
                frame = FleetView(self.notebook, self.service, on_changed=self._fleet_changed)
            else:
                frame = TripView(self.notebook, self.service, on_changed=self._trips_changed)
            self.notebook.add(frame, text=label)
            self.section_frames[key] = frame
        self.notebook.bind('<<NotebookTabChanged>>', self._tab_changed)

    def _tab_changed(self, event=None):
        if self.io_busy:
            return
        for key in ('customers', 'orders', 'fleet', 'trips'):
            view = self.section_frames[key]
            if self.notebook.select() == str(view) and not view.loaded:
                view.refresh()

    def _customers_changed(self):
        self._refresh_related('orders', 'refresh_customers')

    def _refresh_related(self, section, method='refresh'):
        """Lưu đã thành công; lỗi đọc lại không được báo thành lỗi lưu."""
        view = self.section_frames[section]
        try:
            refreshed = getattr(view, method)()
        except Exception as error:
            logging.getLogger(__name__).error('Làm mới tab %s thất bại (%s)', section, type(error).__name__)
            refreshed = False
        if refreshed is False:
            view.loaded = False
            self.status.set('Đã lưu thay đổi, nhưng một tab chưa cập nhật được. Chuyển sang tab đó hoặc nhấn Làm mới để thử lại.')

    def _orders_changed(self, event=None):
        self._refresh_related('trips')
        self.refresh_home()

    def _trips_changed(self):
        self._refresh_related('orders')
        self.refresh_home()

    def _fleet_changed(self):
        # Cập nhật Combobox và tải xe mà không xóa form tạo chuyến đang nhập.
        self._refresh_related('trips', 'refresh_resources')
        self.refresh_home()
        self.event_generate('<<FleetChanged>>', when='tail')

    def set_service(self, service):
        self.service = service
        self.section_frames['customers'].set_service(service)
        self.section_frames['orders'].set_service(service)
        self.section_frames['fleet'].set_service(service)
        self.section_frames['trips'].set_service(service)
        self.status.set('Đã kết nối MySQL • Số liệu thật từ hệ thống' if service else 'Chưa kết nối MySQL')
        self.refresh_home()

    def show_home(self):
        self.workspace.grid_remove()
        self.home.grid()
        self.refresh_home()

    def show_section(self, section):
        """Mở tab trong cùng cửa sổ; không tạo thêm Tk hoặc kết nối DB."""
        self.notebook.select(self.section_frames[section])
        self.home.grid_remove()
        self.workspace.grid()
