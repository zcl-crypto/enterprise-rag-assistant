# Independent RAG Review Packet

This is an unreviewed, fixed sample from a fictional-policy evaluation. It is not a quality certification.
The reviewer must be a person who did not develop this project. Do not edit the source JSON report.
Review each factual claim against the cited text and the policy source. For no-answer cases, check the full corpus manifest.
Use yes, no, unclear, or N/A in each field. Record a reason for every no or unclear judgment.

- Report generated at: `2026-09-21T03:32:42.996679+00:00`
- Report SHA-256: `013fc46474086712d05a29a95b4ba6ea1a03be0651f62dc6ac40d37c0163a78c`
- Sampling seed: `20260918`
- Selected: 37 cases (20 answered, all completed positive refusals, 5 no-answer, all unauthorized).
- Corpus manifest: `data/corpus/manifest.json`

## Reviewer

- Name or identifier: [ ]
- Date: [ ]
- Report version confirmed: [ ]

## Case Index

| Case ID | Category | Model status | Question clear | Response correct | Citation supported | Access safe | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `382b3b98499fd371` | single_document | insufficient_evidence |  |  |  |  |  |
| `0665f4e391978760` | single_document | answered |  |  |  |  |  |
| `850665ae8b4b3cbc` | single_document | answered |  |  |  |  |  |
| `124fc8bbea29c4f0` | single_document | insufficient_evidence |  |  |  |  |  |
| `506aa63abe2e245a` | single_document | answered |  |  |  |  |  |
| `ff2b7c5c9581d04f` | single_document | answered |  |  |  |  |  |
| `6887afe40a013509` | single_document | answered |  |  |  |  |  |
| `de30ee343ff9a812` | single_document | answered |  |  |  |  |  |
| `0c3fb7fa9db05cb9` | single_document | answered |  |  |  |  |  |
| `c4203f0ef198debf` | single_document | answered |  |  |  |  |  |
| `9ef7edd2438fa805` | single_document | answered |  |  |  |  |  |
| `20a0362c6e5fd25f` | single_document | insufficient_evidence |  |  |  |  |  |
| `58c95504f4d28a5d` | single_document | answered |  |  |  |  |  |
| `c6407da1cc843f50` | single_document | insufficient_evidence |  |  |  |  |  |
| `7a9a3ad04d4836a2` | single_document | insufficient_evidence |  |  |  |  |  |
| `aea9461a47c4f29b` | single_document | answered |  |  |  |  |  |
| `33e105a4b0dd2313` | single_document | answered |  |  |  |  |  |
| `c3706830cb3ee95f` | single_document | answered |  |  |  |  |  |
| `de27ce4c58a381c0` | single_document | answered |  |  |  |  |  |
| `9d08d1760ea48337` | single_document | answered |  |  |  |  |  |
| `504a51aa8cac77a0` | single_document | insufficient_evidence |  |  |  |  |  |
| `177521f963c74ff5` | single_document | answered |  |  |  |  |  |
| `62c940dceff2e746` | single_document | answered |  |  |  |  |  |
| `2569485aa190cff0` | single_document | answered |  |  |  |  |  |
| `26518917a2403ead` | cross_document | answered |  |  |  |  |  |
| `976a0dd6aab9839a` | cross_document | answered |  |  |  |  |  |
| `dcb32ebc19a99872` | cross_document | insufficient_evidence |  |  |  |  |  |
| `386999f0f6fede98` | no_answer | insufficient_evidence |  |  |  |  |  |
| `99b5a5edfaa1dff7` | no_answer | insufficient_evidence |  |  |  |  |  |
| `76d3e4d6ffedad84` | no_answer | insufficient_evidence |  |  |  |  |  |
| `71137979062a2165` | no_answer | insufficient_evidence |  |  |  |  |  |
| `4451f77ae1ee36a6` | no_answer | insufficient_evidence |  |  |  |  |  |
| `0f3b5f49384bd395` | unauthorized | insufficient_evidence |  |  |  |  |  |
| `0217d11671eeb159` | unauthorized | insufficient_evidence |  |  |  |  |  |
| `9209f7b6e0e045a0` | unauthorized | insufficient_evidence |  |  |  |  |  |
| `c3f38d75fca15578` | unauthorized | insufficient_evidence |  |  |  |  |  |
| `7ad8ac0d804fe811` | unauthorized | insufficient_evidence |  |  |  |  |  |

