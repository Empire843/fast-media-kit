# Taste-Skill Design Specification: Quick Media Tools

Tài liệu này xác định các tiêu chuẩn thẩm mỹ và quy chuẩn thiết kế giao diện cho dự án **Quick Media Tools** dựa trên triết lý Taste-Skill (Anti-Slop Frontend).

## Thiết lập Dials (Dial Configuration)

Vì đây là một ứng dụng Dashboard công cụ kỹ thuật dành cho Creator (Utility Dashboard), các chỉ số thiết lập được tối ưu hóa như sau:

*   **`DESIGN_VARIANCE: 4`** - Ưu tiên bố cục gọn gàng, cân đối, các khối chức năng rõ ràng. Không sử dụng các hình khối hoặc lệch trục phi đối xứng quá đà.
*   **`MOTION_INTENSITY: 5`** - Chuyển động mượt mà, thời gian chuyển động nhanh (`0.2s` đến `0.25s`), sử dụng cubic-bezier tinh tế. Đảm bảo tuân thủ `prefers-reduced-motion`.
*   **`VISUAL_DENSITY: 7`** - Mật độ thông tin cao để người dùng có cái nhìn bao quát về tham số cấu hình, nhưng giữ khoảng đệm (padding/gap) hợp lý để không gây ngột ngạt.

## Ngôn ngữ thiết kế (Design Language)

### 1. Palette màu (Sleek Dark Tech)
Chúng ta sử dụng bảng màu tối (Dark Mode mặc định) lấy cảm hứng từ các công cụ cao cấp như Linear hoặc Vercel:
*   **Nền chính (Background):** Slate tối sâu (`#080b11`) để giảm mỏi mắt.
*   **Nền thẻ/Panel (Card/Surface):** Slate xám đậm (`#0f131a`).
*   **Viền (Borders):** Viền mảnh mờ (`rgba(255, 255, 255, 0.07)` hoặc `#1e293b`).
*   **Màu nhấn chính (Primary Accent):** Emerald/Mint Green (`#10b981`) và Cyan/Blue (`#06b6d4`) tạo ra dải gradient mượt mà.
*   **Màu text chính (Text Primary):** Trắng xám (`#f3f4f6`).
*   **Màu text phụ (Text Secondary):** Xám nhạt (`#9ca3af`).

### 2. Typography
*   Sử dụng font **Outfit** từ Google Fonts cho các tiêu đề chính, con số và thẻ trạng thái để mang lại cảm giác công nghệ cao cấp.
*   Sử dụng font **Inter** cho text body, form inputs, labels và các đoạn văn bản mô tả để tối ưu độ đọc.
*   Sử dụng font chữ Monospace chất lượng cao (**Cascadia Mono** hoặc **Consolas**) cho các bảng so sánh text và log panel.

### 3. Quy chuẩn các thành phần UI
*   **Bo góc (Border Radius):**
    *   Thành phần nhỏ (nút bấm, input): `8px` (`--rs`).
    *   Thành phần lớn (card, panels, drop zone): `12px` (`--r`).
*   **Độ phản hồi xúc giác (Tactile Feedback):**
    *   Tất cả các nút bấm tương tác phải có hiệu ứng scale nhỏ nhẹ (`transform: scale(0.98)`) khi bấm (`:active`).
    *   Trạng thái focus của Input phải hiển thị viền màu nhấn kèm bóng mờ nhẹ (`box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2)`).
*   **Vùng kéo thả (Drop Zone):**
    *   Không để phẳng lỳ. Khi kéo file đè lên (`.dragover`), đường viền nét đứt của drop-zone sẽ chuyển động xoay hoặc chạy vòng quanh để biểu thị trạng thái sẵn sàng nhận file.

## Kỷ luật code frontend (AI Anti-Slop Rules)
1. **Không dùng Placeholders:** Mọi icon phải là SVG thực tế, sắc nét, không dùng ký tự text làm icon.
2. **Đồng nhất:** Không pha trộn nhiều thư viện thiết kế. Giữ CSS thuần, tối ưu hóa các biến CSS để dễ bảo trì.
3. **Giữ nguyên logic nghiệp vụ:** Không chỉnh sửa hoặc xóa bỏ các thuộc tính ID, Class hoặc attributes bắt đầu bằng `data-` mà JavaScript dùng để điều khiển luồng hoạt động (ví dụ: `data-tool`, `data-async-form`, `data-sheet-loader`).
