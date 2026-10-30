"""Cấu hình MySQL cho Mini TMS.

Mặc định dành cho máy Vinh; biến môi trường được ưu tiên nếu được thiết lập.
main.py gọi load_config() rồi truyền kết quả vào Database(config).
Trước khi chia sẻ mã nguồn, thay mật khẩu cá nhân mặc định bằng cấu hình riêng.
"""

import os


class ConfigError(ValueError):
    """Cấu hình kết nối không hợp lệ."""


def load_config() -> dict:
    """Đọc cấu hình tại thời điểm gọi, không tự mở kết nối MySQL."""
    host = os.environ.get("DB_HOST", "localhost").strip()
    port_text = os.environ.get("DB_PORT", "3306").strip()
    database = os.environ.get("DB_NAME", "mini_tms").strip()
    user = os.environ.get("DB_USER", "root").strip()
    password = os.environ.get("DB_PASSWORD", "mysql")

    for variable, value in (
        ("DB_HOST", host),
        ("DB_NAME", database),
        ("DB_USER", user),
    ):
        if not value:
            raise ConfigError(f"{variable} không được để trống.")

    if not port_text.isascii() or not port_text.isdecimal():
        raise ConfigError("DB_PORT phải là số nguyên từ 1 đến 65535.")
    try:
        port = int(port_text)
    except ValueError:
        raise ConfigError("DB_PORT phải là số nguyên từ 1 đến 65535.") from None
    if not 1 <= port <= 65535:
        raise ConfigError("DB_PORT phải là số nguyên từ 1 đến 65535.")

    # Giữ nguyên mật khẩu, kể cả khoảng trắng hoặc giá trị rỗng được khai báo.
    return {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
    }
