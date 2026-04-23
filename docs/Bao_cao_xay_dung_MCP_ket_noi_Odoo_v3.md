# BÁO CÁO XÂY DỰNG MCP KẾT NỐI ODOO

Project: MCP Odoo

Ngày rà soát: 23/04/2026

Mục tiêu: xây dựng MCP server làm lớp trung gian chuẩn hóa giữa HTTP client hoặc AI agent và hệ thống Odoo thông qua XML-RPC, đồng thời bổ sung khả năng quan sát vận hành, kiểm soát tốc độ gọi và resource ngữ nghĩa cho các luồng HR và finance.

## Tóm tắt điều hành

Ở trạng thái hiện tại, project không còn chỉ là một MCP wrapper mỏng cho Odoo. Hệ thống đã phát triển thành một MCP server hướng HTTP với các lớp chức năng rõ ràng:

- transport streamable HTTP tại endpoint /mcp;
- xác thực Basic Auth theo từng request và xác thực trực tiếp với Odoo;
- Odoo XML-RPC client có timeout, retry, redirect handling và phân loại lỗi;
- rate limit tạm thời theo user và theo surface gọi;
- audit log JSONL cho tool call và các resource đọc Odoo;
- hai MCP tool thực tế là odoo_execute_method và hrm_export_payroll_table;
- nhóm resource generic, recipe và semantic resource cho HR companies, departments, payroll runs, finance journals;
- hỗ trợ HTTPS native ngay trên listener của MCP server.

Nói cách khác, phiên bản hiện tại đã có thêm lớp reliability và observability, đồng thời có bề mặt resource giàu ngữ nghĩa hơn đáng kể so với giai đoạn chỉ tập trung vào payroll export.

## 1. Phạm vi dự án hiện tại

Project hiện cung cấp một Odoo MCP Server dựa trên FastMCP. Thành phần runtime chính gồm:

- FastMCP application với streamable_http_path là /mcp và stateless_http bằng true;
- Starlette app làm lớp HTTP thực thi middleware xác thực;
- Odoo XML-RPC client dùng cho authenticate, execute_kw, search_read, read và fields_get;
- tool surface tối giản nhưng đủ linh hoạt cho gọi method tổng quát và payroll export;
- resource surface gồm cả generic resource và semantic resource để AI client hiểu domain tốt hơn.

Phạm vi hiện tại vẫn thiên về HRM, đặc biệt là payroll, nhưng project đã có thêm semantic resource cho finance journals và lớp hạ tầng đủ tổng quát để mở rộng tiếp. Tuy vậy, toolset đang expose ra ngoài vẫn mới có một nhóm duy nhất là hrm.

## 2. Kiến trúc tổng thể

Kiến trúc triển khai hiện tại gồm ba lớp chính:

- Client hoặc AI agent gửi request MCP qua HTTP tới /mcp;
- MCP server xác thực, gọi tool hoặc đọc resource tương ứng;
- Odoo xử lý nghiệp vụ và dữ liệu qua XML-RPC.

Luồng xử lý chuẩn:

- HTTP client gọi POST /mcp kèm Authorization theo Basic Auth;
- middleware tách username và password rồi tạo OdooClient bằng đúng thông tin đó;
- OdooClient authenticate với Odoo qua endpoint /xmlrpc/2/common;
- khi xác thực thành công, request được gắn state gồm odoo_client, odoo_username, odoo_uid;
- tool hoặc resource dùng client đã gắn vào context để gọi Odoo;
- kết quả được chuẩn hóa lại thành MCP tool response hoặc JSON resource.

Các route public hiện có:

- GET /healthz
- GET /mcp/health
- GET /mcp/config
- POST /mcp

Trong đó /mcp/config hiện không chỉ mô tả auth và toolset mà còn trả ra cấu hình observability như audit log và rate limit.

## 3. Transport, xác thực và bảo mật

### 3.1. Những gì đã triển khai trong code

