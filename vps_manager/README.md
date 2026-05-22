# VPS Management Dashboard - Trình Quản Trị VPS Cá Nhân

Đây là công cụ quản lý máy chủ Ubuntu VPS từ xa với giao diện đồ họa Web hiện đại (**Glassmorphism Dark Theme**), giúp bạn thao tác với VPS của mình thông qua giao thức SSH an toàn mà không cần nhớ hay gõ các câu lệnh terminal phức tạp.

## 🌟 Tính Năng Nổi Bật

1. **Giám Sát Tài Nguyên VPS (Dashboard)**: Theo dõi trực quan phần trăm sử dụng CPU, RAM, dung lượng ổ đĩa còn trống và thời gian hoạt động liên tục (Uptime) của VPS.
2. **Quản Lý Docker Container**:
   - Liệt kê toàn bộ các container hiện có trên VPS.
   - Thao tác nhanh: **Khởi chạy (Start)**, **Tạm dừng (Stop)**, **Khởi động lại (Restart)**.
   - Xem nhanh **Nhật ký hoạt động (Logs)** của từng container qua cửa sổ hiển thị (Modal) thông minh.
3. **Trình Soạn Thảo Cấu Hình (.env)**: Tải trực tiếp file `.env` của dự án `fast-media-kit` từ VPS lên giao diện, hỗ trợ chỉnh sửa trực quan và lưu đè hoặc tự động restart container chỉ với 1 click chuột.
4. **Terminal Console (Dòng Lệnh VPS)**: Thực thi nhanh bất kỳ câu lệnh Linux tùy biến nào lên VPS một cách nhanh chóng và an toàn.

---

## 🚀 Hướng Dẫn Khởi Chạy Nhanh

### 1. Cài đặt thư viện cần thiết (Nếu chưa cài)
Mở terminal tại máy tính cá nhân của bạn và chạy lệnh cài đặt:
```bash
pip install paramiko fastapi uvicorn
```

### 2. Chạy ứng dụng
Do bạn đang đứng ở trong thư mục `vps_manager`, hãy chạy câu lệnh:
```bash
python main.py
```

*Lưu ý: Nếu bạn đứng từ thư mục gốc của dự án `quick-media-tools`, bạn có thể chạy:*
```bash
python vps_manager/main.py
```

### 3. Truy cập giao diện quản lý
Mở trình duyệt Web của bạn và truy cập địa chỉ:
👉 **`http://localhost:9000`**

---

## 🔒 Bảo Mật & Lưu Trữ
- **Lưu trữ Cục bộ**: Thông tin IP, Username và Mật khẩu SSH được lưu an toàn trong file `config.json` ngay tại máy tính cá nhân của bạn.
- **Không Chia sẻ**: Ứng dụng chạy hoàn toàn local (cục bộ trên máy của bạn), không gửi hay chia sẻ thông tin đăng nhập VPS của bạn qua bất kỳ máy chủ trung gian nào.
