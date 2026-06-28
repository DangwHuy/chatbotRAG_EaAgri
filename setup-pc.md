# Part 1. Clone the Repo

### 1. Cài đặt Git (nếu chưa có)

Tải Git từ: https://git-scm.com/download/win

Chạy trình cài đặt và làm theo hướng dẫn, sử dụng tùy chọn mặc định (chỉ cần nhấn OK nhiều lần!)

### 2. Mở Command Prompt

Nhấn `Win + R`, gõ `cmd`, sau đó nhấn `Enter`

### 3. Điều hướng đến thư mục dự án

Nếu bạn có một thư mục riêng cho các dự án, hãy điều hướng đến đó bằng lệnh cd: 
`cd C:\Users\YourUsername\Projects`

Thay "YourUsername" bằng tên người dùng Windows thực tế của bạn. Nếu chưa có thư mục dự án, hãy tạo một thư mục mới: 
`mkdir C:\Users\YourUsername\Projects`

`cd C:\Users\YourUsername\Projects`

### 4. Clone Repository

Nhập lệnh sau vào Command Prompt (trong thư mục Projects):

`git clone https://github.com/tam1511/llmprojects.git`

Lệnh này sẽ tạo một thư mục mới có tên `llmprojects` bên trong thư mục `Projects` và tải mã nguồn về.

Đi vào thư mục dự án: `cd llmprojects`

thư mục `llmprojects` sẽ là thư mục gốc của dự án

# Part 2. Setup Environment

Mình sử dụng nền tảng Anaconda để thiết lập môi trường làm việc. Đây là một công cụ mạnh mẽ giúp tạo ra một môi trường Data Science hoàn chỉnh.

Lợi ích của Anaconda: ✅ Đảm bảo bạn sử dụng đúng phiên bản Python ✅ Tất cả các gói thư viện đều tương thích, ngay cả khi hệ thống của chúng ta khác nhau ✅ Ổn định và đáng tin cậy sau khi thiết lập xong

Lưu ý: Quá trình cài đặt có thể mất thời gian và Dung lượng ổ cứng yêu cầu khá lớn (5GB+)

Dù mất công ban đầu, nhưng Anaconda giúp bạn tránh được rất nhiều lỗi về môi trường sau này!

**Tuy nhiên, không nhất thiết phải sử dụng Anaconda. Bạn có thể chọn một phương pháp thay thế khác. Cách này nhanh hơn, đơn giản hơn, nhưng có thể không đảm bảo được tính tương thích cao như Anaconda.**

### 1. Tải và cài đặt Anaconda
Tải Anaconda từ: https://docs.anaconda.com/anaconda/install/windows/

Chạy trình cài đặt và làm theo hướng dẫn. Lưu ý rằng Anaconda chiếm vài GB dung lượng và quá trình cài đặt có thể mất thời gian.

### 2. Thiết lập môi trường

Mở Anaconda Prompt:

Tìm kiếm Anaconda Prompt trong Start Menu và mở nó.

Điều hướng đến thư mục gốc của dự án:

Nhập lệnh sau, thay YourUsername bằng tên thực của bạn: `cd C:\Users\YourUsername\Projects\llmprojects`

Sau đó, chạy: `dir` để kiểm tra xem bạn có thấy các thư mục con của dự án hay không

**Tạo môi trường trong Anaconda**

Chạy lệnh sau để tạo môi trường từ file `environment.yml`:

`conda env create -f environment.yml`

*Lưu ý:*

*Quá trình này có thể mất 20-30 phút, thậm chí lâu hơn nếu bạn chưa từng sử dụng Anaconda trước đó hoặc nếu mạng chậm. Nếu gặp bất cứ vấn đề gì hãy chuyển sang cách thay thế khác (miniconda hoặc virtual environment)*

### 3. Kích hoạt môi trường

Sau khi cài đặt hoàn tất, kích hoạt môi trường mới bằng lệnh: `conda activate llms`

Nếu thành công, bạn sẽ thấy (llms) xuất hiện trong dòng lệnh, báo hiệu rằng môi trường đã được kích hoạt. 

# Cách thay thế Anaconda - Tạo Virtual Environment

### 1. Mở Command Prompt

Nhấn `Win + R`, nhập `cmd`, rồi nhấn `Enter`

### 2. Kiểm tra phiên bản Python

Chạy lệnh sau để kiểm tra phiên bản Python bạn đang sử dụng:
`python --version`

Lý tưởng nhất, bạn nên sử dụng **Python 3.11** để đảm bảo đồng bộ hoàn toàn. Nếu không, cũng không sao, nhưng có thể cần quay lại bước này nếu gặp vấn đề về tương thích.

👉 Bạn có thể tải Python tại đây:
https://www.python.org/downloads/

### 3. Di chuyển đến thư mục dự án

Dùng lệnh `cd` để di chuyển đến thư mục gốc của dự án
`cd C:\Users\YourUsername\Projects\llmprojects`

Sau đó, chạy: `dir` để kiểm tra xem bạn có thấy các thư mục con trong dự án hay không

### 4. Tạo môi trường ảo

Chạy lệnh sau để tạo một môi trường ảo mới: `python -m venv llms`

**Kích hoạt môi trường ảo**

`llms\Scripts\activate`

Nếu thành công, bạn sẽ thấy (llms) xuất hiện trong dòng lệnh, báo hiệu rằng môi trường ảo đã được kích hoạt. 

Bạn cần cài đặt lại các thư viện cần dùng cho môi trường này