- Server dùng streamable HTTP transport tại /mcp.
- Middleware OdooBasicAuthMiddleware xác thực từng request nghiệp vụ với Odoo.
- Các route /healthz, /mcp/health, /mcp/config được bỏ qua auth để phục vụ health check và inspector.
- Preflight OPTIONS cũng được bỏ qua xác thực.
- CORS hiện mở cho http://localhost:6274 và http://127.0.0.1:6274 để phục vụ inspector cục bộ.
- Listener của MCP server có thể chạy HTTPS native nếu khai báo MCP_SSL_CERTFILE và MCP_SSL_KEYFILE.
- Cấu hình Odoo hỗ trợ bật hoặc tắt verify SSL thông qua ODOO_VERIFY_SSL.

### 3.2. Cách xác thực hoạt động

Server không dùng shared service account ở tầng MCP. Thay vào đó:

- mỗi request gửi username và password hoặc API key qua Basic Auth;
- middleware dùng chính cặp thông tin đó để authenticate với Odoo;
- nếu Odoo hỗ trợ API key thì key nằm ở vị trí password;
- quyền thực thi của tool và resource vì vậy bám theo người dùng Odoo thực tế.

Đây là điểm mạnh quan trọng của thiết kế hiện tại vì nó giữ nguyên mô hình phân quyền của Odoo thay vì tạo thêm lớp ủy quyền riêng ở giữa.

## 4. Odoo XML-RPC client, retry và phân loại lỗi

Một thay đổi lớn của project là lớp Odoo client nay đã có cấu trúc vận hành rõ hơn.

### 4.1. Retry policy

OdooClient hiện dùng RetryPolicy với các tham số:

- timeout_seconds;
- max_attempts;
- backoff_seconds;
- max_backoff_seconds;
- max_redirects.

RedirectTransport xử lý:

- timeout;
- redirect HTTP 301, 302, 303, 307, 308;
- retry cho các HTTP status retryable như 408, 429, 500, 502, 503, 504;
- retry cho một số lỗi network và OSError thường gặp;
- outbound proxy nếu có biến môi trường HTTP_PROXY.

### 4.2. Phân loại lỗi ổn định

Project hiện đã có taxonomy lỗi riêng cho Odoo, gồm các nhóm chính:

- configuration_error;
- authentication_error;
- authorization_error;
- timeout;
- connection_error;
- protocol_error;
- remote_error;
- rate_limit;
- application_error ở nhánh fault từ Odoo;
- upstream_rate_limit trong trường hợp Odoo hoặc upstream trả HTTP 429.

Lợi ích của lớp này là tool và resource không chỉ trả chuỗi lỗi thô mà còn trả:

- error;
- error_category;
- retryable;
- error_details khi có thể.

Điều này rất quan trọng với AI agent vì nó cho phép phân biệt lỗi nên retry với lỗi cần đổi tham số, đổi user hoặc xin thêm quyền.

## 5. Tool surface hiện có

Server hiện chỉ expose hai tool:

- odoo_execute_method
- hrm_export_payroll_table

### 5.1. Tool odoo_execute_method

Đây là tool tổng quát nhất của project. Tool nhận:

- model;
- method;
- args;
- kwargs.

Ý nghĩa thực tế:

- dùng khi caller đã biết chính xác model và method;
- dùng khi agent muốn tự phân rã một workflow lớn thành chuỗi lời gọi Odoo cụ thể;
- dùng như lower-level primitive cho các workflow đặc thù.

Tool này hiện đã được bọc bằng lớp execute_observed_call, nên mỗi lần gọi:

- bị kiểm tra rate limit;
- được audit log;
- trả về rate_limit metadata;
- dùng error taxonomy ổn định nếu Odoo trả lỗi.

### 5.2. Tool hrm_export_payroll_table

Đây là convenience wrapper cho luồng export bảng lương. Tool hỗ trợ hai cách gọi:

- truyền trực tiếp run_id nếu đã biết batch payroll;
- hoặc truyền company_id cùng stage để server tự resolve batch.

Các điểm quan trọng của implementation hiện tại:

- stage được parse theo các dạng như 2026-03, 03/2026, thang 3 nam 2026;
- server ưu tiên resolve payroll run theo company_id cộng khoảng ngày date_start và date_end;
- nếu model không có đủ field ngày, code fallback sang tìm theo name ilike;
- nếu có nhiều batch phù hợp thì trả lỗi multiple_matches thay vì đoán.