## Case Details

### 1. `382b3b98499fd371`

- Category / user: `single_document` / `admin`
- Question: 休六天年假要提前几天申请？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 提前七个工作日
- Expected policy IDs: hr-leave
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- `hr-leave` 年休假与请假办法
  - 年休假申请: 连续五个工作日以内的年休假至少提前两个工作日申请；超过五个工作日须提前七个工作日申请。直属主管在系统中审批。
  - 病假证明: 病假连续超过两天时，员工应在返岗后三个工作日内补交医院证明；人事部核对后归档。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 2. `0665f4e391978760`

- Category / user: `single_document` / `admin`
- Question: 新员工报到当天要交哪些材料？
- Model status: `answered`
- Model answer: 新员工报到当天要交的材料包括身份证明、工资卡信息与紧急联系人 [1]。
- Reference answer: 身份证明、工资卡信息和紧急联系人
- Expected policy IDs: hr-onboarding
- Restricted policy ID: (none)

Citations returned:

- `hr-onboarding` (新员工入职办理规范 / 报到材料): 新员工报到当天提交身份证明、工资卡信息与紧急联系人；人事部只在受控系统保存扫描件。

Reference policy excerpts:

- `hr-onboarding` 新员工入职办理规范
  - 报到材料: 新员工报到当天提交身份证明、工资卡信息与紧急联系人；人事部只在受控系统保存扫描件。
  - 试用期培训: 入职后三十天内完成信息安全培训和岗位导师面谈。培训未完成时不开放生产系统权限。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 3. `850665ae8b4b3cbc`

- Category / user: `single_document` / `admin`
- Question: 远程办公申请要提前多久？
- Model status: `answered`
- Model answer: 远程办公申请要提前至少一个工作日由直属主管审批 [1]。
- Reference answer: 至少一个工作日
- Expected policy IDs: hr-remote
- Restricted policy ID: (none)

Citations returned:

- `hr-remote` (远程办公管理办法 / 申请范围): 符合岗位要求的员工每周可申请周二或周四远程办公一天，至少提前一个工作日由直属主管审批。

Reference policy excerpts:

- `hr-remote` 远程办公管理办法
  - 申请范围: 符合岗位要求的员工每周可申请周二或周四远程办公一天，至少提前一个工作日由直属主管审批。
  - 信息保护: 远程办公必须使用公司 VPN 和多因素认证，不得在公共设备下载内部资料。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 4. `124fc8bbea29c4f0`

- Category / user: `single_document` / `admin`
- Question: 远程办公能用公共电脑下载内部资料吗？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 不能
- Expected policy IDs: hr-remote
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- `hr-remote` 远程办公管理办法
  - 申请范围: 符合岗位要求的员工每周可申请周二或周四远程办公一天，至少提前一个工作日由直属主管审批。
  - 信息保护: 远程办公必须使用公司 VPN 和多因素认证，不得在公共设备下载内部资料。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 5. `506aa63abe2e245a`

- Category / user: `single_document` / `admin`
- Question: 国内出差要提前多久申请？
- Model status: `answered`
- Model answer: 根据编号资料[1]，国内出差申请应在出发前三个工作日提交。
- Reference answer: 出发前三个工作日
- Expected policy IDs: hr-travel
- Restricted policy ID: (none)

Citations returned:

- `hr-travel` (国内出差申请制度 / 行程审批): 国内出差申请应在出发前三个工作日提交，说明目的、预算和目的地；直属主管和部门负责人依次审批。

Reference policy excerpts:

- `hr-travel` 国内出差申请制度
  - 行程审批: 国内出差申请应在出发前三个工作日提交，说明目的、预算和目的地；直属主管和部门负责人依次审批。
  - 行程变更: 已批准的出差如增加城市或预算，须在订票前重新提交变更审批。紧急行程由部门负责人书面确认。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 6. `ff2b7c5c9581d04f`

- Category / user: `single_document` / `admin`
- Question: 培训报名之前要谁批准？
- Model status: `answered`
- Model answer: 根据编号资料[1]，与岗位直接相关的外部课程，在报名之前应取得主管批准。
- Reference answer: 直属主管
- Expected policy IDs: hr-training
- Restricted policy ID: (none)

Citations returned:

- `hr-training` (员工培训费用支持办法 / 费用上限): 与岗位直接相关的外部课程，每名员工每自然年可报销不超过三千元；报名之前应取得主管批准。

Reference policy excerpts:

- `hr-training` 员工培训费用支持办法
  - 费用上限: 与岗位直接相关的外部课程，每名员工每自然年可报销不超过三千元；报名之前应取得主管批准。
  - 报销材料: 课程结束后十个工作日内提交发票、课程证明和学习总结，财务按年度余额核销。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 7. `6887afe40a013509`

- Category / user: `single_document` / `admin`
- Question: 培训结束后多久提交报销材料？
- Model status: `answered`
- Model answer: 根据编号资料[1]，培训结束后十个工作日内提交发票、课程证明和学习总结。
- Reference answer: 十个工作日内
- Expected policy IDs: hr-training
- Restricted policy ID: (none)

Citations returned:

- `hr-training` (员工培训费用支持办法 / 报销材料): 课程结束后十个工作日内提交发票、课程证明和学习总结，财务按年度余额核销。

Reference policy excerpts:

- `hr-training` 员工培训费用支持办法
  - 费用上限: 与岗位直接相关的外部课程，每名员工每自然年可报销不超过三千元；报名之前应取得主管批准。
  - 报销材料: 课程结束后十个工作日内提交发票、课程证明和学习总结，财务按年度余额核销。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 8. `de30ee343ff9a812`

- Category / user: `single_document` / `admin`
- Question: 费用报销应在发生后多久提交？
- Model status: `answered`
- Model answer: 费用发生后三十个自然日内提交报销单和合规票据。[1]
- Reference answer: 三十个自然日内
- Expected policy IDs: fin-expense
- Restricted policy ID: (none)

Citations returned:

- `fin-expense` (): 员工费用报销细则 提交时限 费用发生后三十个自然日内提交报销单和合规票据。逾期须说明原因并由部门负责人批准。 审批分级 单笔超过三千元须经财务复核；单笔超过一万元还须财务负责人批准。拆分报销以规避审批 禁止。

Reference policy excerpts:

- `fin-expense` 员工费用报销细则
  - 提交时限: 费用发生后三十个自然日内提交报销单和合规票据。逾期须说明原因并由部门负责人批准。
  - 审批分级: 单笔超过三千元须经财务复核；单笔超过一万元还须财务负责人批准。拆分报销以规避审批禁止。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 9. `0c3fb7fa9db05cb9`

- Category / user: `single_document` / `admin`
- Question: 单笔四千元报销由谁复核？
- Model status: `answered`
- Model answer: 单笔四千元报销须经财务复核。[1]
- Reference answer: 财务复核
- Expected policy IDs: fin-expense
- Restricted policy ID: (none)

Citations returned:

- `fin-expense` (): 员工费用报销细则 提交时限 费用发生后三十个自然日内提交报销单和合规票据。逾期须说明原因并由部门负责人批准。 审批分级 单笔超过三千元须经财务复核；单笔超过一万元还须财务负责人批准。拆分报销以规避审批 禁止。

Reference policy excerpts:

- `fin-expense` 员工费用报销细则
  - 提交时限: 费用发生后三十个自然日内提交报销单和合规票据。逾期须说明原因并由部门负责人批准。
  - 审批分级: 单笔超过三千元须经财务复核；单笔超过一万元还须财务负责人批准。拆分报销以规避审批禁止。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 10. `c4203f0ef198debf`

