# Hậu kỳ bot: đọc số, dừng, chốt

Kiến thức vận hành máy sau khi đã chạy. Không có tên sàn. Không có mã lỗi của một nền tảng.

## Đóng máy thì cầm về bao nhiêu?

Lấy **tổng lãi-lỗ (P&L)**, không lấy % xanh trên chart.

- Lãi đã rút / đã chốt = tiền đã cầm về.
- Lãi “treo” / tiềm năng = chưa chốt, chưa phải tiền túi.
- Số chính xác lúc đóng (lưới lẫn DCA) là tổng P&L.

Bật xem **cụm lệnh trên đồ thị** để đọc máy đang mua/bán tới đâu. Dùng để quản lý, không để tưởng tay sẽ gồng được như máy.

## Rút lãi thì máy yếu đi

Lãi lưới mặc định thường cộng vào ký quỹ: máy lì hơn, vạch cháy xa hơn. Rút lãi / bớt ký quỹ: cầm được tiền về nhưng vạch cháy gần hơn. Không có lựa chọn “vừa rút vừa lì như lúc chưa rút”.

## Sửa khoảng / sửa thông số khi đang chạy

Bot lưới: sửa khoảng giá và số ô thì máy đóng toàn bộ lệnh đang kê để dựng lưới mới. Chỉ hợp khi máy đang có lãi, hoặc giá đã ra ngoài khoảng mà vẫn muốn theo máy đó. Máy đang âm mà sửa ≈ cắt lỗ rồi tạo máy mới bằng số còn lại nhỏ hơn.

Bot DCA: bước giá / % chốt / số ô / số tiền tạo thường không sửa được sau khi tạo. Ký quỹ, tái đầu tư, điều kiện dừng thì sửa được.

Sửa giữa chừng = không còn đúng máy lúc bắt đầu.

## Không dùng “tăng vị thế”

Tăng vị thế = thêm vốn vào máy đang chạy. Thường thêm được, rút phần thêm không được. Nếu phải chọn giữa thêm vị thế và ký quỹ thì lúc dạy ưu tiên ký quỹ (bơm vào rút ra được). Tốt nhất không dùng.

Với DCA: phần thêm chỉ sống một vòng hiện tại; sau lần chốt bị đẩy ra. Thêm rồi không xóa được. Giảng viên gần như không dùng nữa.

Thêm tiền để “cho lì hơn” thì khi cháy mất cả phần thêm.

## Điều kiện dừng

Giống chốt lời / cắt lỗ cho cả máy. Các kiểu lúc dạy kể: làm tay (mặc định), theo giá, theo RSI (giảng viên không dùng), theo tín hiệu bên ngoài (không dạy).

Có thể cài chốt / dừng theo giá hoặc theo % lãi-lỗ; chạm một trong hai thì máy đóng.

DCA: “hết vòng thì nghỉ” = sau lần chốt vòng hiện tại thì đóng toàn bộ, không mở vòng mới. Dùng khi đang gồng lỗ, muốn về chỗ bắt đầu rồi nghỉ.

Không đặt chỗ dừng thì số đã gắn có thể chạy tới hết.

## Không dùng chung một túi ký quỹ cho nhiều máy

Ký quỹ tự chuyển = nhiều máy dùng chung một quỹ. Tiết kiệm khi ít tiền, nhưng biến động mạnh dễ cháy cả cụm. Máy nào túi đó. 2 máy còn dùng được; 5–7 máy chung một mẻ thì rất khó.

Tách túi thì một máy cháy mất đúng túi đó — **chỉ khi** không chung quỹ.

## Ngưng vòng khi đã khớp hết lệnh an toàn

Đóng nguyên vòng hiện tại theo giá thị trường, chỉ một vòng. Áp dụng khi máy đã khớp hết tất cả lệnh an toàn — lúc rủi ro/cháy cao nhất. Khớp khoảng mười mấy lệnh rồi hồi là lúc máy khỏe. Không nghe tư vấn mua thêm lúc đã khớp hết. Giữ tiền còn hơn kiếm tiền.

Nếu mọi mức mua an toàn đã khớp hết, kế hoạch trung bình giá ban đầu đã xong. Tiếp tục là cược mới.

## Hai lỗi hay gặp (DCA)

1. Tiền mỗi lệnh thấp hơn mức tối thiểu nền tảng. Cài cao hơn mức tối thiểu khoảng 3–5 lần.
2. Hết tiền trước khi khớp hết mức: bước giá xa + đòn bẩy cao + không ký quỹ. Sửa hướng: bước giá dưới 2% và ký quỹ đủ. Ký quỹ ít thì nền tảng có thể không cho khớp thêm lệnh gần vạch cháy — đừng tưởng máy còn DCA.

## Tạo lại máy / đảo chiều

Tạo lại: copy setting, chỉ nhập lại số tiền. Dùng khi máy đang hiệu quả. Lưới thường đòi số tiền tạo lớn nên lãi kép kiểu này dễ hơn với DCA. Khá rủi ro; vốn nhỏ thì được.

Đảo chiều (long thành short) cùng setting: hai máy lưới ngược nhau có thể cùng ăn hoặc cùng đổ — không giống hedge an toàn. Hơi khát bạc, không phải chặn rủi ro.

## Không có trong chương này

Không có tên sàn, không có tên nút của một app, không có copy bot.