Về đầu ra:

- hàm business helper export_payroll_table tạo payload kiểu client_payload;
- nhưng MCP tool hrm_export_payroll_table mặc định nâng đầu ra thành embedded MCP file resource;
- server vẫn đồng thời lưu một bản sao file ở server side dưới data/export;
- include_file_content cho phép giữ lại base64 trong structured content;
- return_file_resource điều khiển việc có nhúng resource file vào content hay không.

Tool này vẫn là wrapper đặc thù cho payroll, còn nếu agent muốn kiểm soát chi tiết từng bước thì vẫn nên dùng odoo_execute_method.

## 6. Resource surface hiện có

Một thay đổi đáng chú ý là resource layer hiện đã phong phú hơn nhiều.

### 6.1. Generic resource

Nhóm resource generic gồm:

- odoo://server/info
- odoo://models
- odoo://models/hr.payslip.run/fields
- odoo://models/res.company/fields
- odoo://models/hr.department/fields
- odoo://models/account.journal/fields
- odoo://models/{model}/fields
- odoo://records/{model}/{record_id}

Nhóm này phục vụ các nhu cầu:

- đọc metadata hệ thống;
- khám phá model khả dụng;
- lấy schema field;
- đọc một record cụ thể.

### 6.2. Recipe resource

Nhóm recipe hiện có:

- odoo://guides/execute-method-recipes
- odoo://recipes/payroll-export/company-month

Đây là resource tĩnh, dùng để hướng dẫn AI client cách chuyển một yêu cầu tự nhiên như xuất bảng lương tháng 3/2026 của công ty A thành chuỗi lời gọi:

- res.company.search_read
- hr.payslip.run.search_read
- hr.payslip.run.export_xlsx

### 6.3. Semantic resource

Project giờ đã có semantic resource cho hai domain chính là HR và finance:

- odoo://domains/hr/companies
- odoo://domains/hr/companies/{company_id}
- odoo://domains/hr/departments
- odoo://domains/hr/departments/{department_id}
- odoo://domains/hr/payroll/runs
- odoo://domains/hr/payroll/runs/{run_id}
- odoo://domains/hr/payroll/company/{company_id}/period/{year}/{month}
- odoo://domains/finance/journals
- odoo://domains/finance/journals/{journal_id}

Các semantic resource này không đơn thuần phản chiếu toàn bộ model Odoo. Chúng chọn sẵn một bộ field business-friendly ổn định hơn, ví dụ:

- company dùng các field như id, name, currency_id, partner_id;
- department dùng id, name, company_id, parent_id, manager_id;
- payroll run dùng id, name, company_id, date_start, date_end, state;
- journal dùng id, name, code, type, company_id, active.

Một chi tiết triển khai quan trọng là server không giả định mọi field đều luôn tồn tại. Trước khi đọc dữ liệu, resource sẽ gọi fields_get rồi lấy giao của curated field set với field thực sự có trong model. Nhờ vậy semantic resource mềm dẻo hơn khi schema Odoo khác nhau giữa môi trường.

## 7. Observability và kiểm soát vận hành

Đây là phần mới và có giá trị thực tế nhất trong project hiện tại.

### 7.1. Rate limiting

Server hiện dùng InMemoryRateLimiter với cấu hình:

- bật tắt bằng MCP_RATE_LIMIT_ENABLED;
- giới hạn số lần gọi bằng MCP_RATE_LIMIT_MAX_CALLS;
- cửa sổ thời gian bằng MCP_RATE_LIMIT_WINDOW_SECONDS.

Key của rate limit là:

- user;
- surface_name.

Điều đó có nghĩa là cùng một người dùng có quota riêng cho từng tool hoặc resource Odoo-backed. Đây là limiter tạm thời, chạy trong memory của process hiện tại, chưa phải rate limit phân tán hay production-grade.

### 7.2. Audit log JSONL

Mỗi lần gọi tool hoặc resource Odoo-backed sẽ ghi audit event vào file JSONL. Đường dẫn mặc định là:

- logs/odoo_audit.jsonl

