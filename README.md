
# Ứng Dụng Trò Chuyện & Phát Trực Tuyến

## Giới thiệu

Đây là ứng dụng máy tính hỗ trợ trò chuyện, chia sẻ file, và phát trực tiếp video/audio giữa nhiều người dùng. Ứng dụng hỗ trợ cả đăng nhập xác thực và không xác thực (chế độ Khách), sử dụng Firebase cho xác thực và Firestore cho lưu trữ dữ liệu. File được lưu trữ trên Supabase và các stream được ghi lại trên máy người phát.

## Cài đặt

### 1. Biên dịch thành file thực thi (.exe)

Sử dụng lệnh sau trong CMD để tạo file `.exe`:

```bash
pyinstaller --onefile --windowed --noconsole final.py --add-data "networkapp-fab62-firebase-adminsdk-fbsvc-69c7879b05.json;."
```

Sau khi chạy, file `.exe` sẽ được tạo ra và có thể chạy trực tiếp.

### 2. Thiết lập môi trường

Trước khi chạy mã nguồn, thực thi file `setup.py` để cài đặt các thư viện cần thiết:

```bash
python setup.py
```

## Hướng dẫn sử dụng

### Đăng nhập và đăng ký

- **Chế độ Khách:** Chỉ có thể xem, không gửi được tin nhắn.
- **Đăng nhập:** Cần nhập đúng tên người dùng và mật khẩu.
- **Đăng ký:** Cần nhập tên người dùng và mật khẩu mới. Không hỗ trợ khôi phục mật khẩu.

### Gửi tin nhắn, chia sẻ file, và phát trực tiếp

- Chọn hoặc tạo kênh mới.
- Gửi tin nhắn bằng phím Enter.
- Gửi file bằng nút "Gửi file" (chỉ hỗ trợ từng file).
- Phát trực tiếp nếu là chủ kênh. Video sẽ lưu tại thư mục `%temp%`.

### Tham gia stream

- Chọn kênh có stream đang hoạt động.
- Nhấn "Join stream" để tham gia.

### Tính năng hỗ trợ

- Xem danh sách người dùng online.
- Chế độ ẩn danh.
- Đăng xuất để đổi tài khoản.
- Mỗi hành động đều được lưu vào cơ sở dữ liệu.
- Yêu cầu quyền truy cập IP, camera, micro.

## Lỗi thường gặp

- Chương trình khởi động chậm → chờ hoặc khởi động lại máy.
- Không gửi/stream được → kiểm tra kênh, quyền, hoặc trạng thái đăng nhập.
- Video không lưu → cần kết thúc stream đúng cách.
- Thiết bị không hỗ trợ → kiểm tra phần cứng hoặc quyền truy cập.

## Liên hệ

Mọi phản hồi hoặc báo lỗi xin gửi về: **nghiem.trinhaman@hcmut.edu.vn**

---

**Lưu ý:** Ứng dụng hiện KHÔNG hỗ trợ trên thiết bị di động.
