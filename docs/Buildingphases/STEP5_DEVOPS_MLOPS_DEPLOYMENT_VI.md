# BƯỚC 5 - DevOps / MLOps Deployment and Monitoring

## Architecture Logic

```text
Clinician Browser / HIS Gateway
          |
          v
Kubernetes Service -> FastAPI Pods (HPA 2..10 replicas)
                         |        |           |
                         |        |           +--> MLflow Tracking Server
                         |        |                 latency / tokens / safety flags
                         |        |
                         |        +--> ONNX Runtime Execution Provider
                         |             Intel OpenVINO or NVIDIA CUDA
                         |
                         +--> Qdrant Server Cluster
                              shared vector store, not local pod disk
```

## Runtime Strategy

| Runtime | Image build | ONNX provider | K8s use case |
| --- | --- | --- | --- |
| CPU baseline | `Dockerfile --build-arg ORT_FLAVOR=cpu` | `CPUExecutionProvider` | Development/small sandbox |
| Intel optimized | `Dockerfile --build-arg ORT_FLAVOR=intel` | `OpenVINOExecutionProvider` | CPU/Intel edge or hospital cluster |
| NVIDIA GPU | `Dockerfile.nvidia` | `CUDAExecutionProvider` | GPU node pool for high throughput |

FastEmbed đã được cấu hình để nhận `RAG_ORT_EXECUTION_PROVIDER`, nhờ đó
embedding ONNX thực sự chọn execution provider tương ứng image.

## Docker

### CPU

```powershell
docker build -t clinical-summarizer:cpu-v0.1.0 --build-arg ORT_FLAVOR=cpu .
```

### Intel OpenVINO

```powershell
docker build -t clinical-summarizer:intel-v0.1.0 --build-arg ORT_FLAVOR=intel .
```

Chạy thử image Intel:

```powershell
docker run --rm -p 8080:8080 `
  -e RAG_ENVIRONMENT=production `
  -e RAG_EMBEDDING_PROVIDER=fastembed `
  -e RAG_ORT_EXECUTION_PROVIDER=OpenVINOExecutionProvider `
  -e RAG_QDRANT_URL=http://host.docker.internal:6333 `
  clinical-summarizer:intel-v0.1.0
```

### NVIDIA CUDA

```powershell
docker build -f Dockerfile.nvidia -t clinical-summarizer:nvidia-v0.1.0 .
docker run --rm --gpus all -p 8080:8080 `
  -e RAG_ENVIRONMENT=production `
  -e RAG_EMBEDDING_PROVIDER=fastembed `
  -e RAG_ORT_EXECUTION_PROVIDER=CUDAExecutionProvider `
  -e RAG_QDRANT_URL=http://host.docker.internal:6333 `
  clinical-summarizer:nvidia-v0.1.0
```

`Dockerfile.nvidia` giả định host đã cấu hình NVIDIA Container Toolkit và
driver tương thích CUDA/cuDNN của image.

## Kubernetes

Files:

| File | Nội dung |
| --- | --- |
| `deploy/k8s/deployment.yaml` | Namespace, ConfigMap, Intel Deployment, Service, HPA |
| `deploy/k8s/deployment-nvidia-patch.yaml` | GPU node selector, CUDA provider, GPU resource limit |

Triển khai Intel:

```powershell
kubectl apply -f deploy/k8s/deployment.yaml
kubectl -n clinical-ai get deploy,svc,hpa
```

Triển khai NVIDIA dùng overlay/patch trong pipeline phát hành:

```powershell
kubectl apply -f deploy/k8s/deployment.yaml
kubectl patch deployment clinical-summarizer-api -n clinical-ai --patch-file deploy/k8s/deployment-nvidia-patch.yaml
```

### Autoscaling

`HorizontalPodAutoscaler` dùng `autoscaling/v2`:

- Minimum `2` pods để có high availability.
- Maximum `10` pods.
- Scale up khi CPU trung bình vượt `65%` hoặc memory vượt `75%`.
- Scale-down có cửa sổ ổn định `300` giây để tránh dao động khi giờ khám cao điểm.

Cluster cần Metrics Server hoặc metrics adapter tương ứng để HPA đọc CPU/memory.
Với production nâng cao, nên bổ sung custom metric như request latency hoặc
queue depth bên cạnh tài nguyên hệ thống.

## MLflow Tracking

Code: `backend/app/services/telemetry.py`.

Enable bằng environment:

```dotenv
RAG_MLFLOW_ENABLED=true
RAG_MLFLOW_TRACKING_URI=http://mlflow.clinical-ai.svc.cluster.local:5000
RAG_MLFLOW_EXPERIMENT_NAME=medical-record-summarization-prod
RAG_MLFLOW_LOG_REDACTED_SAFETY_ARTIFACTS=true
```

Khi chạy local không có tracking server, cấu hình mẫu dùng
`sqlite:///./backend/var/mlflow.db`; filesystem-only MLflow tracking không được
chọn làm mặc định vì đã deprecated ở các phiên bản MLflow mới.

Mỗi request summary ghi:

| Metric / Tag | Ý nghĩa |
| --- | --- |
| `latency_ms` | Thời gian retrieval + generation + guardrail |
| `input_tokens_estimated` | Token của query và retrieved evidence |
| `output_tokens_estimated` | Token của candidate summary |
| `retrieved_chunks` | Số evidence chunks |
| `citation_coverage_pct` | Tỉ lệ claims được support |
| `suspected_hallucination` | `1` khi blocked hoặc có guardrail issue |
| `guardrail_issue_count` | Tổng issue bị phát hiện |
| `workflow`, `generator_provider`, `embedding_provider` | Metadata vận hành |

### PHI Safety

Telemetry mặc định không log:

- raw patient text;
- generated claim text;
- source evidence;
- patient/tenant identifier.

Khi có suspicion, artifact chỉ chứa `issue_codes`, số lượng lỗi và coverage.
Nếu MLflow tracking server không khả dụng, API vẫn trả kết quả cho workflow;
failure telemetry được ghi vào application log thay vì làm hỏng request.

## File Delivery

| File | Vai trò |
| --- | --- |
| `Dockerfile` | CPU / Intel OpenVINO image |
| `Dockerfile.nvidia` | NVIDIA CUDA image |
| `.dockerignore` | Không đưa `.env`, dữ liệu và artifacts vào build context |
| `requirements.txt` | Unified runtime, evaluation, and MLflow dependencies for local SQLite validation and remote server |
| `backend/app/services/telemetry.py` | Metrics/safety logging |
| `deploy/k8s/deployment.yaml` | Kubernetes workload và autoscaling |
| `deploy/k8s/deployment-nvidia-patch.yaml` | GPU deployment override |

## Production Controls Còn Cần

- Secret manager/KMS cho Qdrant, MLflow auth và mọi provider credentials.
- NetworkPolicy chỉ cho API gọi Qdrant/MLflow/FHIR endpoints được duyệt.
- MLflow database/artifact encryption, retention policy và audit access.
- Model artifact registry nội bộ để pods không tải model công khai lúc startup.
- Alerting trên latency p95, tỷ lệ `suspected_hallucination`, lỗi guardrail và
  failure của FHIR writeback.
