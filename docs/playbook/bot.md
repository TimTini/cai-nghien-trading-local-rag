# Bot lưới và bot DCA (cách máy chạy)

Kiến thức về **cơ chế máy**. Không có tên sàn. Không kêu mở tài khoản. Máy không bảo đảm lãi. Nhận định sai hướng vẫn mất hết số đã bỏ vào con bot đó.

Số ví dụ lúc dạy là thói quen demo, **không phải chén thánh**.

## Bot lưới là gì

Bot lưới kê sẵn nhiều mức mua và bán trong **một khoảng giá**. Giá dao động trong khoảng thì máy khớp từng nhịp nhỏ. Không cần bắt đúng một điểm đỉnh hay đáy. Không dùng như all-in một điểm.

Bot không thay nhận định hướng. Máy giải tâm lý “không vào thì tiếc, vào rồi thì run” và chốt giúp vì người hay quên chốt lãi — chứ ít ai quên cắt lỗ.

Lưới sống nhờ giá **đi hai chiều** trong khoảng đã kê. Coin “nóng” chạy một mạch, hoặc đứng im không nhịp, thì giả định gãy — không phải vì chưa “top”.

## Lưới không đòn bẩy và lưới có đòn bẩy

Cùng một khoảng giá, số lần giá đi qua các ô (tick) càng nhiều thì máy ăn càng nhiều vòng. Ưu tiên đồng có nhịp và người mua-bán. Đồng nến đứng thì lưới gần như không ra lãi.

Lưới **không đòn bẩy** (kiểu giữ hàng giao ngay): dễ nắm cơ bản, hiệu quả thường kém lưới **có đòn bẩy** vì không nhân biên độ. Không đòn bẩy thì hold được thì đỡ cháy kiểu ký quỹ — đó là đổi khác rủi ro, không phải “an toàn = lãi”.

Lưới có đòn bẩy: quá ít ô (khoảng 10) thì một cây nến dài có thể chỉ khớp vài lệnh, rất lâu mới khớp. Lúc dạy hay để khoảng 100 ô, đòn bẩy 20, biên mỗi ô khoảng 8–12% với đồng biến động cao — **thói quen demo**, không bắt buộc mọi cặp.

Người mới tập lúc dạy hay chọn đồng giá nhỏ (nhiều số 0 sau phẩy) để số tiền tạo máy rẻ. Rẻ không có nghĩa ít rủi ro: đòn bẩy vẫn cháy hết số đã gắn.

## Chia ô: đều theo tiền hay theo phần trăm

- Đều theo **khoảng giá**: càng gần mép / giá càng giảm thì tiền vào mỗi ô có thể lớn hơn.
- Đều theo **phần trăm**: mỗi ô một khoảng % gần đều.

Lúc dạy thường chọn đều theo tiền. Hai cách không khác nhau quá nhiều; người mới không cần ám ảnh phải chọn đúng một loại.

## Khoảng giá, bắt đầu, ra ngoài khoảng

Khoảng đã chọn là một phần của máy. Khi tạo: nhập giá cao nhất mình nghĩ có thể lên và giá thấp nhất có thể về — máy chỉ chạy trong vùng đó. Lúc tạo, máy thường mua trước một phần để có hàng bán phía trên, giữ phần còn lại nếu giá xuống.

Kéo khoảng theo giá đang chạy là chiến lược khác, không còn lưới ban đầu.

Điều kiện bắt đầu: chạy ngay, hoặc hẹn giá thấp hơn (giống lệnh chờ). Có chỉ báo RSI trên một số máy; lúc dạy **không dùng**.

Khi giá chạy ra ngoài khoảng: máy tạm dừng. Lệnh còn sót được gồng như lệnh thường, có thể đóng tay. Bình thường, không phải máy hỏng. Phần sót vẫn mang **rủi ro theo hướng** giá đang đi.

## Hướng của lưới so với giá đang đứng

Hướng máy phụ thuộc khoảng đặt so với giá hiện tại. Muốn phía trên còn ô khi giá chạy lên thì khoảng phải phủ cao hơn giá đang đứng. Đặt sát giá hiện tại rồi giá chạy ngược mà không còn ô thì gồng khó.

Lãi khi giá về lại chỗ bắt đầu: máy vẫn có thể đã khớp vài nhịp trong lưới — gồng tay gần như không làm được việc này. Ngoại lệ: lãi lúc về entry không có nghĩa máy bất tử. Đừng nội suy một ngày lãi thành lãi kép cả tháng.

## Bot DCA khác bot lưới chỗ nào

Bot lưới: mua nhiều điểm, bán nhiều điểm. Bot DCA: mua ở nhiều điểm, bán **một điểm**. Chạm đường mua thì mua; khi giá trung bình sau các lệnh đã khớp tăng đủ % đã chọn thì chốt hết — đó là một vòng. Sau mỗi lần chốt hết, lưới mua dựng lại quanh giá hiện tại.

## DCA đồng nào thì hợp, đồng nào thì không

DCA theo thời gian: chia nhỏ mua theo ngày/tuần/tháng. Lúc dạy: với Bitcoin, khi đã giảm quá 50% từ đỉnh thì mới bắt đầu mua đều. Chỉ hợp đồng có tăng trưởng lâu dài và đỉnh mùa này còn có cửa cao hơn đỉnh mùa trước — lúc dạy nêu Bitcoin, ETH, SOL, BNB. Không nêu tên sàn.

