# Bot giao dịch (khái niệm)

Đây là kiến thức về **cơ chế**, không phải hướng dẫn mở tài khoản hay cài máy trên một sàn cụ thể.

Bot không bảo đảm lãi. Máy chỉ lặp lại lệnh đã kê. Nhận định sai hướng vẫn mất hết số tiền đã bỏ vào con bot đó.

## Bot lưới

Bot lưới kê sẵn nhiều mức mua và bán trong **một khoảng giá**. Giá dao động trong khoảng thì bot khớp từng nhịp nhỏ (mua thấp hơn / bán cao hơn trong lưới). Không cần bắt đúng một điểm đỉnh hay đáy.

Lưới sống nhờ giá **đi hai chiều** trong khoảng đã kê. Coin “nóng” chạy một mạch, hoặc đứng im không nhịp, thì giả định của máy gãy — không phải vì chưa “top”.

Khoảng giá đã chọn là một phần của máy. Kéo khoảng theo giá đang chạy là chiến lược khác, không còn là lưới ban đầu.

Hai cách chia ô trong khoảng (chỉ để hiểu, không phải bộ số cài):

- Chia đều theo **khoảng giá** (ô cách nhau một đoạn tiền).
- Chia đều theo **phần trăm**.

Không có loại nào “đúng mọi lúc”.

Giới hạn:

- Ngoài khoảng giá đã kê, bot ngừng mua-bán theo lưới. Lệnh còn sót phải xử lý như lệnh thường — và phần sót vẫn mang **rủi ro theo hướng** giá đang đi.
- Lãi từng nhịp nhỏ không có nghĩa bot bất tử. Giá đi ngược rồi quay về chỗ bắt đầu, máy vẫn có thể đã khớp vài nhịp trong lưới; đó chỉ là đường lãi-lỗ của cơ chế, không phải bảo chứng.
- Bot không thay nhận định hướng. “Không vào thì tiếc, vào rồi thì run” là vấn đề tâm lý; máy không sửa view sai.

## Bot DCA (trung bình giá)

DCA nghĩa là mua thêm khi giá đi ngược, rồi chốt **một điểm** khi giá trung bình hồi đủ một khoảng đã chọn. Khác lưới: lưới vừa mua vừa bán nhiều điểm; DCA chủ yếu xếp lệnh cùng một hướng rồi chốt cả cụm.

Hai hình dạng rủi ro khác nhau (không phải mẹo):

- Nhồi thêm khi **đang lỗ** (kéo giá vốn): lỗ có thể lớn hơn, không phải “cách cứu lệnh”.
- Nhồi thêm khi **đang lãi**: số lãi nhìn to nhanh hơn, nhưng vạch cháy cũng có thể bị kéo. Không phải an toàn hơn.

Thang mua đã kê có thể **hết tiền đã gắn** trước khi khớp hết các mức còn lại phía dưới. Lúc đó kế hoạch ban đầu đã đứt — bơm thêm là cược mới, không phải “cho máy chạy nốt”.

Máy hai chiều / “trung lập” (không gắn sẵn một hướng): giá lên đánh một phía, giá xuống đánh phía kia. Tốn vốn hơn máy một chiều. Vẫn không phải rủi ro bằng không.

Giới hạn:

- Có nhịp hồi thì cơ chế mới chạy được. Giá đi một mạch không hồi thì số đã xếp có thể mất hết.
- Sống được vài tháng không phải bảo chứng. Thanh khoản kém thì cơ chế khớp chậm hoặc kẹt.

## Đọc số, tách túi, dừng

Nhìn **tiền lãi-lỗ thật**, không nhìn % xanh trên biểu đồ. % đẹp có thể chưa phải tiền đã cầm về.

Một máy chỉ cháy đúng số đã gắn **khi** túi tiền của máy đó tách khỏi túi khác. Nhiều máy chung một túi: một máy nổ có thể kéo theo máy còn lại.

Lãi đã khớp mà để lại trong cùng túi vẫn có thể mất tiếp. Lấy lãi ra thì túi còn lại nhỏ hơn, máy yếu hơn. Không có lựa chọn “vừa rút vừa lì như lúc chưa rút”.

Sửa khoảng giá / thông số khi đang chạy = không còn đúng máy lúc bắt đầu. Máy đang lỗ mà đổi khoảng gần với cắt lỗ rồi mở máy mới bằng số còn lại nhỏ hơn.

Có thể đặt chỗ dừng theo giá, theo lãi-lỗ, hoặc hết một vòng rồi nghỉ. Không đặt chỗ dừng thì số đã gắn có thể chạy tới hết.

Nếu mọi mức mua an toàn đã khớp hết, kế hoạch trung bình giá ban đầu đã xong. Tiếp tục là cược mới.

## Rủi ro cần nhớ

- Chỉ bỏ vào bot số tiền chấp nhận mất hết. Tiền thuê nhà / ăn uống không thuộc nhóm này.
- Công cụ nhân số lần (đòn bẩy) làm lỗ lớn hơn số mình tưởng. Không có mức nhân “không cháy”.
- Thêm tiền vào bot đang chạy để “cho lì hơn” thì khi cháy mất cả phần thêm.
- Không phó mặc 100% cho máy. Không tin “bot = thu nhập thụ động”.

## Không có trong chương này

Không có tên sàn, không có nút bấm, không có bộ số cài sẵn, không có copy bot / hoa hồng, không có danh sách coin để chạy máy. Phần thao tác trên nền tảng chưa được Bộ Tài chính cấp phép không đưa lên sách public (xem chương phạm vi và pháp lý).
