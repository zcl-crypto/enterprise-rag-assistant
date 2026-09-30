# 拒答复核提示词 A/B

- 时间：2026-09-21T03:37:02.867972+00:00
- 模型：`glm-4-flash-250414`；API：`http://127.0.0.1:8765`。
- 范围：当前完整评测中的 7 道有答案拒答题，以及全部 25 道无答案题。
- 本实验直接测试候选复核提示词，不改变线上问答逻辑；结果仍需人工检查。

| 指标 | 结果 |
| --- | ---: |
| 正例回答 | 0/7 |
| 正例引用全部预期文档 | 0/7 |
| 无答案题保持拒答 | 25/25 |
| 引用格式无效答案 | 0 |
| 输入 / 输出 Token | 13745 / 288 |

## 逐题结果

| 类别 | 问题 | 状态 | 预期文档已引用 |
| --- | --- | --- | ---: |
| single_document | 休六天年假要提前几天申请？ | insufficient_evidence | False |
| single_document | 远程办公能用公共电脑下载内部资料吗？ | insufficient_evidence | False |
| single_document | 出纳能自行修改供应商收款账户吗？ | insufficient_evidence | False |
| single_document | 供应商风险复核有效期多久？ | insufficient_evidence | False |
| single_document | 可以先签采购合同再补审批吗？ | insufficient_evidence | False |
| single_document | 变更申请单必须包含什么？ | insufficient_evidence | False |
| cross_document | 紧急生产变更引发 P1 故障，变更与事故各要多久补记录？ | insufficient_evidence | False |
| no_answer | 公司食堂周末早餐几点开始营业？ | insufficient_evidence | - |
| no_answer | 2027 年公司股票期权授予价格是多少？ | insufficient_evidence | - |
| no_answer | 总部停车场每月收费多少元？ | insufficient_evidence | - |
| no_answer | 员工子女入学补贴是多少？ | insufficient_evidence | - |
| no_answer | 去火星出差的机票由谁审批？ | insufficient_evidence | - |
| no_answer | 年休假可以分几次申请？ | insufficient_evidence | - |
| no_answer | 远程办公能否申请周三作为例外？ | insufficient_evidence | - |
| no_answer | 国内出差的每日住宿费上限是多少？ | insufficient_evidence | - |
| no_answer | 员工餐费报销每天最多多少元？ | insufficient_evidence | - |
| no_answer | 电子发票退回后第二次补正的期限是多久？ | insufficient_evidence | - |
| no_answer | 采购比价比较表应保存几年？ | insufficient_evidence | - |
| no_answer | 采购合同是否允许使用电子签章？ | insufficient_evidence | - |
| no_answer | 紧急采购超过五千元由谁先行批准？ | insufficient_evidence | - |
| no_answer | 供应商风险复核到期后能否自动续期？ | insufficient_evidence | - |
| no_answer | 备用金遗失后员工需要赔偿多少？ | insufficient_evidence | - |
| no_answer | VPN 账号密码每隔多久必须更换？ | insufficient_evidence | - |
| no_answer | P2 故障应在多久内通知应急负责人？ | insufficient_evidence | - |
| no_answer | 办公设备丢失后由谁承担赔偿？ | insufficient_evidence | - |
| no_answer | 访客证遗失的罚款标准是多少？ | insufficient_evidence | - |
| no_answer | 试用期的最长期限是几个月？ | insufficient_evidence | - |
| no_answer | 培训报销未用额度可以结转到下一年吗？ | insufficient_evidence | - |
| no_answer | 超预算幅度不超过百分之十时由谁审批？ | insufficient_evidence | - |
| no_answer | 受限数据加密链接的密码至少多少位？ | insufficient_evidence | - |
| no_answer | 访客非工作时间入园最迟要提前多久申请？ | insufficient_evidence | - |
| no_answer | 系统访问日志具体保存在哪台服务器？ | insufficient_evidence | - |
