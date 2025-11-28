# 离线镜像缓存

本目录用于存放预构建的 Docker 镜像 tar 包，支持完全离线部署。

## 所需镜像文件

| 文件名 | 来源镜像 | 大小约 |
|--------|----------|--------|
| `redis-7-alpine.tar` | redis:7-alpine | ~15 MB |
| `python-3.10-slim.tar` | python:3.10-slim | ~130 MB |
| `nginx-alpine.tar` | nginx:alpine | ~45 MB |

## 生成方法

### 方法一：使用打包脚本（推荐）

在**本地开发机**（能正常访问 Docker Hub）上执行：

```bash
python scripts/package_images.py
```

### 方法二：手动生成

在能访问 Docker Hub 的机器上执行：

```bash
# 1. 拉取镜像
docker pull redis:7-alpine
docker pull python:3.10-slim
docker pull nginx:alpine

# 2. 导出为 tar 文件
docker save -o docker/image-cache/redis-7-alpine.tar redis:7-alpine
docker save -o docker/image-cache/python-3.10-slim.tar python:3.10-slim
docker save -o docker/image-cache/nginx-alpine.tar nginx:alpine
```

## 部署流程

1. 确保本目录包含上述 3 个 tar 文件
2. 将整个项目打包为 `AutoPaperWeb_Server.zip`
3. 上传到服务器 `/opt/AutoPaperWeb_Server.zip`
4. 执行 `sudo /opt/deploy_autopaperweb.sh`

部署脚本会自动检测并加载这些离线镜像。

## 注意事项

- 这些 tar 文件较大，请确保 zip 压缩包包含它们
- 如果镜像版本需要更新，请重新生成 tar 文件
- 服务器上不需要网络即可完成部署