- Category / user: `single_document` / `admin`
- Question: 供应商付款申请需要哪些附件？
- Model status: `answered`
- Model answer: 根据编号资料[1]，供应商付款申请需要附合同、验收记录及发票。
- Reference answer: 合同、验收记录及发票
- Expected policy IDs: fin-payment
- Restricted policy ID: (none)

Citations returned:

- `fin-payment` (供应商付款审批规则 / 付款依据): 付款申请应附合同、验收记录及发票，财务核对收款账户与合同账户一致后才能排款。

Reference policy excerpts:

- `fin-payment` 供应商付款审批规则
  - 付款依据: 付款申请应附合同、验收记录及发票，财务核对收款账户与合同账户一致后才能排款。
  - 大额付款: 单笔超过五万元的付款需业务负责人和财务负责人双重批准，出纳不得自行修改收款账户。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 11. `9ef7edd2438fa805`

- Category / user: `single_document` / `admin`
- Question: 超过五万元付款由谁批准？
- Model status: `answered`
- Model answer: 根据编号资料[1]，单笔超过五万元的付款需业务负责人和财务负责人双重批准。
- Reference answer: 业务负责人和财务负责人
- Expected policy IDs: fin-payment
- Restricted policy ID: (none)

Citations returned:

- `fin-payment` (供应商付款审批规则 / 大额付款): 单笔超过五万元的付款需业务负责人和财务负责人双重批准，出纳不得自行修改收款账户。

Reference policy excerpts:

- `fin-payment` 供应商付款审批规则
  - 付款依据: 付款申请应附合同、验收记录及发票，财务核对收款账户与合同账户一致后才能排款。
  - 大额付款: 单笔超过五万元的付款需业务负责人和财务负责人双重批准，出纳不得自行修改收款账户。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 12. `20a0362c6e5fd25f`

- Category / user: `single_document` / `admin`
- Question: 出纳能自行修改供应商收款账户吗？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 不能
- Expected policy IDs: fin-payment
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- `fin-payment` 供应商付款审批规则
  - 付款依据: 付款申请应附合同、验收记录及发票，财务核对收款账户与合同账户一致后才能排款。
  - 大额付款: 单笔超过五万元的付款需业务负责人和财务负责人双重批准，出纳不得自行修改收款账户。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 13. `58c95504f4d28a5d`

- Category / user: `single_document` / `admin`
- Question: 下季度预算何时提交？
- Model status: `answered`
- Model answer: 下季度预算应在每季度结束前十个工作日提交 [1]。
- Reference answer: 本季度结束前十个工作日
- Expected policy IDs: fin-budget
- Restricted policy ID: (none)

Citations returned:

- `fin-budget` (季度预算调整流程 / 预算申报): 各部门在每季度结束前十个工作日提交下季度预算，列明项目、金额和责任人。

Reference policy excerpts:

- `fin-budget` 季度预算调整流程
  - 预算申报: 各部门在每季度结束前十个工作日提交下季度预算，列明项目、金额和责任人。
  - 超预算处理: 同一预算项目预计超支超过百分之十时，应在支出发生前取得财务负责人批准并更新预算记录。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 14. `c6407da1cc843f50`

- Category / user: `single_document` / `admin`
- Question: 供应商风险复核有效期多久？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 一年
- Expected policy IDs: proc-supplier
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- `proc-supplier` 供应商准入管理规范
  - 准入材料: 新供应商需提交营业执照、收款账户证明及至少三个客户参考案例。采购部核对主体与账户一致性。
  - 风险复核: 合规岗完成制裁名单与利益冲突核查后方可启用供应商编码；复核有效期为一年。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 15. `7a9a3ad04d4836a2`

