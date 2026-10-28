# Security & Local Interface Audit / 安全与本机接口审计

**Project:** MrLiHua · 李华同学  
**Audit date:** 2026-10-28  
**Scope:** distributed HTML/CSS/JS, Python build scripts, demo output

## 1. 结论

MrLiHua 采用**纯静态、单文件、离线**架构：

- 没有后端、服务端进程、数据库或监听端口；
- 页面不发起网络请求；
- 不加载 CDN、远程字体、第三方脚本或统计 SDK；
- 构建脚本只读写本地文件；
- 公开仓库不包含真实试卷或学生数据。

## 2. 浏览器接口清单

对 `assets/app.js`、`assets/app.css`、`templates/shell.html` 和生成的 HTML 进行检索，结果如下：

| 接口 / 行为 | 状态 | 说明 |
|---|---|---|
| `fetch` / `XMLHttpRequest` | 未使用 | 无 HTTP 请求 |
| `WebSocket` / `EventSource` | 未使用 | 无长连接 |
| `navigator.sendBeacon` | 未使用 | 无上报 |
| `https://` / `http://` 外部资源 | 未使用 | 无 CDN、远程字体、图片 |
| `<script src>` / `<link rel="stylesheet">` | 未使用 | CSS/JS 内联 |
| Cookie | 未使用 | 无 Cookie |
| `localStorage` | 仅字号 | key: `exam-font-size`，只保存 `normal/large/xlarge` |
| `sessionStorage` / IndexedDB | 未使用 | 不存储试卷 |
| Service Worker | 未使用 | 无后台缓存 |
| Camera / Microphone / Geolocation | 未使用 | 不申请设备权限 |
| Clipboard | 未使用 | 不读取剪贴板 |
| `file://` | 支持 | 双击 HTML 即可运行 |
| Fullscreen API | 使用 | 需用户点击“全屏”手势 |
| 外部端口 / localhost | 未使用 | 无本地服务 |

## 3. 构建脚本

`scripts/build_exam.py`、`scripts/validate_exam.py`：

- 仅使用 Python 标准库；
- 读取本地 JSON，写出本地 HTML；
- 不访问网络。

`scripts/prepare_images.py`：

- 使用 Pillow 做旋转、裁切、缩放、对比度；
- 只读写本地图片；
- 不访问网络。

## 4. 路径与部署

- 发布文件不包含硬编码的 `C:\Users\...` 或 `D:\...` 绝对路径；
- 构建命令使用相对路径；
- 生成 HTML 无外部依赖，可复制到任意目录或 U 盘；
- 无安装器、无注册表写入、无后台常驻程序。

## 5. 已知边界

1. **只使用可信 JSON**  
   HTML 由本地 JSON 构建；虽然输出对文本做了 HTML 转义，仍不建议把来源不明的 JSON 直接构建后分发给他人。

2. **浏览器本地存储**  
   `localStorage["exam-font-size"]` 只保存字号偏好；清除站点数据即可删除。

3. **版权与隐私**  
   工具本身不上传数据，但使用者把生成 HTML 发布到网上时，仍可能暴露试卷内容。公开前请移除学校名、学生信息和未授权材料。

4. **AI 生成内容**  
   AI 辅助的译文、结构、解析可能有误，见 [AI_DISCLOSURE.md](AI_DISCLOSURE.md)。

## 6. 报告问题

请在本仓库开 Issue，并尽量提供：

- 浏览器版本；
- 复现步骤；
- 相关控制台错误；
- 不包含学生隐私和完整试卷的最小示例。

<https://github.com/salicylate350234/MrLiHua/issues>