Không DCA dài hạn alt mỏng: sau một mùa dễ mất hút, khó về bờ; alt loại đó chỉ lướt, không trung bình giá dài.

Đây là cách **đọc loại đồng**, không phải danh sách “mua hôm nay”.

## DCA lúc đang lỗ / lúc đang lãi

- Lúc đang lỗ, nhồi thêm để kéo giá vốn xuống: rủi ro cao, máy có đòn bẩy hay cháy. Không phải cách cứu lệnh.
- Lúc đã lãi, lấy lãi nhồi tiếp: số lãi nhìn to nhanh, vạch cháy có thể bị kéo. Lúc dạy chỉ minh họa số nhỏ, không dám số lớn. Không muốn học viên áp dụng nhiều.

Mọi DCA phải có điểm cắt trước. Không cắt rồi bơm tiền.

## Thông số máy DCA — ý nghĩa, không phải chén thánh

Lúc dạy hay nói (demo):

- Bước giá nên nhỏ hơn 2% (mặc định lúc dạy 0,5%). Lớn hơn 2% thì cả ngày mới khớp 1–2 lệnh.
- Chốt lời mỗi vòng: 0,4–0,7%. Cao hơn 0,7% dễ kẹt máy; thấp hơn 0,4% thì phí cắn nhiều. Demo 1–2% chỉ để nhìn.
- Đòn bẩy: cộng đồng hay x20; người mới x5, quen rồi mới x20. Vốn nhỏ: x10 trở xuống. Không có mức “không cháy”.
- Hệ số nhân bước giá: nên nhỏ hơn 1 (hay dùng 0,9–0,99, thường 0,97) để giá càng rẻ mua càng nhiều. =1 thì lưới đều. >1 dày đầu thưa dưới — sai nguyên tắc lúc dạy.
- Hệ số nhân tiền: nên cao hơn 1 một chút (1,0x–1,09, ví dụ 1,05). <1 thì càng xuống mua càng ít — sai. 1,1–1,2 làm tiền tạo máy nổ theo cấp số nhân.
- Số lệnh an toàn lúc dạy: 16 ngắn hạn, 26 trung hạn (hay cài), 36 dài hạn. Giảm số lệnh thì tăng bước giá; tăng số lệnh thì giảm bước giá.
- Bước giá / % chốt / số ô / số tiền tạo: nhiều máy **không sửa được** sau khi tạo. Ký quỹ, tái đầu tư, điều kiện dừng thì sửa được.

## Hết tiền trước khi khớp hết mức

Đòn bẩy cao hay bị cháy trước khi khớp hết lệnh an toàn phía dưới. Đòn bẩy thấp hơn kéo vạch cháy ra ngoài khoảng lưới — vốn bỏ ra nhiều hơn, dùng để thực hành.

Muốn ít tiền + lãi nhiều + đòn bẩy cao thì bắt buộc ký quỹ thêm, không chỉ dựa tiền tạo máy. Ký quỹ thêm rồi cháy thì mất cả phần thêm.

## Long DCA, short thì lưới, máy trung lập

Bot DCA cùng một hướng (thường long) hợp khi không chắc điểm mua. Short khó hơn; lúc dạy short bằng bot lưới.

Điểm mạnh: đánh ngược xu hướng vẫn có lãi nếu nhịp giảm có hồi. Giảm một mạch không hồi thì cháy hoặc dính cắt lỗ. Máy không phải chén thánh.

Tuổi thọ lúc dạy: sống khoảng 3 tháng là có thể gọi thành công. Ít máy chạy được lâu như vậy. Thanh khoản yếu thì DCA không sống lâu — vẫn phải hiểu cách máy chạy.

Máy hai chiều / trung lập: không gắn sẵn long hay short. Giá lên đánh một phía, giá xuống đánh phía kia. Tốn vốn hơn máy một chiều. Dùng khi thị trường sập sâu rồi đi ngang / tích lũy, thanh khoản yếu. Không dùng nếu không chấp nhận đánh ngược chiều, hoặc khi giá đang chạy một mạch. Không có “bật máy này vào tháng X”.

## Trước khi tạo: vẽ rủi ro trên đồ thị

Thứ tự lúc dạy (nguyên tắc, không phải menu một sàn):

1. Xác định lực xả nhiều nhất không hồi trên khung từ H4 trở lên (không đo H1).
2. Vẽ trên đồ thị điểm cháy / thanh lý mình chấp nhận.
3. Xác định hỗ trợ gần nhất để rải lệnh DCA.
4. Rải tới vạch hỗ trợ bằng bộ ba: bước giá + lệnh an toàn + nhân bước giá.
5. Nhập hết thông số còn lại ra số tiền tạo máy và vạch cháy.
6. Đo từ vạch cháy tới vạch nhịp giảm sâu nhất rồi tính ký quỹ.

Chưa vạch rủi ro trên đồ thị thì chưa tạo. Máy không thay view.

## Đọc số, dừng, sửa

Xem chương **Hậu kỳ bot**. Tóm tắt: nhìn tiền lãi-lỗ thật, không nhìn % chart; tách túi; sửa giữa chừng là máy khác; khớp hết mức an toàn = kế hoạch cũ đã xong.

## Không có trong chương này

Không có tên sàn. Không có copy bot / hoa hồng. Không có “mở tài khoản tại…”.
