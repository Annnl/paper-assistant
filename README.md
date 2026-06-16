# Paper Assistant

这是一个学术论文写作辅助项目，支持本地启动网页界面。

## 运行方式

在项目根目录下运行：

```powershell
python -m paper_assistant --host 127.0.0.1 --port 8000 --open
```

或者使用安装后的控制台脚本：

```powershell
paper-assistant --host 127.0.0.1 --port 8000 --open
```

然后打开浏览器访问：

```text
http://127.0.0.1:8000/
```

## 功能

- `docs/index.html`：GitHub Pages 首页
- 支持本地运行一个静态文件服务器，方便开发和调试
