# MultiClicker

多位置循环点击器 + 连点器 —— 纯本地运行,无广告、无联网、无遥测。白色简洁 UI,内置倒计时保护、热键控制、紧急停止。

## 功能

**🔄 循环点击**
- 录制多个屏幕位置(`F8`),依次循环定时点击,点完一轮从头再来
- 每个位置的点击间隔、整轮额外等待时间均可自定义
- 位置支持排序、删除;开始前倒计时(可配置 0-60 秒,期间可取消)

**⚡ 连点器**
- 跟随鼠标或固定位置快速连击,间隔最小 10ms(每秒约 100 次)
- 可设置点击次数上限(0 = 无限),实时显示 CPS 与总次数
- 连点立即开始,无倒计时

**通用**
- 左键/右键、单击/双击、窗口置顶
- 当前点击位置高亮、进度统计、鼠标坐标实时显示、运行日志
- 所有参数自动保存,下次启动自动恢复
- `ESC` 随时紧急停止

## 热键

| 按键 | 功能 |
|---|---|
| `F8` | 录制位置(循环模式)/ 设定固定点(连点模式) |
| `F9` | 开始 / 停止 |
| `F10` | 清空列表(循环模式)/ 清除固定点(连点模式) |
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
