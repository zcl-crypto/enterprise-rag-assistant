# 虚构制度语料

`manifest.json` 中的全部企业、制度、金额和时限均为虚构，仅用于项目演示与检索评测。

- `manifest.json`：25 份制度正文、格式、部门范围与 75 道单文档问答标注。
- `eval_extras.json`：5 道跨文档、25 道无答案、5 道越权问题。
- `generated/`：运行 `python -m scripts.generate_corpus` 生成的真实 PDF、DOCX、Markdown、TXT、HTML 文件。

评测只索引这 25 份互不重复的制度；早期 `data/sample/` 的 3 份 Markdown 样例不参与评测。标注尚待独立人工复核，不能视为最终冻结测试集。
