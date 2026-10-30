-- Dữ liệu giả lập. Chỉ nhập một lần trên DB mới sau schema.sql.
-- Nếu nhập lỗi: dừng và ROLLBACK; không tiếp tục COMMIT phần còn lại.
USE mini_tms;

-- BẮT ĐẦU TRANSACTION
START TRANSACTION;

-- 1. NHẬP CUSTOMERS (15 khách hàng, có 2 tên gần giống để test UI)
INSERT INTO customers (id, name, phone, address) VALUES
(1, 'Nguyễn Văn A', '0901234567', '123 Lê Lợi, Quận 1, TP.HCM'),
(2, 'Trần Thị B', '0912345678', '456 Nguyễn Huệ, Quận 1, TP.HCM'),
(3, 'Công ty TNHH Logistics X', '02833334444', '789 Điện Biên Phủ, Quận 3, TP.HCM'),
(4, 'Nguyễn Văn Ánh', '0909876543', '101 Cách Mạng Tháng 8, Quận 10, TP.HCM'),
(5, 'Lê Hoàng C', '0933445566', '202 Hai Bà Trưng, Quận 3, TP.HCM'),
(6, 'Phạm Minh D', '0944556677', '303 Võ Văn Tần, Quận 3, TP.HCM'),
(7, 'Cửa hàng Thực phẩm Sạch', '0255667788', '404 Lý Thường Kiệt, Quận 10, TP.HCM'),
(8, 'Vũ Thị E', '0955667788', '505 Lê Đại Hành, Quận 11, TP.HCM'),
(9, 'Đặng Văn F', '0966778899', '606 Tô Hiến Thành, Quận 10, TP.HCM'),
(10, 'Bùi Thị G', '0977889900', '707 Sư Vạn Hạnh, Quận 10, TP.HCM'),
(11, 'Công ty CP Giao Vận Nhanh', '02888889999', '808 Nguyễn Trãi, Quận 5, TP.HCM'),
(12, 'Nguyễn Văn Bình', '0901112222', '909 Trần Hưng Đạo, Quận 5, TP.HCM'),
(13, 'Lý Thị H', '0912223333', '111 Hồng Bàng, Quận 5, TP.HCM'),
(14, 'Trương Văn I', '0923334444', '222 Ngô Gia Tự, Quận 10, TP.HCM'),
(15, 'Siêu thị Mini K', '0934445555', '333 Lê Hồng Phong, Quận 10, TP.HCM');

-- 2. NHẬP VEHICLES (8 xe, tải trọng 500-5000kg)
INSERT INTO vehicles (id, plate_number, capacity_kg) VALUES
(1, '51C-12345', 1000.00), -- Xe Test Chuyến A
(2, '51C-99999', 5000.00),
(3, '51C-11111', 2000.00),
(4, '51C-22222', 1500.00),
(5, '51C-33333', 800.00),
(6, '51C-44444', 3500.00),
(7, '51C-55555', 500.00),
(8, '51C-66666', 4000.00);

-- 3. NHẬP DRIVERS (8 tài xế)
INSERT INTO drivers (id, name, phone, license_number) VALUES
(1, 'Lê Văn Tài', '0981111111', 'B2-123456'),
(2, 'Nguyễn Văn Xế', '0982222222', 'B2-234567'),
(3, 'Trần Văn Lái', '0983333333', 'C-345678'),
(4, 'Phạm Văn Phụ', '0984444444', 'B2-456789'),
(5, 'Hoàng Văn Bánh', '0985555555', 'C-567890'),
(6, 'Đỗ Văn Lốp', '0986666666', 'B2-678901'),
(7, 'Vũ Văn Động', '0987777777', 'C-789012'),
(8, 'Ngô Văn Cơ', '0988888888', 'B2-890123');

-- 4. NHẬP TRIPS (12 chuyến)
INSERT INTO trips (id, vehicle_id, driver_id, departure_date, status) VALUES
-- CHUYẾN CHỜ (PENDING)
(1, 1, 1, '2026-10-20', 'PENDING'), -- Chuyến A (Test vượt tải, hiện có 950kg)
(2, 2, 2, '2026-10-21', 'PENDING'), -- Chuyến B (Rỗng - Test không cho khởi hành)
(3, 3, 3, '2026-10-22', 'PENDING'),
(4, 4, 4, '2026-10-23', 'PENDING'),
(5, 5, 5, '2026-10-24', 'PENDING'),
-- CHUYẾN ĐANG CHẠY (IN_TRANSIT)
(6, 6, 6, '2026-10-18', 'IN_TRANSIT'), -- Chuyến C (Test không cho thêm/bớt)
(7, 7, 7, '2026-10-18', 'IN_TRANSIT'),
(8, 8, 8, '2026-10-19', 'IN_TRANSIT'),
(9, 1, 2, '2026-10-19', 'IN_TRANSIT'), -- Xe 1 chạy ngày khác
-- CHUYẾN HOÀN THÀNH (COMPLETED)
(10, 2, 1, '2026-10-17', 'COMPLETED'),
(11, 3, 4, '2026-10-17', 'COMPLETED'),
(12, 4, 5, '2026-10-16', 'COMPLETED');