- Category / user: `single_document` / `admin`
- Question: 可以先签采购合同再补审批吗？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 不可以
- Expected policy IDs: proc-contract
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- `proc-contract` 采购合同评审流程
  - 法务评审: 采购合同总金额超过五万元或包含数据处理条款时，签署前必须经法务评审。
  - 签署顺序: 合同审批通过后由授权签字人签署；任何人不得先签字后补流程，合同扫描件须归档。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 16. `aea9461a47c4f29b`

- Category / user: `single_document` / `admin`
- Question: 五千元以内紧急采购多久补审批？
- Model status: `answered`
- Model answer: 根据编号资料[1]，单笔五千元以内的紧急采购可先由值班负责人确认，然后在二十四小时内补交采购负责人审批。
- Reference answer: 二十四小时内
- Expected policy IDs: proc-emergency
- Restricted policy ID: (none)

Citations returned:

- `proc-emergency` (紧急采购例外办法 / 事后复核): 单笔五千元以内的紧急采购可先由值班负责人确认，二十四小时内补交采购负责人审批。

Reference policy excerpts:

- `proc-emergency` 紧急采购例外办法
  - 适用场景: 生产中断或重大安全故障可启动紧急采购，申请人须记录事件编号、预计金额和无法常规采购的原因。
  - 事后复核: 单笔五千元以内的紧急采购可先由值班负责人确认，二十四小时内补交采购负责人审批。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 17. `33e105a4b0dd2313`

- Category / user: `single_document` / `admin`
- Question: 生产系统权限默认有效期多久？
- Model status: `answered`
- Model answer: 生产系统权限默认有效期九十天 [1]。
- Reference answer: 九十天
- Expected policy IDs: it-access
- Restricted policy ID: (none)

Citations returned:

- `it-access` (系统账号与权限管理 / 开通与期限): 生产系统权限由直属主管和系统负责人批准，默认有效期九十天；到期须重新申请。

Reference policy excerpts:

- `it-access` 系统账号与权限管理
  - 开通与期限: 生产系统权限由直属主管和系统负责人批准，默认有效期九十天；到期须重新申请。
  - 离职撤销: 人事部发出离职通知后，IT 值班人员须在四小时内撤销生产系统账号和 VPN 权限。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 18. `c3706830cb3ee95f`

- Category / user: `single_document` / `admin`
- Question: 离职通知后多久撤销生产账号？
- Model status: `answered`
- Model answer: 根据编号资料[1]，人事部发出离职通知后，IT值班人员须在四小时内撤销生产系统账号和VPN权限。
- Reference answer: 四小时内
- Expected policy IDs: it-access
- Restricted policy ID: (none)

Citations returned:

- `it-access` (系统账号与权限管理 / 离职撤销): 人事部发出离职通知后，IT 值班人员须在四小时内撤销生产系统账号和 VPN 权限。

Reference policy excerpts:

- `it-access` 系统账号与权限管理
  - 开通与期限: 生产系统权限由直属主管和系统负责人批准，默认有效期九十天；到期须重新申请。
  - 离职撤销: 人事部发出离职通知后，IT 值班人员须在四小时内撤销生产系统账号和 VPN 权限。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 19. `de27ce4c58a381c0`

- Category / user: `single_document` / `admin`
- Question: 设备丢失后多久上报？
- Model status: `answered`
- Model answer: 设备丢失应在发现后一小时内报告 IT 服务台和信息安全岗，说明设备编号及最后使用地点。[1]
- Reference answer: 一小时内
- Expected policy IDs: it-device
- Restricted policy ID: (none)

Citations returned:

- `it-device` (): 办公设备与介质使用规定 设备保护 公司笔记本必须开启全盘加密和自动锁屏；禁止使用未经批准的移动存储设备复制工作资料。 遗失上报 设备丢失应在发现后一小时内报告 IT 服务台和信息安全岗，说明设备编号及最后使用地点。

Reference policy excerpts:

- `it-device` 办公设备与介质使用规定
  - 设备保护: 公司笔记本必须开启全盘加密和自动锁屏；禁止使用未经批准的移动存储设备复制工作资料。
  - 遗失上报: 设备丢失应在发现后一小时内报告 IT 服务台和信息安全岗，说明设备编号及最后使用地点。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 20. `9d08d1760ea48337`

