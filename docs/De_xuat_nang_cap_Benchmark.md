# BÁO CÁO ĐỀ XUẤT NÂNG CẤP KIẾN TRÚC HỆ THỐNG TÓM TẮT BỆNH ÁN LÂM SÀNG (CLIN-SUMM)
**Tác vụ:** Tối ưu hóa luồng RAG và Mở rộng năng lực xử lý bối cảnh y khoa  
**Tác giả:** Kỹ sư Phát triển Hệ thống AI  

---

## 1. ĐẶT VẤN ĐỀ & HẠN CHẾ CỦA KIẾN TRÚC HIỆN TẠI

Hệ thống `clin-summ` hiện tại đang sử dụng các mô hình ngôn ngữ dạng **Encoder-Decoder (Seq2Seq)** đời đầu, bao gồm `facebook/bart-large-cnn` và bộ các mô hình `google/pegasus` (các biến thể XSum, PubMed, CNN). Qua kết quả thực nghiệm diện rộng trên 200 bản ghi của tập dữ liệu `MultiClinSum`, kiến trúc này đã bộc lộ hai điểm nghẽn vật lý chí mạng:

### 1.1. Hiện tượng cắt cụt bối cảnh (Context Window Truncation)
* **Thực trạng:** Các mô hình BART và Pegasus có giới hạn cửa sổ ngữ cảnh nghiêm ngặt ở mức **1,024 tokens** (cho cả đầu vào và đầu ra). 
* **Hậu quả:** Khi hệ thống chuyển sang luồng **RAG Grounded** nâng cao, việc bổ sung các chỉ thị hệ thống phức tạp, danh sách sự thật ưu tiên (`[CITATION_FIRST_CLINICAL_FACTS]`), cùng 10–12 đoạn bằng chứng lâm sàng kèm Metadata từ Qdrant dễ dàng đẩy kích thước Prompt vượt ngưỡng 2,500 tokens. Thư viện xử lý buộc phải cắt cụt phần đuôi dữ liệu để vừa khít 1024 tokens. Điều này khiến thông tin Kế hoạch điều trị (`PLAN`) và Xét nghiệm (`DIAGNOSTICS`) nằm ở cuối Prompt bị xóa bỏ hoàn toàn trước khi mô hình kịp đọc.

### 1.2. Mâu thuẫn định dạng tiền huấn luyện (Pre-training Format Mismatch)
* **Thực trạng:** BART và Pegasus được tối ưu hóa bằng cách đọc một văn bản phẳng, có tính tuyến tính và liên kết ngữ pháp cao (như bài báo khoa học, tin tức báo chí). 
* **Hậu quả:** Cấu trúc Prompt của RAG y khoa mang tính chắp vá cao, đan xen nhiều ký hiệu mã hóa trích dẫn kỹ thuật (`[cit-1]`, `[cit-2]`) và nhãn phân mục (`[MEDICATIONS_FACTS]`). Định dạng phi tuyến tính này làm nhiễu cơ chế Attention (Chú ý) của các mô hình Seq2Seq cỡ nhỏ, dẫn đến việc tăng mạnh chỉ số **Critical Omission (Bỏ sót thông tin)** lên ngưỡng ~0.79 và làm giảm độ chính xác của dòng thời gian lâm sàng.

---

## 2. ĐỀ XUẤT KIẾN TRÚC MỚI: PHÂN TẦNG DECODER-ONLY TRÊN THIẾT BỊ CỤC BỘ (LOCAL COGNITIVE LAYER)

Để khắc phục triệt để các hạn chế trên mà vẫn đảm bảo tính độc lập dữ liệu, không rò rỉ thông tin y tế cá nhân (PHI), báo cáo đề xuất tích hợp thêm hai nhà cung cấp mô hình (Providers) thuộc thế hệ **Decoder-only (Causal LM)** có kích thước nhỏ gọn từ 1.5B đến 8B tham số:

1. **Qwen 2.5 (Trọng tâm: `Qwen2.5-1.5B-Instruct` và `Qwen2.5-3B-Instruct`)**
2. **Llama 3.2 (Trọng tâm: `Llama-3.2-3B-Instruct`)**

### 2.1. Các lợi thế công nghệ cốt lõi

#### A. Cửa sổ ngữ cảnh cực đại (128K Context Window)
Cả hai dòng mô hình Qwen 2.5 và Llama 3.2 đều hỗ trợ kiến trúc xử lý độ dài bối cảnh lên tới **128,000 tokens**. Khả năng này triệt tiêu hoàn toàn rủi ro thất thoát dữ liệu do cắt cụt bối cảnh. Hệ thống RAG có thể tự do làm giàu dữ liệu, nạp toàn bộ lịch sử bệnh án dài và sâu của bệnh nhân vào một lượt xử lý duy nhất.

