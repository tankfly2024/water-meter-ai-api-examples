# WaterMeter AI：Home Assistant 水表集成

[English](README.md) · [官网](https://watermeterai.com/) · [API文档](https://watermeterai.com/zh-cn/api-docs) · [申请API Key](https://watermeterai.com/zh-cn/api-keys)

利用已经接入 Home Assistant 的摄像头拍摄水表，调用水表云端识别 API，把累计读数显示成传感器，并为用水统计提供数据。当前服务支持指针表、机械数字表；不承诺 LED 表识别。

**欢迎先到[水表识别官网 watermeterai.com](https://watermeterai.com/zh-cn)体验识别。在官网[免费注册](https://watermeterai.com/zh-cn/login?flow=register)并登录，即可[免费创建API Key](https://watermeterai.com/zh-cn/api-keys)，用于连接本插件。普通免费账号每天可识别20次，与官网及所有API工具共用额度，特殊账号按实际额度执行。** 接入方式见[中文API文档](https://watermeterai.com/zh-cn/api-docs)。

**当前为0.1.0本地测试原型。** 已提供读数状态机和本机HTTP模拟服务测试；真实 Home Assistant 安装、配置界面、摄像头取图、统计面板和生产API识别尚待端到端实测。本项目是手工安装的自定义集成，不宣称已进入官方集成或HACS。适配代码参照 Home Assistant 2026.11.2，未认证其它版本兼容性。

## 功能

- 在配置界面选择已有 `camera` 实体，填入自己的 API Key。
- 点击“识别水表”抓取并上传一张 JPEG、PNG 或 WEBP 图片，最大20MB。默认没有定时上传，启动和重启不触发识别。
- 首次读数、超过阈值的正向跳变进入“待确认读数”。对照真实水表后点击“确认待确认读数”；误读可点击“丢弃待确认读数”，保留已有累计值。
- 首次确认后，未超过阈值的正向变化自动接受。它仍是AI估计值，请按表型、单位和识别频率设置阈值。
- 倒退、质量拦截、失败任务均不覆盖已有累计值，无法识别不会填成0。首版不处理换表、满位归零和统计重置。
- 在 Home Assistant 存储中保存累计值、候选值、任务ID及图片摘要。查询超时或重启后，再点击“识别水表”会查询已保存的任务，不重新上传；连续两次图片字节完全相同时不重复提交。
- 识别后查询服务端额度。普通免费账号**每天20次**，与官网、图片转CSV及其它客户端共用，按服务端自然日（通常为 Asia/Shanghai）重置，未用完不累积。付费、自定义及合作账号按实际政策执行；安装插件不会另送额度，也不会自动获得合作作者额度。

## 手工安装与使用

需要已经运行的 Home Assistant、能够正常取图的水表摄像头、互联网连接，以及允许查询额度、提交任务、查询任务的 API Key。插件不提供摄像头驱动，不在本地运行识别模型。

1. 备份 Home Assistant 配置。
2. 将完整 `custom_components/watermeter_ai` 文件夹复制到 Home Assistant 配置目录。最终应存在 `<配置目录>/custom_components/watermeter_ai/manifest.json`。如果使用安装ZIP，先解压，再复制该文件夹。
3. 重启 Home Assistant。
4. 打开“设置 → 设备与服务 → 添加集成”，搜索 **WaterMeter AI**。
5. 填入API Key，选择摄像头、API读数代表的单位（`m³`或`L`）、允许自动接受的最大增量。默认阈值为所选单位的`10`。插件不自动推断或换算单位，首次确认前必须与实体水表核对。
6. 打开新增设备，点击“识别水表”，对照水表确认或丢弃候选值。

设备提供4个传感器：水表累计读数、待确认读数、识别状态、今日剩余免费识别次数；3个按钮：识别、确认、丢弃。实体ID由Home Assistant实际分配。累计值在首次确认前显示未知；付费账号不会显示虚构的免费剩余次数。

## 用水统计与可选定时识别

累计传感器声明 `device_class: water`、`state_class: total` 及用户选定的体积单位，目标是在完成宿主实测后接入“设置 → 仪表盘 → 能源 → 用水量”。首次确认的是历史累计值，作为统计基准，不等于当天用水量。请先在真实安装中核对统计结果。参见 [Home Assistant 用水指南](https://www.home-assistant.io/docs/energy/water/)和[传感器统计规则](https://contributors.home-assistant.io/core/entities/sensor/)。

[自动化示例](examples/automation.yaml)展示按 Home Assistant 时区每天两次识别。需要用户自行替换按钮实体ID、添加并启用，插件不自动安装或开启。共用日额度还要预留给官网和手动测试。待确认读数未处理时，后续自动识别会被阻止。

## 异常、保存与隐私

- API Key保存在Home Assistant原生配置项中，不进入传感器属性或插件的读数状态文件；Home Assistant配置文件和备份仍包含凭据，应限制访问。
- 用户主动识别或自行配置的自动化执行时，照片才会发送到`https://watermeterai.com`处理。插件不把图片字节写入磁盘；摄像头自身行为和服务端数据政策另行适用。
- 配置只查询额度，不提交图片；启动、重启也不识别。额度在识别后刷新，不持续轮询，因此其它客户端用过额度后，当前显示可能滞后。
- 上传明确被拒绝（如429）后需要手动重试，不循环提交。提交时断网、响应损坏或取消，可能出现“服务端已接受但本地没收到ID”。此时显示“请核查官网任务历史”，并阻止继续上传，避免重复扣次。请先在官网确认任务情况。首版暂未提供未知提交或任务已删除时的界面恢复入口；在官网处理清楚后，可移除并重新添加集成，建立新的本地记录。未核清前不要重建。
- 识别时发现凭据失效会进入Home Assistant重新认证；更新Key保留本地读数和任务ID，新Key需属于有权查询该任务的同一账号。
- 停止定时上传需停用自行添加的自动化。移除集成不会取消已经提交的云端任务。

## 打包与测试

状态机、HTTP测试和打包脚本只需Python 3.9及以上标准库；完整插件需要Home Assistant对应的Python和依赖环境。

```bash
python -B -m unittest discover -s tests -v
python -B package.py --output watermeter-ai-0.1.0.zip
```

测试使用模拟读数及真实本机HTTP服务器，不调用生产API。没有安装Home Assistant时，宿主导入测试会明确跳过；即使导入通过，也不能代替真实安装验收。ZIP只包含自定义集成源码、翻译、说明和可选自动化示例，不包含模型、凭据、图片或服务端代码。

如需批量图片复核、导出表格，请使用另一款[水表图片转CSV工具](../python/image_to_csv/README.md)。