Audit event hiện lưu các thông tin chính:

- timestamp và finished_at;
- duration_ms;
- surface và surface_name;
- user;
- model và method;
- status;
- success;
- error và error_category nếu có;
- retryable nếu có;
- export metadata như file_name, file_path, file_type, file_size_bytes, run_id, company_id, stage, page, records_per_page, delivery.

Điểm cần mô tả chính xác là lớp execute_observed_call hiện đang bao tool và các resource có truy cập Odoo. Hai recipe resource tĩnh không đi qua Odoo nên không cần audit theo kiểu này.

### 7.3. Logging runtime

run_server.py hiện cấu hình:

- log console ở mức INFO;
- log file theo timestamp trong thư mục logs;
- ẩn giá trị các biến môi trường có chứa PASSWORD khi in ra log khởi động.

## 8. Cấu hình và triển khai

Project hiện có hai file mẫu cấu hình:

- .env.example
- odoo_config.json.example

Nhóm cấu hình chính:

- Odoo connection: ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD;
- reliability: ODOO_TIMEOUT, ODOO_RETRY_ATTEMPTS, ODOO_RETRY_BACKOFF_SECONDS, ODOO_RETRY_BACKOFF_MAX_SECONDS, ODOO_MAX_REDIRECTS, ODOO_VERIFY_SSL;
- MCP listener: MCP_HOST, MCP_PORT, MCP_LOG_LEVEL, MCP_TOOLSETS;
- observability: MCP_RATE_LIMIT_ENABLED, MCP_RATE_LIMIT_MAX_CALLS, MCP_RATE_LIMIT_WINDOW_SECONDS, MCP_AUDIT_LOG_PATH;
- native HTTPS: MCP_SSL_CERTFILE, MCP_SSL_KEYFILE, MCP_SSL_KEYFILE_PASSWORD.

Một điểm cần ghi rõ trong báo cáo là MCP_TOOLSETS hiện chỉ chấp nhận:

- hrm;
- all hoặc dấu * nhưng vẫn resolve về hrm.

Nói cách khác, repo hiện chưa có multi-toolset theo nghĩa nhiều nhóm tool nghiệp vụ độc lập cùng được expose.

## 9. Artefact hỗ trợ trong repo

Ngoài code runtime, repo hiện còn có các artefact hỗ trợ phân tích và mapping:

- docs/tool_catalog.md mô tả cách chọn tool và semantic resource;
- data/diagrams chứa sơ đồ hoặc báo cáo phân tích model;
- data/mappings chứa mapping cột Excel cho dữ liệu payroll.

Các artefact này hữu ích cho việc hiểu domain và chuẩn hóa export payroll. Tuy nhiên, cần phân biệt rõ:

- chúng là tài liệu hỗ trợ hoặc dữ liệu phân tích;
- không phải toàn bộ đều là bề mặt runtime đang được MCP server expose;
- một số file phân tích trong data có tính lịch sử hoặc generated, nên không nên mô tả chúng như module runtime hiện hành.

## 10. Cấu trúc mã nguồn hiện tại

Cấu trúc hợp lý để mô tả trong báo cáo là:

- run_server.py: entry point khởi động server và cấu hình logging;
- src/odoo_mcp/server/: transport, auth, Odoo client, errors, observability, audit, rate limit;
- src/odoo_mcp/mcp/: app FastMCP, tool registry, tool implementation, resource implementation, recipe template;
- tests/: test cho client, auth, routes, toolsets, tools, resources, observability;
- docs/: tài liệu công cụ và báo cáo;
- data/: dữ liệu mapping và artefact phân tích hỗ trợ.

Cách tách này phản ánh tương đối tốt kiến trúc thực của project: lớp server và vận hành được tách khỏi lớp MCP surface.

## 11. Trạng thái kiểm thử

Tại thời điểm rà soát ngày 23/04/2026, test suite chạy thành công với kết quả:

- 40 passed

Các nhóm test đang bao phủ:

- HTTP/TLS config;
- Basic Auth middleware;
- tool registration và tool descriptions;
- resource registration và template URI;
- observability gồm audit log và rate limit;
- retry và error classification ở Odoo client.

