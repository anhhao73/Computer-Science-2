# Mini TMS — Quản lý vận chuyển

Ứng dụng bài tập dùng Python, Tkinter và MySQL. Chạy `main.py` từ thư mục chứa file này.

## 1. Chuẩn bị trên máy giảng viên

- Python 3.10 trở lên, có Tkinter (bản cài Python cho Windows thường có sẵn).
- MySQL Server 8.0.16 trở lên để thực thi các ràng buộc CHECK; đã kiểm tra trên MySQL 8.0.46.
- Tài khoản MySQL có quyền đọc/ghi database dùng cho bài tập. Việc tạo database/bảng cần quyền tương ứng.
- Cài thư viện trong PowerShell tại thư mục dự án:

```powershell
python -m pip install -r requirements.txt
```

Đã kiểm tra với Python 3.10 và mysql-connector-python 26.7.0. Yêu cầu connector từ 9.2 để hỗ trợ thời gian chờ đọc/ghi.

## 2. Cấu hình kết nối

`config.py` đọc các biến môi trường dưới đây. Giá trị đặt trong PowerShell chỉ áp dụng cho phiên PowerShell đó và ứng dụng khởi chạy từ phiên đó.

| Biến | Giá trị trên máy giảng viên |
|---|---|
| DB_HOST | `localhost` nếu MySQL chạy trên chính máy đó |
| DB_PORT | `3306` hoặc cổng thực tế |
| DB_NAME | `mini_tms` |
| DB_USER | Tài khoản MySQL trên máy giảng viên |
| DB_PASSWORD | Mật khẩu của tài khoản trên máy giảng viên |

```powershell
$env:DB_HOST = 'localhost'
$env:DB_PORT = '3306'
$env:DB_NAME = 'mini_tms'
$env:DB_USER = 'root'
$env:DB_PASSWORD = Read-Host 'Nhap mat khau MySQL' -MaskInput
python -B main.py
```

`-MaskInput` dùng PowerShell 7.1 trở lên. Nếu dùng Windows PowerShell 5.1, có thể đặt `DB_PASSWORD` bằng hộp cấu hình biến môi trường của Windows rồi mở lại PowerShell.

`config.py` hiện giữ cấu hình mặc định dành cho máy Vinh, có mật khẩu cục bộ. **Trước khi gửi source, thay mật khẩu mặc định trong bản bàn giao bằng chuỗi rỗng**; không gửi mật khẩu cá nhân hoặc thư mục `backups`. Cấu hình của máy Vinh không tự tạo tài khoản/database trên máy khác.

## 3. Nhập dữ liệu lần đầu

Chỉ thực hiện khi database đích chưa có các bảng của dự án:

1. Mở MySQL Workbench, kết nối tới MySQL của máy đó.
2. Chạy `sql/schema.sql` để tạo database, bảng và ràng buộc.
3. Chạy `sql/sample_data.sql` một lần.
4. Nếu có lỗi khi nhập dữ liệu mẫu, dừng và `ROLLBACK`; không tiếp tục tới `COMMIT`.
5. Chạy `python -B main.py`.

Hai file SQL đặt tên database là `mini_tms`. Nếu dùng tên khác, điều chỉnh `CREATE DATABASE`/`USE` trong bản SQL nhập và đặt `DB_NAME` tương ứng trước khi chạy ứng dụng.

Dữ liệu mẫu: 15 khách hàng, 8 xe, 8 tài xế, 12 chuyến, 40 đơn; 10 đơn chưa phân công. Trạng thái chuyến: 5 chờ, 4 đang vận chuyển, 3 hoàn thành. Chuyến #2 rỗng là dữ liệu kiểm thử có chủ đích. Ngày quá khứ được phép trong phạm vi bài tập.

**Không chạy lại `sample_data.sql` trên database đã có dữ liệu.** Thay đổi file SQL không tự cập nhật dữ liệu đã nhập.

## 4. Sửa bốn bản ghi mẫu cũ

Máy Vinh đã được đồng bộ ngày 18/10/2026. Công cụ dưới đây chỉ dành cho database đã nhập bản mẫu cũ của nhóm:

```powershell
# Xem trước, chỉ đọc dữ liệu:
python -B ../mini_tms_support/tools/repair_legacy_data.py
# Áp dụng khi cần:
python -B ../mini_tms_support/tools/repair_legacy_data.py --apply
```

Công cụ kiểm tra quan hệ/trạng thái và giá trị cũ trước khi sửa, khóa dữ liệu, sao lưu bốn đơn vào `../mini_tms_support/backups/legacy_orders_*.json`, rồi cập nhật trong một giao dịch:

| Đơn | Cũ | Đúng theo mẫu |
|---|---|---|
| #15 | Chuyến #1 | Chuyến #3 |
| #20 | 300 kg | 100 kg |
| #28 | 700 kg | 150 kg |
| #30 | 800 kg | 100 kg |

Nếu gặp giá trị khác dự kiến hoặc còn chuyến quá tải, công cụ dừng và rollback. Chạy lại ngay sau khi đồng bộ không phát sinh thay đổi. Nếu người dùng đã vận hành và đổi trạng thái chuyến, công cụ có thể từ chối: không ép chạy hoặc nhập lại seed.

## 5. Sử dụng và khôi phục kết nối

- Khách hàng → Đơn vận chuyển → Xe và tài xế → Chuyến xe → Gán đơn → Khởi hành → Hoàn thành.
- Số nhập không có dấu phân cách hàng nghìn, dùng dấu chấm thập phân; ngày `YYYY-MM-DD`. Điện thoại là chuỗi, giữ số 0 đầu.
- Chỉ sửa đơn chưa phân công; chỉ thêm/bỏ đơn khi chuyến đang chờ. Tổng tải bằng tải trọng xe được phép.
- Xe và tài xế mỗi đối tượng chỉ có một chuyến/ngày, kể cả chuyến đã hoàn thành.
- Trang chủ đọc dữ liệu nhất quán từ service; thanh tải hiển thị ba chuyến chờ sớm nhất, bảng có đủ chuyến chờ.
- Sau thao tác thành công, các tab liên quan và Trang chủ được làm mới. Nếu đang mở nhiều cửa sổ, dùng Làm mới để đọc thay đổi từ cửa sổ khác.
- Nếu mất kết nối, khôi phục MySQL rồi nhấn **Kết nối lại** ở chân cửa sổ. Form đang nhập được giữ, các danh sách được nạp lại.
- Không tự gửi lại thao tác ghi sau lỗi kết nối. Nếu lỗi xảy ra lúc lưu/commit, kết quả có thể chưa rõ: kết nối lại và kiểm tra danh sách trước khi lưu lần nữa để tránh tạo trùng.
- Nếu thay đổi cấu hình môi trường, mở lại ứng dụng để nạp cấu hình mới.

Thời gian chờ: kết nối 5 giây; đọc/ghi 10 giây cho từng thao tác mạng. Từ 19/10/2026, `main.py` chứa và dùng lớp `ServiceWorker`: một worker duy nhất tạo, sử dụng và đóng kết nối MySQL. Tkinter vẫn xử lý vẽ lại, di chuyển/đổi kích thước cửa sổ và bộ đếm thời gian trong lúc chờ. Các thao tác dữ liệu được tạm chặn để tránh gửi trùng; sau 120 ms xuất hiện tiến trình. Worker không truy cập widget, không tự chạy lại thao tác ghi. Nếu bấm đóng khi đang xử lý, chờ hoàn tất rồi bấm đóng lại. Tổng thời gian nhiều truy vấn vẫn có thể dài hơn 10 giây.

Phím tắt: **F5** làm mới màn hình hiện tại; **Alt+Home** về Trang chủ. Tab và Shift+Tab di chuyển giữa các điều khiển. Giao diện được kiểm tra ở 1180×820 và 1000×780; ở kích thước nhỏ, dùng thanh cuộn bảng để xem thêm dòng.

## 6. Kiểm thử