- Category / user: `single_document` / `admin`
- Question: VPN 账号可以共享吗？
- Model status: `answered`
- Model answer: 根据编号资料 [1]，远程接入公司网络必须启用多因素认证，不得共享 VPN 账号或将令牌交给他人。
- Reference answer: 不可以
- Expected policy IDs: it-vpn
- Restricted policy ID: (none)

Citations returned:

- `it-vpn` (远程接入与 VPN 规范 / 登录控制): 远程接入公司网络必须启用多因素认证，不得共享 VPN 账号或将令牌交给他人。

Reference policy excerpts:

- `it-vpn` 远程接入与 VPN 规范
  - 登录控制: 远程接入公司网络必须启用多因素认证，不得共享 VPN 账号或将令牌交给他人。
  - 境外接入: 员工因公境外接入应至少提前五个工作日向信息安全岗报备访问国家与时段。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 21. `504a51aa8cac77a0`

- Category / user: `single_document` / `admin`
- Question: 变更申请单必须包含什么？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 回滚方案与验证人
- Expected policy IDs: it-change
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- `it-change` 生产系统变更管理
  - 常规窗口: 常规生产变更安排在每周三二十点至二十二点，申请单必须包含回滚方案与验证人。
  - 紧急变更: 紧急变更可由值班经理先授权实施，实施后二十四小时内补交变更委员会复盘记录。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 22. `177521f963c74ff5`

- Category / user: `single_document` / `admin`
- Question: P1 故障多久更新一次进展？
- Model status: `answered`
- Model answer: P1 故障每三十分钟更新一次进展。[1]
- Reference answer: 每三十分钟
- Expected policy IDs: it-incident
- Restricted policy ID: (none)

Citations returned:

- `it-incident` (信息系统故障响应分级 / 进展通报): P1 处置期间每三十分钟更新一次进展；恢复后两个工作日内完成事故复盘。

Reference policy excerpts:

- `it-incident` 信息系统故障响应分级
  - 一级故障: 核心业务不可用属于 P1，值班人员应在发现后十五分钟内通知应急负责人。
  - 进展通报: P1 处置期间每三十分钟更新一次进展；恢复后两个工作日内完成事故复盘。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 23. `62c940dceff2e746`

- Category / user: `single_document` / `admin`
- Question: 受限数据能上传公共云盘吗？
- Model status: `answered`
- Model answer: 根据编号资料[1]，受限数据不得上传公共云盘或发送个人邮箱。
- Reference answer: 不能
- Expected policy IDs: sec-classification
- Restricted policy ID: (none)

Citations returned:

- `sec-classification` (企业数据分级办法 / 受限数据): 受限数据不得上传公共云盘或发送个人邮箱；跨部门访问须由数据所有者和安全岗共同批准。

Reference policy excerpts:

- `sec-classification` 企业数据分级办法
  - 分级类别: 数据按公开、内部、机密、受限四级管理，文档所有者在创建时标注级别。
  - 受限数据: 受限数据不得上传公共云盘或发送个人邮箱；跨部门访问须由数据所有者和安全岗共同批准。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 24. `2569485aa190cff0`

- Category / user: `single_document` / `admin`
- Question: 可以用个人邮箱发送受限数据吗？
- Model status: `answered`
- Model answer: 不可以，受限数据不得上传公共云盘或发送个人邮箱。[1] 批准后使用加密链接并加水印，链接有效期最多七天，不得使用个人邮箱或公开分享链接。[2] 受限数据对外传输须由数据所有者、法务和信息安全岗联合批准。[3]
- Reference answer: 不可以
- Expected policy IDs: sec-export
- Restricted policy ID: (none)

Citations returned:

