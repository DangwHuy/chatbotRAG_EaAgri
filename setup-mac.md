# Part 1. Clone the Repo

## 1. Cài đặt Git (nếu chưa có)

- Truy cập https://git-scm.com/downloads/mac 
- Cài đặt Homebrew.
- Open Terminal (Applications > Utilities > Terminal) dán

-   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` 
- Cài đặt Git `$ brew install git` 

## 2. Điều hướng đến thư mục dự án

Nếu bạn có một thư mục riêng cho các dự án, hãy điều hướng đến đó bằng lệnh cd: 

`cd ~/Documents/Projects`

Nếu chưa có thư mục dự án, hãy tạo một thư mục mới:

`mkdir ~/Documents/Projects`

## 3. Clone Repository

Nhập lệnh sau vào Terminal (trong thư mục Projects):

`git clone https://github.com/tam1511/llmprojects.git`

Lệnh này sẽ tạo một thư mục mới có tên llmprojects bên trong thư mục Projects và tải mã nguồn về.

Đi vào thư mục dự án: `cd llmprojects`

thư mục llmprojects sẽ là thư mục gốc của dự án

# Part 2. Install Anaconda environment

Mình sử dụng nền tảng Anaconda để thiết lập môi trường làm việc. Đây là một công cụ mạnh mẽ giúp tạo ra một môi trường Data Science hoàn chỉnh.

Lợi ích của Anaconda: ✅ Đảm bảo bạn sử dụng đúng phiên bản Python ✅ Tất cả các gói thư viện đều tương thích, ngay cả khi hệ thống của chúng ta khác nhau ✅ Ổn định và đáng tin cậy sau khi thiết lập xong

Lưu ý: Quá trình cài đặt có thể mất thời gian và Dung lượng ổ cứng yêu cầu khá lớn (5GB+)

Dù mất công ban đầu, nhưng Anaconda giúp bạn tránh được rất nhiều lỗi về môi trường sau này!

**Tuy nhiên, không nhất thiết phải sử dụng Anaconda. Bạn có thể chọn một phương pháp thay thế khác. Cách này nhanh hơn, đơn giản hơn, nhưng có thể không đảm bảo được tính tương thích cao như Anaconda.**

## 1. Tải và cài đặt Anaconda

Tải Anaconda từ: https://docs.anaconda.com/anaconda/install/mac-os/

Chạy trình cài đặt và làm theo hướng dẫn. Lưu ý rằng Anaconda chiếm vài GB dung lượng và quá trình cài đặt có thể mất thời gian.

## 2. Thiết lập môi trường

Mở Terminal mới (Applications > Utilities > Terminal)

Điều hướng đến "thư mục gốc của dự án" bằng lệnh:

`cd ~/Documents/Projects/llmprojects`

Sau đó, dùng lệnh `ls` để kiểm tra xem bạn có thể thấy các thư mục con hay không

Tiếp theo, tạo môi trường bằng lệnh:

`conda env create -f environment.yml`

Chờ trong vài phút để tất cả các gói được cài đặt – trong một số trường hợp, nếu bạn chưa sử dụng Anaconda trước đây, quá trình này có thể mất 20-30 phút, thậm chí lâu hơn tùy thuộc vào kết nối Internet của bạn. Nếu gặp bất cứ vấn đề gì hãy chuyển sang cách thay thế khác (miniconda hoặc virtual environment) 

Bây giờ, bạn đã xây dựng thành công một môi trường AI cách ly và chuyên dụng cho việc phát triển LLMs, chạy vector datastores và nhiều ứng dụng khác. Để kích hoạt môi trường này, hãy dùng lệnh:

`conda activate llms`

## 3. Bắt đầu với Vscode 

Nhập lênh `code .` để bắt đầu

# Cách thay thế Anaconda - Tạo Virtual Environment

**Mở Terminal trên macOS**

Đi tới Applications > Utilities > Terminal và mở Terminal. 

**Kiểm tra phiên bản Python**

Chạy lệnh sau để kiểm tra phiên bản Python bạn đang sử dụng: `python --version`

Lý tưởng nhất, bạn nên sử dụng Python 3.11 để đảm bảo đồng bộ hoàn toàn. Nếu không, cũng không sao, nhưng có thể cần quay lại bước này nếu gặp vấn đề về tương thích.

👉 Bạn có thể tải Python tại đây:
https://www.python.org/downloads/

**Di chuyển đến thư mục dự án**

Dùng lệnh `cd` để di chuyển đến thư mục gốc của dự án `cd C:\Users\YourUsername\Projects\llmprojects`

Sau đó, chạy: `ls` để kiểm tra xem bạn có thấy các thư mục con trong dự án hay không

**Tạo môi trường ảo**

Chạy lệnh sau để tạo một môi trường ảo mới: 

`python -m venv llms`

**Kích hoạt môi trường ảo**

`source llms/bin/activate`

Nếu thành công, bạn sẽ thấy (llms) xuất hiện trong dòng lệnh, báo hiệu rằng môi trường ảo đã được kích hoạt. 

Bạn cần cài đặt lại các thư viện cần dùng cho môi trường này!