Điều này cho thấy project hiện đã có lớp kiểm thử khá tốt cho bề mặt public và các hành vi vận hành cốt lõi.

## 12. Đánh giá hiện trạng

### 12.1. Điểm mạnh

- Kiến trúc rõ ràng, tách transport, client, tool và resource.
- Giữ nguyên mô hình phân quyền của Odoo nhờ auth theo từng request.
- Có retry, timeout, redirect handling và phân loại lỗi rõ ràng.
- Có rate limit và audit log ở mức đủ dùng cho giai đoạn hiện tại.
- Có semantic resource giúp AI client làm việc theo domain thay vì chỉ theo model kỹ thuật.
- Có payroll export wrapper hỗ trợ giao file dưới dạng embedded MCP resource.

### 12.2. Giới hạn hiện tại

- Toolset công khai vẫn chỉ có hrm.
- Tool odoo_execute_method chưa có method allowlist hoặc policy engine.
- Rate limiting hiện chỉ là in-memory trong một process.
- Audit log đang ghi ra local JSONL file, chưa có pipeline tập trung.
- Phạm vi semantic resource mới dừng ở một số entity HR và finance cơ bản.
- Repo có artefact dữ liệu hỗ trợ nhưng chưa được chuẩn hóa thành một bộ tài liệu runtime thống nhất.

## 13. Kết luận

Phiên bản hiện tại của MCP Odoo đã tiến thêm một bước rõ rệt so với giai đoạn chỉ mô tả kết nối Odoo và export bảng lương. Hệ thống giờ có:

- bề mặt tool tối giản nhưng thực dụng;
- resource generic cộng semantic resource có định hướng domain;
- lớp reliability ở Odoo client;
- lớp observability ở mức tool và Odoo-backed resource;
- khả năng vận hành thực tế tốt hơn nhờ audit log, rate limit và HTTPS native.

Mô tả phù hợp nhất cho project ở thời điểm này là: một Odoo MCP server thiên về HRM nhưng đã có thêm hạ tầng vận hành và semantic resource đủ rõ để làm nền cho các mở rộng tiếp theo. Đây chưa phải nền tảng multi-domain production hoàn chỉnh, nhưng đã vượt xa một bản proof of concept đơn thuần.

## Phụ lục A. Danh sách endpoint, tool và resource chính

Endpoint:

- GET /healthz
- GET /mcp/health
- GET /mcp/config
- POST /mcp

Tool:

- odoo_execute_method
- hrm_export_payroll_table

Resource generic:

- odoo://server/info
- odoo://models
- odoo://models/{model}/fields
- odoo://records/{model}/{record_id}

Recipe resource:

- odoo://guides/execute-method-recipes
- odoo://recipes/payroll-export/company-month

Semantic resource:

- odoo://domains/hr/companies
- odoo://domains/hr/companies/{company_id}
- odoo://domains/hr/departments
- odoo://domains/hr/departments/{department_id}
- odoo://domains/hr/payroll/runs
- odoo://domains/hr/payroll/runs/{run_id}
- odoo://domains/hr/payroll/company/{company_id}/period/{year}/{month}
- odoo://domains/finance/journals
- odoo://domains/finance/journals/{journal_id}

## Phụ lục B. Các biến môi trường quan trọng

- ODOO_URL
- ODOO_DB
- ODOO_USERNAME
- ODOO_PASSWORD
- ODOO_TIMEOUT
- ODOO_RETRY_ATTEMPTS
- ODOO_RETRY_BACKOFF_SECONDS
- ODOO_RETRY_BACKOFF_MAX_SECONDS
- ODOO_MAX_REDIRECTS
- ODOO_VERIFY_SSL
- MCP_HOST
- MCP_PORT
- MCP_LOG_LEVEL
- MCP_TOOLSETS
- MCP_RATE_LIMIT_ENABLED
- MCP_RATE_LIMIT_MAX_CALLS
- MCP_RATE_LIMIT_WINDOW_SECONDS
- MCP_AUDIT_LOG_PATH
- MCP_SSL_CERTFILE
- MCP_SSL_KEYFILE
- MCP_SSL_KEYFILE_PASSWORD
