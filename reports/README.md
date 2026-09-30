# Evaluation Reports

本目录保留可复现的离线评测快照。语料、企业名称和制度均为虚构数据。

## 推荐阅读顺序

1. [`hybrid-eval.md`](hybrid-eval.md)：Dense、Hybrid、Hybrid + Reranker 的 110 题检索对照。
2. [`generation-eval-full.md`](generation-eval-full.md)：真实模型 API 的 110 题端到端结果。
3. [`generation-eval-analysis.md`](generation-eval-analysis.md)：过度拒答案例及原因分析。
4. [`independent-review-pack.md`](independent-review-pack.md)：供独立真人复核的固定抽样包，目前尚未填写。

其余 `generation-eval-*` 和 `refusal-retry-*` 文件用于记录开发过程中的小样本、提示词和
拒答策略实验，不应替代最终报告。

## 指标边界

- 检索指标只判断预期文档是否进入候选集合。
- 生成自动指标只判断回答状态、预期文档引用、未知引用和越权暴露。
- 自动指标不能替代答案正确率或引用语义支持率；这两项需要独立人工复核。