-- 5. NHẬP ORDERS (40 đơn)
-- Lưu ý: Tổng tải các đơn của Trip 1 = 950kg
INSERT INTO orders (id, customer_id, trip_id, pickup_address, delivery_address, weight_kg, freight_amount) VALUES
-- 30 Đơn đã được phân công
(1, 1, 1, 'Kho Q1', 'Quận 3', 500.00, 150000.00),
(2, 2, 1, 'Kho Q1', 'Quận 5', 450.00, 120000.00), -- Tổng 2 đơn Trip 1 = 950kg
(3, 3, 3, 'Kho Q3', 'Quận 10', 200.00, 50000.00),
(4, 4, 4, 'Kho Q10', 'Quận 11', 300.00, 80000.00),
(5, 5, 5, 'Kho Q5', 'Quận 1', 400.00, 100000.00),
(6, 6, 6, 'Kho Q3', 'Quận 7', 1000.00, 300000.00),
(7, 7, 6, 'Kho Q10', 'Quận 4', 500.00, 150000.00),
(8, 8, 7, 'Kho Q11', 'Quận 2', 250.00, 90000.00),
(9, 9, 8, 'Kho Q10', 'Quận 9', 800.00, 250000.00),
(10, 10, 9, 'Kho Q5', 'Quận 12', 350.00, 110000.00),
(11, 11, 10, 'Kho Q1', 'Quận Bình Thạnh', 600.00, 180000.00),
(12, 12, 10, 'Kho Q1', 'Quận Phú Nhuận', 400.00, 120000.00),
(13, 13, 11, 'Kho Q5', 'Quận Tân Bình', 700.00, 210000.00),
(14, 14, 12, 'Kho Q10', 'Quận Gò Vấp', 550.00, 160000.00),
(15, 15, 3, 'Kho Q10', 'Quận Tân Phú', 0.01, 10000.00), -- Chuyển sang chuyến 3 để chuyến 1 đúng 950kg
(16, 1, 3, 'A', 'B', 100.00, 20000.00),
(17, 2, 4, 'A', 'B', 150.00, 30000.00),
(18, 3, 5, 'A', 'B', 200.00, 40000.00),
(19, 4, 6, 'A', 'B', 250.00, 50000.00),
(20, 5, 7, 'A', 'B', 100.00, 60000.00),
(21, 6, 8, 'A', 'B', 350.00, 70000.00),
(22, 7, 9, 'A', 'B', 400.00, 80000.00),
(23, 8, 10, 'A', 'B', 450.00, 90000.00),
(24, 9, 11, 'A', 'B', 500.00, 100000.00),
(25, 10, 12, 'A', 'B', 550.00, 110000.00),
(26, 11, 3, 'A', 'B', 600.00, 120000.00),
(27, 12, 4, 'A', 'B', 650.00, 130000.00),
(28, 13, 5, 'A', 'B', 150.00, 140000.00), -- Chuyến #5: 400 + 200 + 150 = 750 kg <= 800 kg
(29, 14, 6, 'A', 'B', 750.00, 150000.00),
(30, 15, 7, 'A', 'B', 100.00, 160000.00),

-- 10 Đơn CHƯA PHÂN CÔNG (trip_id = NULL)
(31, 1, NULL, 'Kho Q1', 'Quận 4', 100.00, 30000.00),  -- Test vượt tải (Thêm vào Trip 1: 950 + 100 = 1050 > 1000)
(32, 2, NULL, 'Kho Q1', 'Quận 4', 50.00, 15000.00),   -- Test biên bằng tải (Thêm vào Trip 1: 950 + 50 = 1000)
(33, 3, NULL, 'Kho Q3', 'Quận 2', 200.00, 50000.00),
(34, 4, NULL, 'Kho Q10', 'Quận 9', 300.00, 60000.00),
(35, 5, NULL, 'Kho Q5', 'Quận 7', 400.00, 70000.00),
(36, 6, NULL, 'Kho Q3', 'Quận 12', 500.00, 80000.00),
(37, 7, NULL, 'Kho Q10', 'Quận Bình Tân', 600.00, 90000.00),
(38, 8, NULL, 'Kho Q11', 'Quận Tân Bình', 700.00, 100000.00),
(39, 9, NULL, 'Kho Q10', 'Quận Phú Nhuận', 800.00, 110000.00),
(40, 10, NULL, 'Kho Q5', 'Quận Gò Vấp', 900.00, 120000.00);

-- KẾT THÚC TRANSACTION
COMMIT;
