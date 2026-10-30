-- Tạo database với utf8mb4
CREATE DATABASE IF NOT EXISTS mini_tms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mini_tms;

-- 1. Bảng customers
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(25) NOT NULL,
    address VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

-- 2. Bảng vehicles
CREATE TABLE vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    capacity_kg DECIMAL(10,2) NOT NULL,
    CONSTRAINT uq_vehicle_plate UNIQUE (plate_number),
    CONSTRAINT chk_vehicle_capacity CHECK (capacity_kg > 0)
) ENGINE=InnoDB;

-- 3. Bảng drivers
CREATE TABLE drivers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(25) NOT NULL,
    license_number VARCHAR(30) NOT NULL,
    CONSTRAINT uq_driver_license UNIQUE (license_number)
) ENGINE=InnoDB;

-- 4. Bảng trips
CREATE TABLE trips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    driver_id INT NOT NULL,
    departure_date DATE NOT NULL,
    status ENUM('PENDING', 'IN_TRANSIT', 'COMPLETED') NOT NULL DEFAULT 'PENDING',
    CONSTRAINT fk_trip_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT,
    CONSTRAINT fk_trip_driver FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE RESTRICT,
    CONSTRAINT uq_trip_vehicle_date UNIQUE (vehicle_id, departure_date),
    CONSTRAINT uq_trip_driver_date UNIQUE (driver_id, departure_date)
) ENGINE=InnoDB;

-- 5. Bảng orders (Tạo sau cùng vì phụ thuộc vào trips và customers)
CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    trip_id INT NULL,
    pickup_address VARCHAR(255) NOT NULL,
    delivery_address VARCHAR(255) NOT NULL,
    weight_kg DECIMAL(10,2) NOT NULL,
    freight_amount DECIMAL(12,2) NOT NULL,
    CONSTRAINT fk_order_customer FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
    CONSTRAINT fk_order_trip FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE RESTRICT,
    CONSTRAINT chk_order_weight CHECK (weight_kg > 0),
    CONSTRAINT chk_order_freight CHECK (freight_amount >= 0)
) ENGINE=InnoDB;