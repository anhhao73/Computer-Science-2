"""Lớp lưu trữ dữ liệu cho dự án MINI TMS của nhóm.

Người phụ trách: Duy — kết nối MySQL và viết các truy vấn có tham số.

Quy ước tích hợp:
- Cơ sở dữ liệu MySQL có tên ``mini_tms``; tên bảng và cột theo tài liệu v1.0 của nhóm.
- Mô-đun model có tên ``models.py``, cung cấp các lớp Customer, Vehicle, Driver,
  Trip và TransportOrder với các trường theo Phụ lục B.
- Mỗi nghiệp vụ hoàn chỉnh ở lớp service nên được đặt trong ``with db.transaction():``.
- Các hàm thao tác dữ liệu không tự commit. Giao dịch chỉ commit ở phạm vi ngoài cùng
  và rollback nếu có ngoại lệ thoát khỏi khối lệnh.

Cài thư viện phụ thuộc:
    python -m pip install mysql-connector-python
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any, Mapping, Optional, Sequence

try:
    import mysql.connector as _mysql_connector
    from mysql.connector import Error as _MySQLConnectorError
except ImportError:  # Cho phép nạp và kiểm tra cú pháp khi chưa cài thư viện phụ thuộc.
    _mysql_connector = None
    _MySQLConnectorError = ()  # type: ignore[assignment]


TRIP_STATUSES = ("PENDING", "IN_TRANSIT", "COMPLETED")

_ERROR_MESSAGES = {
    "DUPLICATE": "Dữ liệu bị trùng với một giá trị phải duy nhất.",
    "FOREIGN_KEY": "Dữ liệu liên quan không tồn tại hoặc đang được tham chiếu.",
    "CONNECTION": "Kết nối MySQL bị gián đoạn. Hãy nhấn Kết nối lại. Nếu vừa lưu bị lỗi, kiểm tra dữ liệu trước khi lưu lại.",
    "OTHER": "Đã xảy ra lỗi khi đọc hoặc ghi dữ liệu trong MySQL.",
}


class PersistenceError(RuntimeError):
    """Lỗi lưu trữ có mã ổn định để lớp service xử lý.

    ``message`` là thông báo ngắn, an toàn để hiển thị cho người dùng. ``original``
    giữ ngoại lệ gốc của MySQL Connector để chẩn đoán nội bộ; không hiển thị nguyên
    văn ngoại lệ này trên giao diện Tkinter.
    """

    def __init__(
        self,
        code: str,
        message: Optional[str] = None,
        *,
        original: Optional[BaseException] = None,
        errno: Optional[int] = None,
    ) -> None:
        normalized_code = code if code in _ERROR_MESSAGES else "OTHER"
        self.code = normalized_code
        self.original = original
        self.errno = errno
        super().__init__(message or _ERROR_MESSAGES[normalized_code])


class Database:
    """Quản lý kết nối MySQL duy nhất được lớp service Python sử dụng.

    Các khóa cấu hình thống nhất là ``host``, ``port``, ``database``, ``user`` và
    ``password``. Cổng mặc định là 3306; mật khẩu mặc định là chuỗi rỗng, phù hợp với
    một số môi trường phát triển cục bộ.

    Hàm khởi tạo chỉ kiểm tra cấu hình; cần gọi ``connect()`` một cách tường minh.
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        if not isinstance(config, Mapping):
            raise TypeError("config phải là mapping/dict.")

        missing = [key for key in ("host", "database", "user") if key not in config]
        if missing:
            raise ValueError("Thiếu khóa cấu hình Database: " + ", ".join(missing))

        try:
            port = int(config.get("port", 3306))
        except (TypeError, ValueError) as exc:
            raise ValueError("config['port'] phải là số nguyên.") from exc
        if not 1 <= port <= 65535:
            raise ValueError("config['port'] phải nằm trong khoảng 1–65535.")

        self._config = {
            "host": config["host"],
            "port": port,
            "database": config["database"],
            "user": config["user"],
            "password": config.get("password", ""),
        }
        self._connection: Any = None
        self._transaction_active = False

    # ---------------------------------------------------------------------
    # Vòng đời kết nối
    # ---------------------------------------------------------------------
    def connect(self) -> Any:
        """Mở và trả về kết nối; có thể gọi lại nếu kết nối hiện tại vẫn hoạt động.

        Phương thức không tự kết nối lại khi giao dịch đang diễn ra. Lỗi kết nối được
        chuyển thành PersistenceError có mã ``CONNECTION``.
        """
        if self._connection is not None:
            if self._connection_is_alive(self._connection):
                return self._connection
            if self._transaction_active:
                raise PersistenceError(
                    "CONNECTION",
                    "Kết nối đã mất trong giao dịch; không thể tự kết nối lại.",
                )
            self._discard_connection(self._connection)
            self._connection = None

        if _mysql_connector is None:
            raise PersistenceError(
                "CONNECTION",
                "Chưa cài mysql-connector-python. Chạy: python -m pip install mysql-connector-python",
            )

        connection = None
        cursor = None
        try:
            connection = _mysql_connector.connect(
                host=self._config["host"],
                port=self._config["port"],
                database=self._config["database"],
                user=self._config["user"],
                password=self._config["password"],
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
                use_unicode=True,
                autocommit=False,
                connection_timeout=5,
                read_timeout=10,
                write_timeout=10,
            )
            # Thiết lập rõ ràng thuộc tính này, đồng thời truyền khi tạo kết nối.
            connection.autocommit = False
            cursor = connection.cursor()
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
            self._connection = connection
            return connection
        except Exception as exc:
            if connection is not None:
                self._discard_connection(connection)
            if self._is_connector_error(exc):
                raise self._translate_connector_error(exc) from exc
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    # Không để lỗi đóng cursor che mất lỗi kết nối hoặc thiết lập ban đầu.
                    pass

    def close(self) -> None:
        """Hoàn tác công việc chưa hoàn tất và giải phóng kết nối cùng các khóa."""
        connection = self._connection
        if connection is None:
            self._transaction_active = False
            return

        # Rollback sau commit là an toàn và cần thiết nếu vẫn còn thay đổi chưa hoàn tất.
        try:
            if self._connection_is_alive(connection):
                connection.rollback()
        except Exception:
            # Nếu kết nối tới máy chủ đã hỏng, có thể không thực hiện được rollback.
            # Dù vậy, vẫn thử đóng kết nối cục bộ ở phía dưới.
            pass
        finally:
            self._transaction_active = False
            self._connection = None
            try:
                connection.close()
            except Exception:
                pass

    @staticmethod
    def _connection_is_alive(connection: Any) -> bool:
        try:
            return bool(connection.is_connected())
        except Exception:
            return False

    @staticmethod
    def _discard_connection(connection: Any) -> None:
        try:
            connection.close()
        except Exception:
            pass

    def _require_connection(self) -> Any:
        if self._connection is None:
            raise PersistenceError("CONNECTION", "Hãy gọi Database.connect() trước khi truy vấn.")
        if not self._connection_is_alive(self._connection):
            raise PersistenceError("CONNECTION")
        return self._connection

    @contextmanager
    def transaction(self, *, snapshot: bool = False) -> Generator["Database", None, None]:
        """Thực hiện trọn vẹn một nghiệp vụ: commit khi thành công, rollback khi có lỗi.

        Không hỗ trợ giao dịch lồng nhau. Mọi hàm dữ liệu mà service sử dụng phải dùng
        chung kết nối này và không được tự commit.
        """
        connection = self._require_connection()
        if self._transaction_active:
            raise PersistenceError(
                "OTHER",
                "Không hỗ trợ transaction lồng nhau; hãy dùng một transaction ngoài cùng.",
            )

        self._transaction_active = True
        try:
            if snapshot:
                connection.start_transaction(isolation_level="REPEATABLE READ",
                                             consistent_snapshot=True, readonly=True)
            else:
                connection.start_transaction(isolation_level="READ COMMITTED")
            yield self
            if self._connection is not connection:
                raise PersistenceError(
                    "CONNECTION",
                    "Kết nối đã bị đóng hoặc thay đổi trước khi transaction kết thúc.",
                )
            connection.commit()
        except BaseException as exc:
            try:
                connection.rollback()
            except Exception:
                pass
            if self._is_connector_error(exc):
                raise self._translate_connector_error(exc) from exc
            raise
        finally:
            self._transaction_active = False

    # ---------------------------------------------------------------------
    # Quản lý cursor và xử lý lỗi
    # ---------------------------------------------------------------------
    @contextmanager
    def _cursor(self) -> Generator[Any, None, None]:
        connection = self._require_connection()
        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)
            yield cursor
        except Exception as exc:
            if self._is_connector_error(exc):
                raise self._translate_connector_error(exc) from exc
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    # Lỗi truy vấn ban đầu (nếu có) hữu ích hơn lỗi phát sinh khi đóng cursor.
                    pass

    @staticmethod
    def _is_connector_error(exc: BaseException) -> bool:
        if _MySQLConnectorError and isinstance(exc, _MySQLConnectorError):
            return True
        # Hỗ trợ cả lỗi connector trong trường hợp thư viện phụ thuộc
        # chưa có lúc nạp mô-đun nhưng được ứng dụng nạp sau đó.
        module_name = exc.__class__.__module__
        return module_name.startswith("mysql.connector") and hasattr(exc, "errno")

    @staticmethod
    def _translate_connector_error(exc: BaseException) -> PersistenceError:
        errno_value = getattr(exc, "errno", None)
        try:
            errno = int(errno_value) if errno_value is not None else None
        except (TypeError, ValueError):
            errno = None

        if errno == 1062:
            code = "DUPLICATE"
        elif errno in (1451, 1452):
            code = "FOREIGN_KEY"
        elif errno in (1042, 1045, 2002, 2003, 2005, 2006, 2013, 2055):
            code = "CONNECTION"
        elif exc.__class__.__name__ in ("InterfaceError", "ReadTimeoutError", "WriteTimeoutError"):
            code = "CONNECTION"
        else:
            code = "OTHER"

        return PersistenceError(code, original=exc, errno=errno)

    @staticmethod
    def _decimal_or_zero(value: Any) -> Decimal:
        if value is None:
            return Decimal("0.00")
        if isinstance(value, Decimal):
            return value
        # Dùng str() để tránh đưa sai số biểu diễn số thực nhị phân vào Decimal.
        return Decimal(str(value))

    @staticmethod
    def _model(model_name: str, **fields: Any) -> Any:
        """Khởi tạo model theo quy ước ``models.py`` đã thống nhất trong nhóm.

        Việc import được trì hoãn để có thể đọc/kiểm thử tệp này trước khi ghép mô-đun
        model của Hào. Khi chạy ứng dụng thực tế, các lớp model vẫn phải tồn tại.
        """
        try:
            models_module = import_module("models")
            model_class = getattr(models_module, model_name)
        except (ImportError, AttributeError) as exc:
            raise PersistenceError(
                "OTHER",
                f"Không tìm thấy {model_name} trong models.py; hãy thống nhất tên model với Hào.",
                original=exc,
            ) from exc
        try:
            return model_class(**fields)
        except Exception as exc:
            raise PersistenceError(
                "OTHER",
                f"Không thể ánh xạ dữ liệu MySQL sang {model_name}; kiểm tra chữ ký model với Hào.",
                original=exc,
            ) from exc

    @classmethod
    def _customer_from_row(cls, row: Mapping[str, Any]) -> Any:
        return cls._model(
            "Customer",
            id=int(row["id"]),
            name=row["name"],
            phone=row["phone"],
            address=row["address"],
        )

    @classmethod
    def _vehicle_from_row(cls, row: Mapping[str, Any]) -> Any:
        return cls._model(
            "Vehicle",
            id=int(row["id"]),
            plate_number=row["plate_number"],
            capacity_kg=cls._decimal_or_zero(row["capacity_kg"]),
        )

    @classmethod
    def _driver_from_row(cls, row: Mapping[str, Any]) -> Any:
        return cls._model(
            "Driver",
            id=int(row["id"]),
            name=row["name"],
            phone=row["phone"],
            license_number=row["license_number"],
        )

    @classmethod
    def _order_from_row(cls, row: Mapping[str, Any]) -> Any:
        trip_id = row["trip_id"]
        return cls._model(
            "TransportOrder",
            id=int(row["id"]),
            customer_id=int(row["customer_id"]),
            trip_id=None if trip_id is None else int(trip_id),
            pickup_address=row["pickup_address"],
            delivery_address=row["delivery_address"],
            weight_kg=cls._decimal_or_zero(row["weight_kg"]),
            freight_amount=cls._decimal_or_zero(row["freight_amount"]),
        )

    @classmethod
    def _trip_from_row(cls, row: Mapping[str, Any]) -> Any:
        # Theo quy ước, list_trips() trả về chuyến xe mà chưa nạp danh sách đơn hàng.
        return cls._model(
            "Trip",
            id=int(row["id"]),
            vehicle_id=int(row["vehicle_id"]),
            driver_id=int(row["driver_id"]),
            departure_date=row["departure_date"],
            status=row["status"],
            orders=[],
        )

    # ---------------------------------------------------------------------
    # Khách hàng
    # ---------------------------------------------------------------------
    def get_customer(self, customer_id: int) -> Any | None:
        sql = """SELECT id, name, phone, address
                 FROM customers WHERE id = %s"""
        with self._cursor() as cursor:
            cursor.execute(sql, (customer_id,))
            row = cursor.fetchone()
        return None if row is None else self._customer_from_row(row)

    def list_customers(self, keyword: str = "") -> list[Any]:
        keyword = keyword.strip()
        if keyword:
            sql = """SELECT id, name, phone, address
                     FROM customers
                     WHERE name LIKE %s OR phone LIKE %s
                     ORDER BY id"""
            pattern = f"%{keyword}%"
            params: Sequence[Any] = (pattern, pattern)
        else:
            sql = """SELECT id, name, phone, address
                     FROM customers ORDER BY id"""
            params = ()
        with self._cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return [self._customer_from_row(row) for row in rows]

    def insert_customer(self, name: str, phone: str, address: str) -> int:
        sql = "INSERT INTO customers (name, phone, address) VALUES (%s, %s, %s)"
        with self._cursor() as cursor:
            cursor.execute(sql, (name, phone, address))
            return int(cursor.lastrowid)

    def update_customer(self, customer_id: int, name: str, phone: str, address: str) -> None:
        sql = """UPDATE customers
                 SET name = %s, phone = %s, address = %s
                 WHERE id = %s"""
        with self._cursor() as cursor:
            cursor.execute(sql, (name, phone, address, customer_id))

    # ---------------------------------------------------------------------
    # Xe vận chuyển
    # ---------------------------------------------------------------------
    def get_vehicle(self, vehicle_id: int, for_update: bool = False) -> Any | None:
        suffix = self._for_update_suffix(for_update)
        sql = """SELECT id, plate_number, capacity_kg
                 FROM vehicles WHERE id = %s""" + suffix
        with self._cursor() as cursor:
            cursor.execute(sql, (vehicle_id,))
            row = cursor.fetchone()
        return None if row is None else self._vehicle_from_row(row)

    def list_vehicles(self) -> list[Any]:
        sql = "SELECT id, plate_number, capacity_kg FROM vehicles ORDER BY id"
        with self._cursor() as cursor:
            cursor.execute(sql, ())
            rows = cursor.fetchall()
        return [self._vehicle_from_row(row) for row in rows]

    def insert_vehicle(self, plate_number: str, capacity_kg: Decimal) -> int:
        sql = "INSERT INTO vehicles (plate_number, capacity_kg) VALUES (%s, %s)"
        with self._cursor() as cursor:
            cursor.execute(sql, (plate_number, capacity_kg))
            return int(cursor.lastrowid)

    def update_vehicle(self, vehicle_id: int, plate_number: str, capacity_kg: Decimal) -> None:
        sql = """UPDATE vehicles
                 SET plate_number = %s, capacity_kg = %s
                 WHERE id = %s"""
        with self._cursor() as cursor:
            cursor.execute(sql, (plate_number, capacity_kg, vehicle_id))

    # ---------------------------------------------------------------------
    # Tài xế
    # ---------------------------------------------------------------------
    def get_driver(self, driver_id: int, for_update: bool = False) -> Any | None:
        suffix = self._for_update_suffix(for_update)
        sql = """SELECT id, name, phone, license_number
                 FROM drivers WHERE id = %s""" + suffix
        with self._cursor() as cursor:
            cursor.execute(sql, (driver_id,))
            row = cursor.fetchone()
        return None if row is None else self._driver_from_row(row)

    def list_drivers(self) -> list[Any]:
        sql = "SELECT id, name, phone, license_number FROM drivers ORDER BY id"
        with self._cursor() as cursor:
            cursor.execute(sql, ())
            rows = cursor.fetchall()
        return [self._driver_from_row(row) for row in rows]

    def insert_driver(self, name: str, phone: str, license_number: str) -> int:
        sql = "INSERT INTO drivers (name, phone, license_number) VALUES (%s, %s, %s)"
        with self._cursor() as cursor:
            cursor.execute(sql, (name, phone, license_number))
            return int(cursor.lastrowid)

    def update_driver(self, driver_id: int, name: str, phone: str, license_number: str) -> None:
        sql = """UPDATE drivers
                 SET name = %s, phone = %s, license_number = %s
                 WHERE id = %s"""
        with self._cursor() as cursor:
            cursor.execute(sql, (name, phone, license_number, driver_id))

    # ---------------------------------------------------------------------
    # Đơn vận chuyển
    # ---------------------------------------------------------------------
    def get_order(self, order_id: int, for_update: bool = False) -> Any | None:
        suffix = self._for_update_suffix(for_update)
        sql = """SELECT id, customer_id, trip_id, pickup_address, delivery_address,
                        weight_kg, freight_amount
                 FROM orders WHERE id = %s""" + suffix
        with self._cursor() as cursor:
            cursor.execute(sql, (order_id,))
            row = cursor.fetchone()
        return None if row is None else self._order_from_row(row)

    def list_orders(self, unassigned_only: bool = False) -> list[Any]:
        sql = """SELECT id, customer_id, trip_id, pickup_address, delivery_address,
                        weight_kg, freight_amount
                 FROM orders"""
        if unassigned_only:
            sql += " WHERE trip_id IS NULL"
        sql += " ORDER BY id"
        with self._cursor() as cursor:
            cursor.execute(sql, ())
            rows = cursor.fetchall()
        return [self._order_from_row(row) for row in rows]

    def list_orders_by_trip(self, trip_id: int) -> list[Any]:
        sql = """SELECT id, customer_id, trip_id, pickup_address, delivery_address,
                        weight_kg, freight_amount
                 FROM orders WHERE trip_id = %s ORDER BY id"""
        with self._cursor() as cursor:
            cursor.execute(sql, (trip_id,))
            rows = cursor.fetchall()
        return [self._order_from_row(row) for row in rows]

    def insert_order(
        self,
        customer_id: int,
        pickup_address: str,
        delivery_address: str,
        weight_kg: Decimal,
        freight_amount: Decimal,
    ) -> int:
        # Đơn mới mặc định chưa được phân công: trip_id = NULL.
        sql = """INSERT INTO orders
                 (customer_id, trip_id, pickup_address, delivery_address, weight_kg, freight_amount)
                 VALUES (%s, NULL, %s, %s, %s, %s)"""
        with self._cursor() as cursor:
            cursor.execute(
                sql,
                (customer_id, pickup_address, delivery_address, weight_kg, freight_amount),
            )
            return int(cursor.lastrowid)

    def update_order(
        self,
        order_id: int,
        customer_id: int,
        pickup_address: str,
        delivery_address: str,
        weight_kg: Decimal,
        freight_amount: Decimal,
    ) -> None:
        # Không nhận trip_id tại đây; service phải từ chối sửa đơn đã được phân công.
        sql = """UPDATE orders
                 SET customer_id = %s,
                     pickup_address = %s,
                     delivery_address = %s,
                     weight_kg = %s,
                     freight_amount = %s
                 WHERE id = %s"""
        with self._cursor() as cursor:
            cursor.execute(
                sql,
                (customer_id, pickup_address, delivery_address, weight_kg, freight_amount, order_id),
            )

    def set_order_trip(self, order_id: int, trip_id: Optional[int]) -> None:
        sql = "UPDATE orders SET trip_id = %s WHERE id = %s"
        with self._cursor() as cursor:
            cursor.execute(sql, (trip_id, order_id))

    # ---------------------------------------------------------------------
    # Chuyến xe
    # ---------------------------------------------------------------------
    def get_trip(self, trip_id: int, for_update: bool = False) -> Any | None:
        suffix = self._for_update_suffix(for_update)
        sql = """SELECT id, vehicle_id, driver_id, departure_date, status
                 FROM trips WHERE id = %s""" + suffix
        with self._cursor() as cursor:
            cursor.execute(sql, (trip_id,))
            row = cursor.fetchone()
        return None if row is None else self._trip_from_row(row)

    def list_trips(self, status: Optional[str] = None) -> list[Any]:
        if status is not None and status not in TRIP_STATUSES:
            raise ValueError(f"status phải là một trong: {', '.join(TRIP_STATUSES)}")

        sql = "SELECT id, vehicle_id, driver_id, departure_date, status FROM trips"
        params: Sequence[Any] = ()
        if status is not None:
            sql += " WHERE status = %s"
            params = (status,)
        sql += " ORDER BY departure_date, id"
        with self._cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        # Mỗi Trip có danh sách riêng; nạp chi tiết bằng list_orders_by_trip().
        return [self._trip_from_row(row) for row in rows]

    def insert_trip(self, vehicle_id: int, driver_id: int, departure_date: date) -> int:
        # Để MySQL áp dụng giá trị DEFAULT đã thống nhất là 'PENDING'.
        sql = "INSERT INTO trips (vehicle_id, driver_id, departure_date) VALUES (%s, %s, %s)"
        with self._cursor() as cursor:
            cursor.execute(sql, (vehicle_id, driver_id, departure_date))
            return int(cursor.lastrowid)

    def update_trip_status(self, trip_id: int, status: str) -> None:
        if status not in TRIP_STATUSES:
            raise ValueError(f"status phải là một trong: {', '.join(TRIP_STATUSES)}")
        sql = "UPDATE trips SET status = %s WHERE id = %s"
        with self._cursor() as cursor:
            cursor.execute(sql, (status, trip_id))

    # ---------------------------------------------------------------------
    # Truy vấn hỗ trợ nghiệp vụ cho TMSService
    # ---------------------------------------------------------------------
    def get_trip_total_weight(self, trip_id: int) -> Decimal:
        sql = """SELECT COALESCE(SUM(weight_kg), 0.00) AS total_weight
                 FROM orders WHERE trip_id = %s"""
        with self._cursor() as cursor:
            cursor.execute(sql, (trip_id,))
            row = cursor.fetchone()
        if row is None:
            return Decimal("0.00")
        return self._decimal_or_zero(row.get("total_weight"))

    def vehicle_has_trip(self, vehicle_id: int, departure_date: date) -> bool:
        sql = """SELECT 1 AS found FROM trips
                 WHERE vehicle_id = %s AND departure_date = %s LIMIT 1"""
        with self._cursor() as cursor:
            cursor.execute(sql, (vehicle_id, departure_date))
            row = cursor.fetchone()
        return row is not None

    def driver_has_trip(self, driver_id: int, departure_date: date) -> bool:
        sql = """SELECT 1 AS found FROM trips
                 WHERE driver_id = %s AND departure_date = %s LIMIT 1"""
        with self._cursor() as cursor:
            cursor.execute(sql, (driver_id, departure_date))
            row = cursor.fetchone()
        return row is not None

    def get_max_active_trip_weight(self, vehicle_id: int) -> Decimal:
        """Trả về tổng khối lượng hàng lớn nhất trong các chuyến đang hoạt động của xe.

        Theo quy ước của nhóm, chuyến đang hoạt động có trạng thái PENDING hoặc
        IN_TRANSIT. Nếu xe không có chuyến đang hoạt động, trả về Decimal('0.00').
        """
        sql = """SELECT COALESCE(MAX(active_trip.total_weight), 0.00) AS max_weight
                 FROM (
                     SELECT t.id, COALESCE(SUM(o.weight_kg), 0.00) AS total_weight
                     FROM trips AS t
                     LEFT JOIN orders AS o ON o.trip_id = t.id
                     WHERE t.vehicle_id = %s
                       AND t.status IN (%s, %s)
                     GROUP BY t.id
                 ) AS active_trip"""
        with self._cursor() as cursor:
            cursor.execute(sql, (vehicle_id, "PENDING", "IN_TRANSIT"))
            row = cursor.fetchone()
        if row is None:
            return Decimal("0.00")
        return self._decimal_or_zero(row.get("max_weight"))

    # ---------------------------------------------------------------------
    # Hàm hỗ trợ khóa bản ghi
    # ---------------------------------------------------------------------
    def _for_update_suffix(self, for_update: bool) -> str:
        if not isinstance(for_update, bool):
            raise TypeError("for_update phải là bool.")
        if not for_update:
            return ""
        if not self._transaction_active:
            raise PersistenceError(
                "OTHER",
                "SELECT ... FOR UPDATE chỉ được dùng bên trong db.transaction().",
            )
        # Chọn đoạn SQL cố định bằng biến boolean nội bộ, không lấy từ văn bản người dùng.
        return " FOR UPDATE"