- `sec-classification` (企业数据分级办法 / 受限数据): 受限数据不得上传公共云盘或发送个人邮箱；跨部门访问须由数据所有者和安全岗共同批准。
- `sec-export` (受限数据对外传输审批 / 传输控制): 批准后使用加密链接并加水印，链接有效期最多七天；不得使用个人邮箱或公开分享链接。
- `sec-export` (受限数据对外传输审批 / 审批链): 受限数据对外传输须由数据所有者、法务和信息安全岗联合批准，申请中写明接收方与用途。

Reference policy excerpts:

- `sec-export` 受限数据对外传输审批
  - 审批链: 受限数据对外传输须由数据所有者、法务和信息安全岗联合批准，申请中写明接收方与用途。
  - 传输控制: 批准后使用加密链接并加水印，链接有效期最多七天；不得使用个人邮箱或公开分享链接。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 25. `26518917a2403ead`

- Category / user: `cross_document` / `admin`
- Question: 国内出差申请和出差费用报销分别有什么时限？
- Model status: `answered`
- Model answer: 国内出差申请应在出发前三个工作日提交 [1]。出差费用报销应在费用发生后三十个自然日内提交报销单和合规票据 [2]。
- Reference answer: 出发前三个工作日申请；费用发生后三十个自然日内报销。
- Expected policy IDs: hr-travel, fin-expense
- Restricted policy ID: (none)

Citations returned:

- `hr-travel` (国内出差申请制度 / 行程审批): 国内出差申请应在出发前三个工作日提交，说明目的、预算和目的地；直属主管和部门负责人依次审批。
- `fin-expense` (): 员工费用报销细则 提交时限 费用发生后三十个自然日内提交报销单和合规票据。逾期须说明原因并由部门负责人批准。 审批分级 单笔超过三千元须经财务复核；单笔超过一万元还须财务负责人批准。拆分报销以规避审批 禁止。

Reference policy excerpts:

- `hr-travel` 国内出差申请制度
  - 行程审批: 国内出差申请应在出发前三个工作日提交，说明目的、预算和目的地；直属主管和部门负责人依次审批。
  - 行程变更: 已批准的出差如增加城市或预算，须在订票前重新提交变更审批。紧急行程由部门负责人书面确认。
- `fin-expense` 员工费用报销细则
  - 提交时限: 费用发生后三十个自然日内提交报销单和合规票据。逾期须说明原因并由部门负责人批准。
  - 审批分级: 单笔超过三千元须经财务复核；单笔超过一万元还须财务负责人批准。拆分报销以规避审批禁止。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 26. `976a0dd6aab9839a`

- Category / user: `cross_document` / `admin`
- Question: 采购到货后申请供应商付款，需要怎样验收并附哪些材料？
- Model status: `answered`
- Model answer: 由需求部门与采购部各派一人共同验收，记录数量、型号和外观。[3] 发现数量或型号差异时，应在两个工作日内书面通知供应商，未确认差异前不得办理付款。[1] 付款申请应附合同、验收记录及发票。[2]
- Reference answer: 需求部门和采购部双人验收；付款附合同、验收记录及发票。
- Expected policy IDs: proc-acceptance, fin-payment
- Restricted policy ID: (none)

Citations returned:

- `proc-acceptance` (采购到货验收标准 / 差异处理): 发现数量或型号差异时，应在两个工作日内书面通知供应商，未确认差异前不得办理付款。
- `fin-payment` (供应商付款审批规则 / 付款依据): 付款申请应附合同、验收记录及发票，财务核对收款账户与合同账户一致后才能排款。
- `proc-acceptance` (采购到货验收标准 / 双人验收): 设备和物料到货时由需求部门与采购部各派一人共同验收，记录数量、型号和外观。

Reference policy excerpts:

- `proc-acceptance` 采购到货验收标准
  - 双人验收: 设备和物料到货时由需求部门与采购部各派一人共同验收，记录数量、型号和外观。
  - 差异处理: 发现数量或型号差异时，应在两个工作日内书面通知供应商，未确认差异前不得办理付款。
