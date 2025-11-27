# Nginx 部署 (反向代理)

本指南介绍如何在宿主机配置 Nginx，作为网关转发流量到 Docker 容器。

## 1. 架构说明

- **Frontend**: 运行在容器端口 18080 (HTTP)
- **Backend**: 运行在容器端口 8080 (HTTP)
- **Nginx (Host)**: 监听 80/443，根据路径转发

## 2. Nginx 配置示例

创建 `/etc/nginx/sites-available/autopaperweb.conf`：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或IP

    # 强制跳转 HTTPS (可选)
    # return 301 https://$host$request_uri;

    # 前端静态页面
    location / {
        proxy_pass http://127.0.0.1:18080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 支持流式输出 (如下载/SSE)
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

## 3. 启用配置

```bash
sudo ln -s /etc/nginx/sites-available/autopaperweb.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 4. HTTPS 配置 (推荐)

使用 Certbot 自动配置 SSL：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```
