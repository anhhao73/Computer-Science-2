"""Khởi động Mini TMS và quản lý vòng đời kết nối MySQL."""

from tkinter import messagebox
from config import load_config, ConfigError
from database import PersistenceError
from views.main_window import MainWindow



from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
import threading
from database import Database
from services import TMSService
from models import BusinessError


class ServiceWorker:
    def __init__(self, root, config, factory=Database):
        self.root, self.config, self.factory = root, dict(config), factory
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='mini-tms-db')
        self.database = self.service = None
        self.busy = False
        self.closed = False
        self.ui_thread = threading.get_ident()
        # Keep one Tcl variable alive on the UI owner. Per-call recursive polling
        # closures could otherwise be garbage-collected on the database thread.
        self._done = tk.BooleanVar(root, False)
        self._pending = None

    def _connect(self):
        if self.database is None:
            self.database = self.factory(self.config)
        self.database.connect()
        if self.service is None:
            self.service = TMSService(self.database)

    def connect(self):
        return self.call(self._connect)

    def __getattr__(self, name):
        if name.startswith('_') or not callable(getattr(TMSService, name, None)):
            raise AttributeError(name)
        return lambda *a, **k: self.call(lambda: getattr(self.service, name)(*a, **k))

    def call(self, operation):
        if threading.get_ident() != self.ui_thread:
            raise RuntimeError('ServiceWorker must be called from the Tk thread')
        if self.closed:
            raise BusinessError('Ứng dụng đang đóng; không gửi thêm thao tác.')
        if self.busy:
            raise BusinessError('Đang xử lý yêu cầu trước. Vui lòng chờ.')
        self.busy = True
        self._done.set(False)
        self.root.set_io_busy(True)
        future = self.executor.submit(operation)
        self._pending = future
        self.root.after(1, self._poll)
        try:
            # Tcl continues to paint, resize and run timers. No Python sleep or
            # future.result wait occurs on the UI thread before completion.
            self.root.wait_variable(self._done)
            return future.result()
        finally:
            self.busy = False
            self.root.set_io_busy(False)

    def _poll(self):
        if self._pending.done():
            self._done.set(True)
        else:
            self.root.after(10, self._poll)

    def request_close(self):
        if self.busy:
            self.root.status.set('Đang xử lý dữ liệu. Vui lòng đóng cửa sổ sau khi thao tác hoàn tất.')
        else:
            self.root.destroy()

    def close(self):
        if not self.closed:
            self.closed = True
            # The same worker that created the connection closes it.
            self.executor.submit(lambda: self.database.close() if self.database else None)
            self.executor.shutdown(wait=True)


def main():
    # Crisp native controls and consistent physical geometry on scaled Windows.
    import sys
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    worker = None

    def connect():
        nonlocal worker
        try:
            if worker is None:
                worker = ServiceWorker(app, load_config())
            worker.connect()
        except (ConfigError, PersistenceError, ValueError) as error:
            app.status.set('Chưa kết nối MySQL • Chỉ xem bố cục, chưa thể lưu dữ liệu')
            messagebox.showerror('Không thể kết nối MySQL',
                                 f'{error}\nKiểm tra dịch vụ MySQL và cấu hình, rồi nhấn Kết nối lại. '
                                 'Nếu thao tác lưu vừa báo lỗi, kiểm tra lại dữ liệu trước khi gửi lại.', parent=app)
            return
        if app.service is None:
            app.set_service(worker)
        else:
            app.refresh_after_reconnect()

    app = MainWindow(on_reconnect=connect)
    app.protocol('WM_DELETE_WINDOW', lambda: worker.request_close() if worker else app.destroy())
    app.after_idle(connect)
    try:
        app.mainloop()
    finally:
        if worker is not None:
            worker.close()


if __name__ == "__main__":
    main()