- `fin-payment` 供应商付款审批规则
  - 付款依据: 付款申请应附合同、验收记录及发票，财务核对收款账户与合同账户一致后才能排款。
  - 大额付款: 单笔超过五万元的付款需业务负责人和财务负责人双重批准，出纳不得自行修改收款账户。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 27. `dcb32ebc19a99872`

- Category / user: `cross_document` / `admin`
- Question: 紧急生产变更引发 P1 故障，变更与事故各要多久补记录？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 紧急变更实施后二十四小时内补复盘记录；P1 恢复后两个工作日内完成事故复盘。
- Expected policy IDs: it-change, it-incident
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- `it-change` 生产系统变更管理
  - 常规窗口: 常规生产变更安排在每周三二十点至二十二点，申请单必须包含回滚方案与验证人。
  - 紧急变更: 紧急变更可由值班经理先授权实施，实施后二十四小时内补交变更委员会复盘记录。
- `it-incident` 信息系统故障响应分级
  - 一级故障: 核心业务不可用属于 P1，值班人员应在发现后十五分钟内通知应急负责人。
  - 进展通报: P1 处置期间每三十分钟更新一次进展；恢复后两个工作日内完成事故复盘。

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 28. `386999f0f6fede98`

- Category / user: `no_answer` / `admin`
- Question: 国内出差的每日住宿费上限是多少？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 国内出差制度没有规定住宿费上限。
- Expected policy IDs: (none)
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 29. `99b5a5edfaa1dff7`

- Category / user: `no_answer` / `admin`
- Question: 电子发票退回后第二次补正的期限是多久？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 电子发票制度没有规定第二次补正期限。
- Expected policy IDs: (none)
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 30. `76d3e4d6ffedad84`

- Category / user: `no_answer` / `admin`
- Question: 试用期的最长期限是几个月？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 新员工入职制度没有规定试用期期限。
- Expected policy IDs: (none)
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 31. `71137979062a2165`

- Category / user: `no_answer` / `admin`
- Question: 培训报销未用额度可以结转到下一年吗？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 培训费用制度没有规定额度结转。
- Expected policy IDs: (none)
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 32. `4451f77ae1ee36a6`

- Category / user: `no_answer` / `admin`
- Question: 系统访问日志具体保存在哪台服务器？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: 记录保存制度没有规定具体存储服务器。
- Expected policy IDs: (none)
- Restricted policy ID: (none)

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 33. `0f3b5f49384bd395`

- Category / user: `unauthorized` / `employee`
- Question: 两万元采购要找几家供应商报价？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: (not specified in the corpus)
- Expected policy IDs: (none)
- Restricted policy ID: proc-quote

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 34. `0217d11671eeb159`

- Category / user: `unauthorized` / `employee`
- Question: 新供应商至少提供几个客户案例？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: (not specified in the corpus)
- Expected policy IDs: (none)
- Restricted policy ID: proc-supplier

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 35. `9209f7b6e0e045a0`

- Category / user: `unauthorized` / `employee`
- Question: 常规生产变更安排在周几几点？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: (not specified in the corpus)
- Expected policy IDs: (none)
- Restricted policy ID: it-change

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 36. `c3f38d75fca15578`

- Category / user: `unauthorized` / `employee`
- Question: P1 故障应多久通知负责人？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: (not specified in the corpus)
- Expected policy IDs: (none)
- Restricted policy ID: it-incident

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]

### 37. `7ad8ac0d804fe811`

- Category / user: `unauthorized` / `employee`
- Question: 受限数据对外传输链接有效期最多多久？
- Model status: `insufficient_evidence`
- Model answer: (no answer returned)
- Reference answer: (not specified in the corpus)
- Expected policy IDs: (none)
- Restricted policy ID: sec-export

Citations returned:

- (none)

Reference policy excerpts:

- No expected policy. Check the full manifest before judging evidence absent.

Review notes:

- Question and reference label clear: [ ]
- Response or refusal correct: [ ]
- Every factual claim supported by its citation: [ ]
- Access control respected: [ ]
- Evidence and correction needed: [ ]
