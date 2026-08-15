# Bot giao dịch (khái niệm)

Đây là kiến thức về **cơ chế**, không phải hướng dẫn mở tài khoản hay cài máy trên một sàn cụ thể.

Bot không bảo đảm lãi. Máy chỉ lặp lại lệnh đã kê. Nhận định sai hướng vẫn mất hết số tiền đã bỏ vào con bot đó.

## Bot lưới

Bot lưới kê sẵn nhiều mức mua và bán trong **một khoảng giá**. Giá dao động trong khoảng thì bot khớp từng nhịp nhỏ (mua thấp hơn / bán cao hơn trong lưới). Không cần bắt đúng một điểm đỉnh hay đáy.

Giới hạn:

- Ngoài khoảng giá đã kê, bot ngừng mua-bán theo lưới. Lệnh còn sót phải xử lý như lệnh thường.
- Lãi từng nhịp nhỏ không có nghĩa bot bất tử. Vẫn có kịch bản mất hết số đã gắn vào bot.
- Bot không thay nhận định hướng. “Không vào thì tiếc, vào rồi thì run” là vấn đề tâm lý; máy không sửa view sai.

## Bot DCA (trung bình giá)

DCA nghĩa là mua thêm khi giá đi ngược, rồi chốt **một điểm** khi giá trung bình hồi đủ một khoảng đã chọn. Khác lưới: lưới vừa mua vừa bán nhiều điểm; DCA chủ yếu xếp lệnh cùng một hướng rồi chốt cả cụm.

Giới hạn:

- Có nhịp hồi thì cơ chế mới chạy được. Giá đi một mạch không hồi thì số đã xếp có thể mất hết.
- Nhồi thêm khi đang lỗ (kéo giá vốn) làm rủi ro lớn hơn, không phải “cách cứu lệnh”.
- Sống được vài tháng không phải bảo chứng. Thanh khoản kém thì cơ chế khớp chậm hoặc kẹt.

## Rủi ro cần nhớ

- Chỉ bỏ vào bot số tiền chấp nhận mất hết. Tiền thuê nhà / ăn uống không thuộc nhóm này.
- Công cụ nhân số lần (đòn bẩy) làm lỗ lớn hơn số mình tưởng. Không có mức nhân “không cháy”.
- Thêm tiền vào bot đang chạy để “cho lì hơn” thì khi cháy mất cả phần thêm.
- Không phó mặc 100% cho máy. Không tin “bot = thu nhập thụ động”.

## Không có trong chương này

Không có tên sàn, không có nút bấm, không có bộ số cài sẵn, không có copy bot / hoa hồng. Phần thao tác trên nền tảng chưa được Bộ Tài chính cấp phép không đưa lên sách public (xem chương phạm vi và pháp lý).
