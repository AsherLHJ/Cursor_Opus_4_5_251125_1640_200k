# Nginx 部署（反向代理、负载均衡、可选 HTTPS/SSL）

本指南面向全新云服务器实例，采用宿主机 Nginx 作为前端网关，转发到本项目 Docker 容器（前端 18080、后端 18081/18082/18083）。内容遵循极简原则，仅列关键步骤；如需更详细参数说明，请参考阿里云官方文档（建议）：

- 在 Nginx 或 Tengine 服务器安装 SSL 证书（Linux）：
https://help.aliyun.com/zh/ssl-certificate/user-guide/install-ssl-certificates-on-nginx-servers-or-tengine-servers

---

## 0. 准备与前置检查
- DNS：将你的域名解析 A 记录指向服务器公网 IP（例如 autopapersearch.com 与 www.autopapersearch.com）。
- 安全组/防火墙：放通 80/443（TCP）。Ubuntu 可使用 UFW；云平台需在安全组开放 80/443。
- Docker 服务：项目容器已按 `docker-compose.yml` 在本机监听 18080（前端）与 18081-18083（后端）。

可选（验证 443 端口连通性）：见阿里云文档中的“步骤二：配置系统与网络环境”。

---

## 1. 安装 Nginx（Ubuntu）
```bash
sudo apt-get update -y
sudo apt-get install -y nginx
```

确认目录结构（常见）：
```
/etc/nginx/
  ├─ nginx.conf
  ├─ sites-available/
  └─ sites-enabled/
```

---

## 2. 非 HTTPS（仅 80 端口）最小可用（如果要配置SSL，则跳过此步骤）
如暂不启用证书，可直接使用仓库自带示例：
```bash
sudo cp /opt/AutoPaperWeb/deploy/nginx_host.conf /etc/nginx/sites-available/autopaperweb.conf
sudo ln -s /etc/nginx/sites-available/autopaperweb.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```
提示：如使用域名，请将 `server_name` 从 IP 改为你的域名。

---

## 3. 启用 HTTPS（443）
步骤参考阿里云官方文档，以下为关键要点：

### 3.1 上传证书到服务器
- 将证书文件与私钥（例如 autopapersearch.com.pem、autopapersearch.com.key）上传到：`/etc/ssl/certs/`
- 建议权限与属主（避免 Nginx 启动失败）：
```bash
sudo chown root:root /etc/ssl/certs/autopapersearch.com.pem /etc/ssl/certs/autopapersearch.com.key
sudo chmod 600 /etc/ssl/certs/autopapersearch.com.key
sudo chmod 644 /etc/ssl/certs/autopapersearch.com.pem
```

说明：若你生成 CSR 时本地持有私钥，下载的证书包不含 .key，需与本地私钥配对使用。私钥遗失需重新签发。

### 3.2 使用示例配置（80 跳转到 443 + 443 反代）
仓库提供 SSL 示例：`deploy/nginx_host_ssl.conf`。按需调整域名与证书路径后部署：
```bash
sudo cp /opt/AutoPaperWeb/deploy/nginx_host_ssl.conf /etc/nginx/sites-available/autopaperweb.conf
sudo ln -sf /etc/nginx/sites-available/autopaperweb.conf /etc/nginx/sites-enabled/autopaperweb.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

示例关键点：
- `server_name autopapersearch.com www.autopapersearch.com;`
- 80 端口仅做 `return 301 https://$host$request_uri;`
- 443 端口：配置 `ssl_certificate` 与 `ssl_certificate_key` 并保持与 80 相同的反代/负载均衡逻辑
- 可选：开启现代 TLS、HSTS 等（示例已附常用配置，可按需启用）

---

## Nginx常规配置结束，如果有域名变更或SSL证书变更，则继续往下参考步骤4

## 4. 域名变更时需同步修改
- Nginx：`/etc/nginx/sites-available/autopaperweb.conf` 中的 `server_name`（以及证书文件路径，如更换域名证书）。
- 证书：更换域名后需部署对应新证书（.pem/.key）。
- CORS（如需）：`docker-compose.yml` 中的 `CORS_ALLOW_ORIGIN`，建议设置为你的前端域名（含协议，例如 `https://autopapersearch.com`）。修改后 `docker compose up -d` 使其生效。
- DNS：更新新的域名解析指向新服务器公网 IP。

---

## 5. 验证与排错
- 语法检测与重载：`sudo nginx -t && sudo systemctl reload nginx`
- 浏览器访问：`https://<你的域名>`，应看到前端页面，地址栏显示安全锁/安全图标
- 快速探测：
```bash
curl -I http://127.0.0.1:18080
curl -sS -o /dev/null -w "%{http_code}\n" https://autopapersearch.com/api/folders
```

---

## 6. 参考（深入配置）
- 阿里云 SSL 安装文档（更详细的 OpenSSL/TLS、模块校验、端口连通验证、防火墙等步骤）：
  https://help.aliyun.com/zh/ssl-certificate/user-guide/install-ssl-certificates-on-nginx-servers-or-tengine-servers
