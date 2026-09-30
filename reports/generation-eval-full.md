# 真实模型问答抽样评测

- 时间：2026-09-21T03:32:42.996679+00:00
- API：`http://127.0.0.1:8765`、`http://127.0.0.1:8766`；采样种子：`17`；已记录 110/110 题，获得非暂时性结果 110/110 题，待重试 0 题。
- 数据：虚构制度与尚未独立复核的题目；本报告不能外推到真实企业。
- 判定：自动指标只检查 API 状态、预期文档是否被引用、无答案状态和越权暴露。
- **答案要点正确率和引用语义支持率尚未人工复核，不能用自动指标替代。**

| 指标 | 结果 |
| --- | ---: |
| 待重试题目 | 0 |
| 有答案题返回回答（已评测） | 73/80 |
| 有答案题引用全部预期文档（已评测） | 73/80 |
| 无答案题拒答（已评测） | 25/25 |
| 越权文档引用次数 | 0 |
| 未知来源引用次数 | 0 |
| 返回 Token 用量的请求 | 110/110 |
| 输入 / 输出 Token | 41260 / 2814 |
| 端到端 p50 / p95 | 3231.21 / 10540.22 ms |

`model_unavailable`、`quota_exceeded` 等状态不计为成功拒答；逐题答案、预期要点与引用正文见 JSON。
端到端延迟统计排除待重试请求。
Token 用量是接口报告值，不是供应商账单或费用保证。

## 待复核题目

| 类别 | 问题 | 状态 | 请求 ID |
| --- | --- | --- | --- |
| single_document | 休六天年假要提前几天申请？ | insufficient_evidence | `622de54e-457a-48c9-a2ed-16f4f69cf5a5` |
| single_document | 远程办公能用公共电脑下载内部资料吗？ | insufficient_evidence | `4db7249d-f382-482c-8c92-6f83ae7049c5` |
| single_document | 出纳能自行修改供应商收款账户吗？ | insufficient_evidence | `649383bb-c519-4a72-a707-2b90e640de3b` |
| single_document | 供应商风险复核有效期多久？ | insufficient_evidence | `c87297ca-dc16-425f-a0bd-ab23911c519c` |
| single_document | 可以先签采购合同再补审批吗？ | insufficient_evidence | `160ae146-cf28-4f98-9c20-5bb5a1287feb` |
| single_document | 变更申请单必须包含什么？ | insufficient_evidence | `cd7b96cd-77b8-4ffa-9a4d-f5e56a24ddf5` |
| cross_document | 紧急生产变更引发 P1 故障，变更与事故各要多久补记录？ | insufficient_evidence | `ad05a88a-66f1-4b45-928b-c08ac322de8b` |
