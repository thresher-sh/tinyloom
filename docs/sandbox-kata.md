# Running tinyloom in Kata Containers

[Kata Containers](https://katacontainers.io/) runs each container inside a lightweight virtual machine with its own kernel. You get the convenience of container tooling (`docker run`, `podman run`) with VM-level isolation -- the strongest boundary available short of a dedicated machine.

This is the best option when running untrusted agent code where container namespace isolation isn't enough. Each tinyloom session gets its own kernel, so a container escape doesn't reach the host.

## Prerequisites

- **Linux only** (x86_64, aarch64, ppc64le, or s390x)
- Hardware virtualization enabled (Intel VT-x, AMD SVM, or ARM Hyp)
- If running inside a VM, nested virtualization must be enabled
- Docker or containerd installed
- No macOS or Windows support (Kata needs bare-metal KVM or nested virt)

Verify KVM is available:

```bash
lsmod | grep kvm
# should show kvm_intel or kvm_amd
```

## Install Kata

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/kata-containers/kata-containers/main/utils/kata-manager.sh) install"
kata-runtime check
```

## Configure the Runtime

### With Docker

Add to `/etc/docker/daemon.json`:

```json
{
  "runtimes": {
    "kata": {
      "path": "/opt/kata/bin/containerd-shim-kata-v2"
    }
  }
}
```

```bash
sudo systemctl restart docker
```

### With containerd

Add to `/etc/containerd/config.toml`:

```toml
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata]
  runtime_type = "io.containerd.kata.v2"
  privileged_without_host_devices = true
  [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata.options]
    ConfigPath = "/opt/kata/share/defaults/kata-containers/configuration.toml"
```

```bash
sudo systemctl restart containerd
```

## End User

Install tinyloom from PyPI inside a Kata-isolated container.

### One-shot

```bash
docker run --rm -it \
  --runtime=kata \
  -v $(pwd):/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom 'create a hello.py and run it'"
```

### Persistent container

```bash
docker run -dit \
  --runtime=kata \
  --name tinyloom \
  -v $(pwd):/app -w /app \
  python:3.11-slim \
  sleep infinity

docker exec tinyloom pip install -q tinyloom
```

Run tinyloom:

```bash
docker exec -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  tinyloom \
  tinyloom "fix the failing tests"
```

The only difference from plain Docker is `--runtime=kata` on the `run` command. Everything else is identical.

## Developer

Work against the tinyloom source repo with full dev tooling, isolated by a per-container VM.

### One-shot

```bash
docker run --rm -it \
  --runtime=kata \
  -v $(pwd):/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  python:3.11-slim \
  sh -c "pip install -q uv && uv sync --extra dev -q && uv run tinyloom 'create a hello.py and run it'"
```

### Persistent container

```bash
docker run -dit \
  --runtime=kata \
  --name tinyloom-dev \
  -v $(pwd):/app -w /app \
  python:3.11-slim \
  sleep infinity

docker exec tinyloom-dev pip install -q uv
docker exec -w /app tinyloom-dev uv sync --extra dev
```

Run from source:

```bash
docker exec -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  tinyloom-dev \
  uv run tinyloom "fix the failing tests"
```

Run tests:

```bash
docker exec -w /app tinyloom-dev uv run pytest tests/ -q
```

Run linter:

```bash
docker exec -w /app tinyloom-dev uv run ruff check tinyloom/ tests/
```

### Manage

```bash
docker stop tinyloom-dev
docker start tinyloom-dev
docker rm tinyloom-dev
```

## Hypervisor Options

| VMM | Best for |
|---|---|
| QEMU | Broadest hardware support, most features |
| Cloud Hypervisor | Performance-focused, modern |
| Firecracker | Minimal footprint, fast boot (< 125ms) |
| Dragonball | Built-in VMM, optimized for containers |

Switch via config file:

```bash
# Firecracker
docker run --runtime=kata --annotation io.katacontainers.config_path=/opt/kata/share/defaults/kata-containers/configuration-fc.toml ...

# QEMU (default)
docker run --runtime=kata ...
```

## Kubernetes

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: kata
handler: kata
---
apiVersion: v1
kind: Pod
metadata:
  name: tinyloom-agent
spec:
  runtimeClassName: kata
  containers:
    - name: tinyloom
      image: python:3.11-slim
      command: ["sleep", "infinity"]
      volumeMounts:
        - name: workspace
          mountPath: /app
      env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: anthropic
  volumes:
    - name: workspace
      hostPath:
        path: /path/to/project
```

## Troubleshooting

### `kata-runtime check` fails

```bash
ls -la /dev/kvm
# If permission denied:
sudo usermod -aG kvm $USER
# Log out and back in
```

### Nested virtualization

```bash
# Intel
echo 1 | sudo tee /sys/module/kvm_intel/parameters/nested
# AMD
echo 1 | sudo tee /sys/module/kvm_amd/parameters/nested
```

### Slow file I/O

Verify your Kata config uses `shared_fs = "virtio-fs"` (faster than 9pfs).
