from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import date
from typing import List, Optional


def required_text(value, label, limit):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} không được rỗng.")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{label} không được quá {limit} ký tự.")
    return value


def valid_decimal(value, label, maximum, allow_zero=False):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{label} phải là Decimal hữu hạn.")
    if value < 0 or (not allow_zero and value == 0) or value > Decimal(maximum):
        raise ValueError(f"{label} phải {'không âm' if allow_zero else 'lớn hơn 0'} và không quá {maximum}.")
    try:
        rounded = value.quantize(Decimal('0.01'))
    except InvalidOperation:
        raise ValueError(f"{label} không hợp lệ.") from None
    if value != rounded:
        raise ValueError(f"{label} chỉ được có tối đa hai chữ số thập phân có nghĩa.")
    return rounded


def valid_id(value):
    if type(value) is not int or value <= 0:
        raise ValueError("ID phải là số nguyên dương.")
    return value

class BusinessError(Exception):
    """Lỗi nghiệp vụ dùng để ném về cho Tầng Giao diện (Vinh) hiển thị."""
    pass

@dataclass
class Customer:
    id: int
    name: str
    phone: str
    address: str

    def __post_init__(self):
        self.name = required_text(self.name, "Tên khách hàng", 100)
        self.phone = required_text(self.phone, "Điện thoại", 25)
        self.address = required_text(self.address, "Địa chỉ", 255)

@dataclass
class Vehicle:
    id: int
    plate_number: str
    capacity_kg: Decimal

    def __post_init__(self):
        self.plate_number = required_text(self.plate_number, "Biển số", 20).upper()
        self.plate_number = required_text(self.plate_number, "Biển số", 20)
        self.capacity_kg = valid_decimal(self.capacity_kg, "Tải trọng xe", '99999999.99')

    def can_carry(self, total_weight: Decimal) -> bool:
        """Kiểm tra xe có thể chở được tổng khối lượng này không."""
        return total_weight <= self.capacity_kg

@dataclass
class Driver:
    id: int
    name: str
    phone: str
    license_number: str

    def __post_init__(self):
        self.name = required_text(self.name, "Tên tài xế", 100)
        self.phone = required_text(self.phone, "Điện thoại", 25)
        self.license_number = required_text(self.license_number, "Số bằng lái", 30)

@dataclass
class TransportOrder:
    id: int
    customer_id: int
    pickup_address: str
    delivery_address: str
    weight_kg: Decimal
    freight_amount: Decimal
    trip_id: Optional[int] = None

    def __post_init__(self):
        valid_id(self.customer_id)
        if self.trip_id is not None:
            valid_id(self.trip_id)
        self.pickup_address = required_text(self.pickup_address, "Địa chỉ lấy", 255)
        self.delivery_address = required_text(self.delivery_address, "Địa chỉ giao", 255)
        self.weight_kg = valid_decimal(self.weight_kg, "Khối lượng", '99999999.99')
        self.freight_amount = valid_decimal(self.freight_amount, "Giá cước", '9999999999.99', True)

@dataclass
class Trip:
    id: int
    vehicle_id: int
    driver_id: int
    departure_date: date
    status: str = 'PENDING'
    # Dùng default_factory để tránh tham chiếu chung 1 list cho mọi đối tượng Trip
    orders: List[TransportOrder] = field(default_factory=list)

    def __post_init__(self):
        valid_id(self.vehicle_id)
        valid_id(self.driver_id)
        if type(self.departure_date) is not date:
            raise ValueError("Ngày khởi hành phải có kiểu date.")
        if self.status not in ('PENDING', 'IN_TRANSIT', 'COMPLETED'):
            raise ValueError("Trạng thái chuyến không hợp lệ.")

    def total_weight(self) -> Decimal:
        """Tính tổng tải trọng của các đơn hàng trong chuyến."""
        return sum((order.weight_kg for order in self.orders), Decimal('0.00'))

    def start(self):
        """Khởi hành chuyến xe: Đóng gói chuyển trạng thái."""
        if self.status != 'PENDING':
            raise ValueError("Chỉ chuyến PENDING mới có thể khởi hành.")
        if not self.orders:
            raise ValueError("Chuyến xe rỗng, cần ít nhất 1 đơn hàng để khởi hành.")
        self.status = 'IN_TRANSIT'

    def complete(self):
        """Hoàn thành chuyến xe: Đóng gói chuyển trạng thái."""
        if self.status != 'IN_TRANSIT':
            raise ValueError("Chỉ chuyến IN_TRANSIT mới có thể hoàn thành.")
        self.status = 'COMPLETED'
