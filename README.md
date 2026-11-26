# 课程测试站自动请求作业

面向教师提供的授权练习环境。程序通过 Python 标准库完成登录、HMAC-SHA256 请求签名、结果校验，并可注册 Windows 每日计划任务。默认时间为电脑本地时间 13:00；中国时区电脑即北京时间 13:00。

## 下载和运行

1. 在 GitHub 项目页面点击 **Code → Download ZIP**，下载并完整解压。
2. 双击 `install.cmd`。安装器会查找 Python 3.10 或更新版本，并验证标准库完整。如果没有合适版本，会尝试通过 Windows 自带的 `winget` 安装 Python 3.13。没有 winget 时，请先从 [python.org](https://www.python.org/downloads/windows/) 安装 Python，再重试。
3. 按提示输入教师指定的测试服务器根地址，例如 `http://127.0.0.1:3033`，不要附加 `/api` 路径。
4. 输入每天运行时间，直接回车使用 `13:00`；再输入课程练习账号。密码输入时不会显示。
5. 安装完成后，双击 `run-now.cmd` 可立即运行一次。成功时会显示服务器返回的成功消息和日期；双击 `view-log.cmd` 可查看本机运行日志。

安装后 Windows 会按设置的时间自动运行。无需每天输入密码、打开网页或手动启动程序。电脑需开机、联网，并保持安装时使用的 Windows 用户已登录，锁屏可以。唤醒睡眠中的电脑还取决于硬件和电源设置。错过运行时间后，任务会在系统恢复可用时补跑。

程序安装时不会立即提交，也不会预先标记当天成功。只有服务器返回成功并确认当天日期后，才会记录本机成功标记；同一安装目录当天再次运行会跳过。网页或另一台电脑上的操作不会同步到本机标记。

## 文件说明

- `install.cmd`：双击启动安装。
- `run-now.cmd`：立即运行一次。
- `view-log.cmd`：打开本机日志。
- `uninstall.cmd`：移除定时任务。
- `install.ps1`、`uninstall.ps1`：安装和卸载逻辑。
- `course_checkin.py`：登录、签名、提交与结果校验。
- `tests`：不联网的 mock 测试。

任务名称为 `CourseCheckin-Daily`。可执行文件、服务器配置、加密凭据、日志和成功标记保存在 `%LOCALAPPDATA%\CourseCheckinDemo`，与项目下载目录分离，因此解压目录之后可以移动。账号密码由 Windows 当前用户加密保存，老师需要输入自己的课程练习账号，不能复用作者电脑上的凭据。

双击 `uninstall.cmd` 只删除计划任务。本机凭据和日志保留在上述目录，便于检查；确认不再需要后，可自行删除该目录。

## 接口与签名

登录为 `POST /api/auth/login`，JSON 字段 `student_no`、`password`。成功响应的 `data` 提供 `token` 和 `sign_key`。提交为 `POST /api/attendance/check-in`，请求体 `{"status":"在校"}`。

签名请求头包括 `Authorization: Bearer <token>`、`X-Timestamp`、`X-Nonce` 和 `X-Sign`。签名原文由大写方法、`/api` 加路径、查询参数行、毫秒时间戳、随机 nonce 组成，以 LF 分行；本请求没有查询参数，所以第三行为空。以 `sign_key` 的 UTF-8 字节为密钥计算 HMAC-SHA256，结果用小写十六进制表示。每次执行都重新登录，不保存长期令牌。

程序只有在响应 `code == 200` 且 `data.attendance_date` 为当天时，才记录成功。

## 离线测试

在项目目录打开终端运行：

```powershell
python -m unittest discover -s tests -v
```

测试会替换网络调用，不连接课程站，也不会创建记录。

## 上传到 GitHub

1. 登录 GitHub，点右上角 `+`，选择 `New repository`。
2. 名称可填 `course-checkin-demo`，可见性按课程要求选择；创建时不要自动生成 README。
3. 创建后点 `uploading an existing file`，把本目录中的文件和 `tests` 文件夹拖入，然后点 `Commit changes`。
4. 将仓库页面链接交给老师。私有仓库要邀请老师的 GitHub 账号。

`.gitignore` 排除了本机凭据、配置、日志和成功标记。网页上传前仍需检查文件清单，不要上传账号、密码或运行数据。