#### B. Cơ chế Huấn luyện Tuân thủ Chỉ thị (Instruction-Tuning)
Thay vì chỉ học cách co ngắn văn bản, các mô hình Instruct thế hệ mới được tối ưu hóa để hiểu sâu sắc bối cảnh Prompt phức tạp. Mô hình phân biệt rõ ràng giữa lệnh điều hướng của hệ thống và dữ liệu lâm sàng thô. Do đó, khi đọc bảng Checklist cấu trúc `Citation-First Facts` do hệ thống chuẩn bị, mô hình sẽ tuân thủ nghiêm ngặt việc đối chiếu dữ kiện, giúp nâng cao chỉ số **Citation coverage** và hạ tỷ lệ thông tin vô căn cứ (**Unsupported claim rate**) về mức tiệm cận 0%.

#### C. Mật độ tri thức cao trên dung lượng nhỏ
* **Qwen 2.5:** Được huấn luyện trên tập dữ liệu khổng lồ 18 nghìn tỷ tokens (18T), giúp bản 1.5B/3B có khả năng hiểu cấu trúc văn bản hành chính và định dạng bảng biểu y khoa cực tốt.
* **Llama 3.2 3B:** Được Meta áp dụng các kỹ thuật nén tri thức (Pruning & Distillation) tiên tiến từ các phiên bản đàn anh (8B/70B), mang lại năng lực suy luận logic lâm sàng sâu sắc, hiểu rõ các thuật ngữ đồng nghĩa y khoa phức tạp mà không cần thực hiện fine-tuning tốn kém.

---

## 3. BẢNG SO SÁNH TỔNG HỢP KIẾN TRÚC HỆ THỐNG

| Tiêu chí so sánh | Kiến trúc Cũ (BART / Pegasus) | Kiến trúc Đề xuất mới (Qwen 2.5 / Llama 3.2) | Tác động trực tiếp tới Chỉ số Lâm sàng |
| :--- | :---: | :---: | :--- |
| **Dạng mạng Neural** | Encoder-Decoder (Seq2Seq) | Decoder-only (Causal LM) | Tăng khả năng tuân thủ cấu trúc Prompt phức tạp, chắp vá của RAG. |
| **Cửa sổ ngữ cảnh (Context)** | **1,024 tokens** | **128,000 tokens (128K)** | Triệt tiêu lỗi cắt cụt dữ liệu $\rightarrow$ **Giảm mạnh Critical Omission**. |
| **Kỹ thuật Huấn luyện** | Tóm tắt văn bản báo chí thuần túy | Instruction-Tuning (Lệnh/Phản hồi) | Tăng độ chính xác khi đối chiếu và giữ vững mã trích dẫn (`[cit-x]`). |
| **Khả năng chạy Local** | Nạp file trọng số gốc (Nặng, chiếm bộ nhớ) | Chạy qua Ollama API + Nén GGUF 4-bit | Đảm bảo tốc độ xử lý nhanh, không gây đơ máy khi chạy Benchmark tự động. |

---

## 4. GIẢI PHÁP TRIỂN KHAI VÀ KHẢ THI KỸ THUẬT (LOCAL DEPLOYMENT)

Để đảm bảo các mô hình thế hệ mới chạy mượt mà trên tài nguyên máy tính cá nhân trong quá trình quét qua vòng lặp kiểm thử 200 bản ghi, hệ thống sẽ chuyển dịch phương thức nạp mô hình từ việc gọi thư viện `transformers` thuần sang cơ chế **Inference Engine tối ưu hóa**:
1. **Lượng tử hóa 4-bit (4-bit Quantization):** Sử dụng các phiên bản mô hình đã được nén sang định dạng GGUF (`Q4_K_M`). Dung lượng mô hình giảm mạnh xuống còn ~1.2 GB (đối với bản 1.5B) và ~2.0 GB (đối với bản 3B), cho phép nạp trọn vẹn và giải phóng nhanh bộ nhớ RAM/VRAM.
2. **Tích hợp qua Ollama Service:** Các script Python (`run_rag_grounded_benchmark.py`) sẽ không trực tiếp load mô hình vào RAM của tiến trình Python. Thay vào đó, nó sẽ giao tiếp thông qua cổng API cục bộ do Ollama quản lý (`http://localhost:11434/v1`). Cơ chế chạy ngầm này tận dụng tối đa thư viện tăng tốc phần cứng của `llama.cpp`, đảm bảo thời gian sinh tóm tắt (Latency) tối ưu và không xảy ra hiện tượng treo máy/tràn bộ nhớ (OOM).

---

## 5. KẾT LUẬN & ĐỊNH HƯỚNG BÁO CÁO ĐỒ ÁN

Sự bổ sung và dịch chuyển kiến trúc sang các mô hình Decoder-only chạy cục bộ (Qwen 2.5 và Llama 3.2) không chỉ là một nâng cấp kỹ thuật, mà còn tạo nên một **câu chuyện nghiên cứu khoa học có chiều sâu cốt lõi** cho đồ án tốt nghiệp:

* **Giai đoạn Baseline:** Minh chứng các giới hạn vật lý kinh điển của thế hệ Seq2Seq cũ trong bài toán xử lý thông tin y tế đa nguồn.
* **Giai đoạn Tiến hóa Kiến trúc:** Khẳng định tính đúng đắn của việc kết hợp giữa **Kỹ thuật RAG cấu trúc (Advanced RAG Pipeline)** và **Năng lực suy luận bối cảnh lớn (Large Context Causal LM)** trên môi trường tính toán phân tán/cục bộ nhằm đạt độ an toàn y khoa tối cao (`Unsupported Claim Rate = 0.0000`).



Hiện tại hệ thống đang : 
[Bệnh án gốc (Source Note)]
       │
       ▼ (ClinicalChunker)
[Các đoạn văn bản ngắn (Chunks)] ──► Nhúng Vector (MiniLM) ──► Đẩy vào Qdrant Store
       │
       ├────────────────────────────────────────┐ (Flow 1.5 - Heuristic)
       ▼ (Flow RAG - 6 Section Queries)         ▼
[Tìm kiếm Vector (Top 3 Chunks/Section)]   [Tính điểm Clinical Salience]
       │                                        │ (Regex khớp từ khóa y khoa)
       ▼                                        ▼
[Tái xếp hạng cục bộ (Rerank)] ───────────► [Lọc & Cân bằng Hạn ngạch (Quota)]
                                                │ (Chọn tối đa 10-12 Chunks tốt nhất)
                                                ▼
                                   [Trích xuất Fact trước (Citation-First)]
                                                │ (Lấy câu chứa thông tin cốt lõi)
                                                ▼
                                   [Đóng gói Context chuyển cho BART/Pegasus]




1. Chiến lược Phân mảnh và Định vị Mục tiêu (Section-Aware Parsing)Thay vì tìm kiếm véc-tơ chung chung cho toàn bộ văn bản, bạn đang chia bài toán tìm kiếm thành 6 phân mục lâm sàng cốt lõi (DIAGNOSIS, MEDICATIONS, TIMELINE, ASSESSMENT, PLAN, DIAGNOSTICS).Mã nguồn xử lý: Hệ thống định nghĩa SECTION_QUERIES làm câu truy vấn nền và SECTION_PATTERNS (Regex) để quét nhanh từ khóa.Cải tiến truy vấn (build_source_aware_section_query): Bạn không dùng nhãn tham chiếu (Ground Truth) để tìm kiếm, mà trích xuất các thuật ngữ tần suất cao trực tiếp từ hồ sơ gốc để "làm giàu" (expand) câu lệnh truy vấn véc-tơ.2. Tầng Tái xếp hạng hỗn hợp tự chế (rerank_section_evidence)Hệ thống hiện tại chưa dùng một mô hình Re-ranker học máy (như Cohere hay BGE), nhưng bạn đã tự viết một hàm scoring lai khá sáng tạo:$$\text{Score} = \text{Vector Score} + (0.035 \times \text{Clinical Salience}) + \text{Section Bonus} - \text{Rank Penalty}$$Cơ chế: Thưởng điểm nếu chunk đó trùng phân mục với phân mục đang tìm (Section Bonus), thưởng dựa trên mật độ từ khóa y khoa (Clinical Salience), và phạt nhẹ các chunk nằm ở rìa kết quả của Qdrant (Rank Penalty).3. Giải pháp chống mất thông tin: Kỹ thuật Citation-First FactsĐây là điểm mấu chốt nhất trong mã nguồn của bạn nhằm giải quyết hiện tượng mô hình Seq2Seq (như BART) bỏ sót các chi tiết nhỏ tần suất thấp (Critical Omission).Cách chạy: Trước khi ném toàn bộ các chunk thô vào prompt cho AI đọc, hàm extract_citation_first_facts sẽ bóc tách các câu quan trọng nhất của từng mục (tối đa 2 facts/mục, không quá 280 ký tự) xếp lên đầu prompt thành một dạng Checklist có đính kèm mã Chunk ID (- (chunk_1) Patient has DM type 2).Mục tiêu: Ép tầng Decoder của mô hình phải nhìn thấy các dữ kiện sinh tử này đầu tiên để đưa vào bản tóm tắt.4. Cơ chế Cân bằng Context (select_balanced_evidence)Hệ thống khống chế nghiêm ngặt cửa sổ ngữ cảnh (max_context_chunks = 10 hoặc 12). Bạn chia đều hạn ngạch (SECTION_CHUNK_QUOTAS), mỗi phân mục y khoa chỉ được lấy tối đa 2 chunks tốt nhất. Nếu thiếu, hệ thống mới nhặt các chunk thừa (leftovers) có điểm cao nhất để bù vào. Điều này giúp ngăn chặn việc một phân mục quá dài lấn át các phân mục khác.── ĐÁG GIÁ: TẠI SAO PHƯƠNG ÁN NÀY VẪN LÀM CHỈ SỐ LÂM 