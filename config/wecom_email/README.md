# 企业微信邮箱 API 配置

## 目录结构
每个公司一个 JSON 配置文件：
- rongrongnm.json - 榕融新材料（广西）
- [company2].json - 待添加

## 配置字段说明
- corp_id: 企业ID
- agent_id: 应用ID  
- secret: 应用密钥
- domain: 公司域名（用于验证）
- trusted_ip: 服务器IP白名单
- status: pending_domain_verification / active

## API 调用流程
1. 域名验证（放 WW_verify_xxx.txt 文件）
2. 配置 IP 白名单
3. 在邮件模块授权应用
4. 调用邮件 API

## 待办
- [ ] 榕融: 等待域名验证文件部署
- [ ] 公司2: 待配置
