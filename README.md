# MultiClicker

多位置循环点击器 —— 录制多个屏幕位置,依次循环定时点击。

纯本地运行,无广告、无联网、无遥测。深色现代 UI,内置倒计时保护、热键控制、紧急停止。

## 功能

- **多位置录制**:把鼠标移到目标处按 `F8`(或点按钮)逐个录制位置,支持排序和删除
- **循环点击**:按 `F9` 开始,依次点击所有位置,点完一轮从头再来
- **定时间隔**:每个位置点击间隔、整轮额外等待时间均可自定义(秒)
- **安全保护**:开始前倒计时(可配置 0-60 秒,期间可取消)、运行中按 `ESC` 立即急停
- **实时反馈**:当前点击位置卡片高亮、本轮进度/总点击统计、鼠标坐标实时显示、运行日志
- **设置记忆**:所有参数自动保存,下次启动自动恢复
- **左键/右键、单击/双击**、窗口置顶

## 热键

| 按键 | 功能 |
|---|---|
| `F8` | 录制当前鼠标位置 |
| `F9` | 开始 / 停止循环点击 |
| `F10` | 清空位置列表 |
| `ESC` | 紧急停止 / 取消倒计时 |

## 使用

### 直接下载 exe(推荐)

到 [Releases](../../releases) 下载 `MultiClicker.exe`,双击运行,无需安装 Python。

> 杀毒软件可能对控制鼠标的程序误报,添加信任即可。

### 从源码运行

```bash
pip install -r requirements.txt
python app.py
```

### 打包 exe

```bash
python -m venv buildenv
buildenv/Scripts/pip install -r requirements.txt pyinstaller
buildenv/Scripts/python -m PyInstaller --onefile --windowed --name MultiClicker --icon icon.ico --collect-data customtkinter app.py
```

## 依赖

- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — 现代 UI
- [pynput](https://github.com/moses-palmer/pynput) — 鼠标控制与全局热键

## 免责声明

本工具仅供学习与合法自动化用途(重复性操作、软件测试等)使用。请勿用于违反任何软件服务条款、游戏规则或法律法规的场景,由此产生的后果由使用者自行承担。

## License

[MIT](LICENSE)
