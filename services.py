from decimal import Decimal
from datetime import date
from typing import List, Optional
from models import Customer, Vehicle, Driver, TransportOrder, Trip, BusinessError, valid_id
from database import PersistenceError
import inspect
import logging
import functools

def handle_business_exceptions(func):
    """Decorator để tự động bắt lỗi ValueError từ model/logic và lỗi DB, bọc thành BusinessError."""
    signature = inspect.signature(func)
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            for name, value in signature.bind(*args, **kwargs).arguments.items():
                if name.endswith('_id'):
                    valid_id(value)
            return func(*args, **kwargs)
        except BusinessError:
            raise
        except ValueError as e:
            raise BusinessError(str(e)) from e
        except PersistenceError as e:
            raise BusinessError(str(e)) from e
        except Exception as e:
            # Không đưa dữ liệu đầu vào hoặc thông tin kết nối vào log/thông báo.
            logging.getLogger(__name__).error("%s thất bại (%s)", func.__name__, type(e).__name__)
            raise BusinessError("Lỗi hệ thống khi xử lý yêu cầu. Vui lòng thử lại.") from e
    return wrapper

class TMSService:
    def __init__(self, db):
        self.db = db

    @handle_business_exceptions
    def get_dashboard_data(self):
        """Read related tables from a single read-only consistent snapshot."""
        with self.db.transaction(snapshot=True):
            trips = self.db.list_trips()
            orders = self.db.list_orders()
            vehicles = {v.id: v for v in self.db.list_vehicles()}
            drivers = {d.id: d for d in self.db.list_drivers()}
            counts = {code: sum(t.status == code for t in trips)
                      for code in ('PENDING', 'IN_TRANSIT', 'COMPLETED')}
            weights = {}
            for order in orders:
                if order.trip_id is not None:
                    weights[order.trip_id] = weights.get(order.trip_id, Decimal('0')) + order.weight_kg
            rows = []
            for trip in sorted(trips, key=lambda t: (t.departure_date, t.id)):
                if trip.status == 'PENDING':
                    vehicle, driver = vehicles[trip.vehicle_id], drivers[trip.driver_id]
                    rows.append((trip.id, trip.departure_date.isoformat(), vehicle.plate_number,
                                 driver.name, weights.get(trip.id, Decimal('0')), vehicle.capacity_kg))
            return dict(counts=counts, rows=rows, unassigned=sum(o.trip_id is None for o in orders))

    # ================= KHÁCH HÀNG =================
    @handle_business_exceptions
    def list_customers(self, keyword: str = "") -> List[Customer]:
        with self.db.transaction():
            return self.db.list_customers(keyword.strip())

    @handle_business_exceptions
    def create_customer(self, name: str, phone: str, address: str) -> int:
        with self.db.transaction():
            item = Customer(0, name, phone, address)
            return self.db.insert_customer(item.name, item.phone, item.address)

    @handle_business_exceptions
    def update_customer(self, customer_id: int, name: str, phone: str, address: str) -> None:
        with self.db.transaction():
            item = Customer(customer_id, name, phone, address)
            if self.db.get_customer(customer_id) is None:
                raise ValueError("Khách hàng không tồn tại.")
            self.db.update_customer(customer_id, item.name, item.phone, item.address)

    # ================= XE VÀ TÀI XẾ =================
    @handle_business_exceptions
    def list_vehicles(self) -> List[Vehicle]:
        with self.db.transaction():
            return self.db.list_vehicles()

    @handle_business_exceptions
    def create_vehicle(self, plate_number: str, capacity_kg: Decimal) -> int:
        with self.db.transaction():
            item = Vehicle(0, plate_number, capacity_kg)
            return self.db.insert_vehicle(item.plate_number, item.capacity_kg)

    @handle_business_exceptions
    def update_vehicle(self, vehicle_id: int, plate_number: str, capacity_kg: Decimal) -> None:
        with self.db.transaction():
            item = Vehicle(vehicle_id, plate_number, capacity_kg)
            vehicle = self.db.get_vehicle(vehicle_id, for_update=True)
            if not vehicle:
                raise ValueError("Xe không tồn tại.")
            # Kiểm tra tải trọng mới không được nhỏ hơn tổng hàng các chuyến đang chạy
            max_active_weight = self.db.get_max_active_trip_weight(vehicle_id)
            if item.capacity_kg < max_active_weight:
                raise ValueError(f"Tải trọng mới ({capacity_kg}kg) nhỏ hơn tổng hàng đang chở ({max_active_weight}kg).")
            self.db.update_vehicle(vehicle_id, item.plate_number, item.capacity_kg)

    @handle_business_exceptions
    def list_drivers(self) -> List[Driver]:
        with self.db.transaction():
            return self.db.list_drivers()

    @handle_business_exceptions
    def create_driver(self, name: str, phone: str, license_number: str) -> int:
        with self.db.transaction():
            item = Driver(0, name, phone, license_number)
            return self.db.insert_driver(item.name, item.phone, item.license_number)

    @handle_business_exceptions
    def update_driver(self, driver_id: int, name: str, phone: str, license_number: str) -> None:
        with self.db.transaction():
            item = Driver(driver_id, name, phone, license_number)
            if self.db.get_driver(driver_id) is None:
                raise ValueError("Tài xế không tồn tại.")
            self.db.update_driver(driver_id, item.name, item.phone, item.license_number)

    # ================= ĐƠN VẬN CHUYỂN =================
    @handle_business_exceptions
    def list_orders(self, unassigned_only: bool = False) -> List[TransportOrder]:
        with self.db.transaction():
            return self.db.list_orders(unassigned_only)

    @handle_business_exceptions
    def create_order(self, customer_id: int, pickup_address: str, delivery_address: str, weight_kg: Decimal, freight_amount: Decimal) -> int:
        with self.db.transaction():
            item = TransportOrder(0, customer_id, pickup_address, delivery_address, weight_kg, freight_amount)
            if self.db.get_customer(customer_id) is None:
                raise ValueError("Khách hàng không tồn tại.")
            return self.db.insert_order(customer_id, item.pickup_address, item.delivery_address, item.weight_kg, item.freight_amount)

    @handle_business_exceptions
    def update_order(self, order_id: int, customer_id: int, pickup_address: str, delivery_address: str, weight_kg: Decimal, freight_amount: Decimal) -> None:
        with self.db.transaction():
            item = TransportOrder(order_id, customer_id, pickup_address, delivery_address, weight_kg, freight_amount)
            order = self.db.get_order(order_id, for_update=True)
            if not order:
                raise ValueError("Đơn hàng không tồn tại.")
            if order.trip_id is not None:
                raise ValueError("Chỉ được sửa đơn hàng chưa phân công chuyến.")
            if self.db.get_customer(customer_id) is None:
                raise ValueError("Khách hàng không tồn tại.")
            self.db.update_order(order_id, customer_id, item.pickup_address, item.delivery_address, item.weight_kg, item.freight_amount)

    # ================= CHUYẾN XE =================
    @handle_business_exceptions
    def list_trips(self, status: Optional[str] = None) -> List[Trip]:
        with self.db.transaction():
            return self.db.list_trips(status)

    @handle_business_exceptions
    def get_trip_details(self, trip_id: int) -> Trip:
        with self.db.transaction():
            trip = self.db.get_trip(trip_id)
            if not trip:
                raise ValueError(f"Chuyến xe {trip_id} không tồn tại.")
            trip.orders = self.db.list_orders_by_trip(trip_id)
            return trip

    @handle_business_exceptions
    def create_trip(self, vehicle_id: int, driver_id: int, departure_date: date) -> int:
        with self.db.transaction():
            Trip(0, vehicle_id, driver_id, departure_date)
            if self.db.get_vehicle(vehicle_id) is None:
                raise ValueError("Xe không tồn tại.")
            if self.db.get_driver(driver_id) is None:
                raise ValueError("Tài xế không tồn tại.")
            # Check trùng lịch xe và tài xế trong ngày
            if self.db.vehicle_has_trip(vehicle_id, departure_date):
                raise ValueError(f"Xe đã có lịch chạy vào ngày {departure_date}.")
            if self.db.driver_has_trip(driver_id, departure_date):
                raise ValueError(f"Tài xế đã có lịch chạy vào ngày {departure_date}.")
            return self.db.insert_trip(vehicle_id, driver_id, departure_date)

    @handle_business_exceptions
    def assign_order_to_trip(self, order_id: int, trip_id: int) -> None:
        with self.db.transaction():
            trip = self.db.get_trip(trip_id, for_update=True)
            if not trip or trip.status != 'PENDING':
                raise ValueError(f"Chuyến {trip_id} không tồn tại hoặc không ở trạng thái PENDING.")
            
            order = self.db.get_order(order_id, for_update=True)
            if not order or order.trip_id is not None:
                raise ValueError(f"Đơn {order_id} không tồn tại hoặc đã được gán vào chuyến khác.")

            vehicle = self.db.get_vehicle(trip.vehicle_id, for_update=True)
            if vehicle is None:
                raise ValueError("Xe của chuyến không tồn tại.")
            current_total = self.db.get_trip_total_weight(trip_id)
            
            if not vehicle.can_carry(current_total + order.weight_kg):
                raise ValueError(f"Tổng hàng ({current_total + order.weight_kg}kg) vượt tải trọng xe ({vehicle.capacity_kg}kg).")

            self.db.set_order_trip(order_id, trip_id)

    @handle_business_exceptions
    def remove_order_from_trip(self, order_id: int, trip_id: int) -> None:
        with self.db.transaction():
            trip = self.db.get_trip(trip_id, for_update=True)
            if not trip or trip.status != 'PENDING':
                raise ValueError("Chỉ có thể loại bỏ đơn khỏi chuyến xe đang ở trạng thái chờ (PENDING).")
            
            order = self.db.get_order(order_id, for_update=True)
            if not order or order.trip_id != trip_id:
                raise ValueError("Đơn hàng không thuộc chuyến xe này.")

            self.db.set_order_trip(order_id, None)

    @handle_business_exceptions
    def start_trip(self, trip_id: int) -> None:
        with self.db.transaction():
            # Khóa chuyến trước khi nạp đơn để thêm/bỏ đơn không chen vào lúc khởi hành.
            # Không gọi self.get_trip_details(): hàm đó mở transaction riêng.
            trip = self.db.get_trip(trip_id, for_update=True)
            if not trip:
                raise ValueError("Chuyến xe không tồn tại.")
            trip.orders = self.db.list_orders_by_trip(trip_id)
            
            # Khóa dữ liệu xe để check tải trọng an toàn
            vehicle = self.db.get_vehicle(trip.vehicle_id, for_update=True)
            if not vehicle:
                raise ValueError("Xe của chuyến không tồn tại.")
            if not vehicle.can_carry(trip.total_weight()):
                raise ValueError("Tải trọng hiện tại vượt mức cho phép, không thể khởi hành.")

            trip.start()
            self.db.update_trip_status(trip_id, trip.status)

    @handle_business_exceptions
    def complete_trip(self, trip_id: int) -> None:
        with self.db.transaction():
            trip = self.db.get_trip(trip_id, for_update=True)
            if not trip:
                raise ValueError("Chuyến xe không tồn tại.")
            
            trip.complete()
            self.db.update_trip_status(trip_id, trip.status)
