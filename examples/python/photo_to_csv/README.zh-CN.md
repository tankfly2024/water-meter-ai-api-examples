# WaterMeter Photo-to-CSV：水表照片识别与表格导出

[English](README.md) · [API 调用示例](../../../README.md)

这是水表项目下的客户端子项目，目标是把一张或一批水表照片整理为可人工核对、修改并导出的读数表，通过 WaterMeter AI 公开 API 完成识别。

**当前状态：项目初始化。** 已建立目录并记录范围，应用功能、启动程序和可下载发行版尚未实现。

## 首版范围

1. 导入单张或多张指针表、机械数字表照片。
2. 使用用户自己的 API Key 提交识别并查询进度。
3. 并排核对原图、AI 原始读数和识别状态。
4. 单独记录人工确认读数，保留原始 AI 结果。
5. 导出文件名、读数、状态及备注等 CSV 字段；未读出项目保留供核对。

API 调用遵循账号当前的服务端额度和服务规则，实际可用次数以官网及额度接口为准。

## 目录职责

| 位置 | 内容 |
| --- | --- |
| `src/` | 客户端程序及界面源码 |
| `tests/` | 客户端测试 |
| `docs/` | 使用和开发说明 |

用户照片、导出表格、密钥及日志保存在源码目录之外的本地数据目录。本目录另设忽略规则，防止临时输入和输出被意外提交。

## 当前可用的调用示例

现有 [Python 单图调用示例](../recognize.py)及其[依赖清单](../requirements.txt)可按[仓库快速开始](../../../README.md#quick-start)使用。

- 官网：https://watermeterai.com/
- 中文 API 文档：https://watermeterai.com/zh-cn/api-docs
- API Key 管理：https://watermeterai.com/zh-cn/api-keys