```powershell
# Kiểm thử tự động bằng kết nối/service giả; không ghi database thật:
python -B -m unittest discover -s ../mini_tms_support/tests -q
# Kiểm thử MySQL thật, tự tạo database thử riêng:
python -B ../mini_tms_support/tests/run_mysql_integration.py --worker
```

Kiểm thử MySQL cần quyền tạo database. Nó tạo database `mini_tms_verify_<thoi_gian>`, nhập dữ liệu và chạy luồng Tkinter trên database đó; không nhập lại seed vào `mini_tms`. Database thử được giữ lại; kết quả lưu tại `../mini_tms_support/tests/mysql_integration_result.json`. Các hộp xác nhận trong bài kiểm thử được tự động trả lời, cửa sổ Tkinter được ẩn.

Kết quả ngày 19/10/2026: 62 kiểm tra tự động đạt; 35 kiểm tra tích hợp MySQL qua worker đạt, gồm rollback, tải bằng giới hạn, chuyển trạng thái, cập nhật liên tab, đọc snapshot khi có ghi đồng thời và kết nối lại giữ form. Đây không phải kiểm thử chịu tải nhiều người dùng.

## 7. Phân công và hợp đồng tích hợp

| Thành viên | Phần phụ trách và điểm nối |
|---|---|
| Vinh | `main.py`, `config.py`, `views/`: gọi service dùng chung, giữ ID số nguyên, Decimal/date; không chạy SQL từ view |
| Hào | `models.py`, `services.py`: kiểm tra nghiệp vụ; `get_dashboard_data()` trả `counts`, `rows`, `unassigned` trong một snapshot |
| Duy | `database.py`: truy vấn tham số, giao dịch/khóa, thời gian chờ; `transaction(snapshot=True)` chỉ đọc với REPEATABLE READ; `connect()` được gọi lại khi người dùng yêu cầu |
| Long | `sql/`, dữ liệu mẫu và hướng dẫn cài đặt; phối hợp cập nhật dữ liệu đã nhập qua công cụ có điều kiện |

Bằng chứng cải tiến và ảnh thực tế: `../mini_tms_support/review_artifacts/REPORT.md`. Các công cụ chụp ảnh dùng `../mini_tms_support/requirements-dev.txt`, không cần cài Pillow để chạy ứng dụng thông thường.

Khi bàn giao cần có toàn bộ mã nguồn, `requirements.txt`, thư mục `views`, `sql` và README. Bộ kiểm thử/công cụ bổ sung nằm riêng trong thư mục kế bên `mini_tms_support`. Không cần gửi `__pycache__`, database kiểm thử hoặc bản sao dữ liệu cục bộ. Sau khi sao chép, kiểm tra trên máy giảng viên bằng database mới và cấu hình của chính máy đó.


## 8. Cấu trúc bàn giao đã thu gọn

```text
mini_tms/
├── main.py
├── config.py
├── requirements.txt
├── README.md
├── models.py
├── services.py
├── database.py
├── views/
│   ├── main_window.py
│   ├── customer_view.py
│   ├── fleet_view.py
│   ├── order_view.py
│   └── trip_view.py
└── sql/
    ├── schema.sql
    └── sample_data.sql
```

`main.py` chứa cả lớp ServiceWorker điều phối I/O và hàm khởi động. `views/main_window.py` chứa cửa sổ chính, DashboardMixin, cấu hình theme và DataTable dùng chung. Các view nhập DataTable từ main_window; cửa sổ chính nhập các view khi xây dựng màn hình để tránh import vòng. Chức năng xử lý nền, giao diện, biểu đồ và nghiệp vụ không bị loại bỏ.

`mini_tms_support` nằm cùng cấp với `mini_tms`, chứa tests, tools, backups, review_artifacts, requirements-dev và các module gốc để tham khảo. Ứng dụng không cần thư mục hỗ trợ để chạy. Chạy các lệnh kiểm thử ở mục 6 từ thư mục `mini_tms`.

Dùng `python -B main.py` để không sinh thư mục `__pycache__`. Nếu chạy Python không có `-B`, cache tự sinh là bình thường và không phải file mã nguồn bổ sung.
