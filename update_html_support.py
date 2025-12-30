import re

# ========== 1. 更新 code_executor_api.py ==========
with open('/home/xinyue/vulcan-brain/code_executor_api.py', 'r') as f:
    code_exec = f.read()

# 添加 chart_html 到 CodeResult
code_exec = code_exec.replace(
    '''class CodeResult(BaseModel):
    success: bool
    image_base64: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None''',
    '''class CodeResult(BaseModel):
    success: bool
    image_base64: Optional[str] = None
    chart_html: Optional[str] = None  # 交互式Plotly HTML
    output: Optional[str] = None
    error: Optional[str] = None'''
)

# 修改保存逻辑 - 优先HTML
code_exec = code_exec.replace(
    '''    # 图表保存逻辑 - 同时支持matplotlib和plotly
    save_code = \'\'\'

# 自动保存图表 (同时支持matplotlib和plotly)
import os

# 方法1: 检查Plotly写入的图片文件
if os.path.exists('/tmp/chart.png'):
    with open('/tmp/chart.png', 'rb') as f:
        print("__CHART_BASE64__" + base64.b64encode(f.read()).decode())
else:
    # 方法2: 检查Matplotlib图表
    _fig = plt.gcf()
    if _fig.get_axes():  # 如果有matplotlib图表
        _buf = BytesIO()
        plt.savefig(_buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        _buf.seek(0)
        print("__CHART_BASE64__" + base64.b64encode(_buf.read()).decode())
        plt.close()
\'\'\'''',
    '''    # 图表保存逻辑 - 优先HTML交互式
    save_code = \'\'\'

# 自动保存图表 (优先交互式HTML)
import os

# 方法1: Plotly HTML (交互式)
if os.path.exists('/tmp/chart.html'):
    with open('/tmp/chart.html', 'r', encoding='utf-8') as f:
        print("__CHART_HTML__" + f.read())
# 方法2: Plotly PNG (静态备选)
elif os.path.exists('/tmp/chart.png'):
    with open('/tmp/chart.png', 'rb') as f:
        print("__CHART_BASE64__" + base64.b64encode(f.read()).decode())
else:
    # 方法3: Matplotlib图表
    _fig = plt.gcf()
    if _fig.get_axes():
        _buf = BytesIO()
        plt.savefig(_buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        _buf.seek(0)
        print("__CHART_BASE64__" + base64.b64encode(_buf.read()).decode())
        plt.close()
\'\'\''''
)

# 修改输出解析 - 支持HTML
code_exec = code_exec.replace(
    '''        # 4. 解析输出
        if '__CHART_BASE64__' in stdout:
            # 提取图表
            parts = stdout.split('__CHART_BASE64__')
            output_text = parts[0].strip()
            img_b64 = parts[1].strip()
            return CodeResult(
                success=True,
                image_base64=img_b64,
                output=output_text if output_text else None
            )''',
    '''        # 4. 解析输出
        # 优先检查交互式HTML
        if '__CHART_HTML__' in stdout:
            parts = stdout.split('__CHART_HTML__')
            output_text = parts[0].strip()
            html_content = parts[1]
            return CodeResult(
                success=True,
                chart_html=html_content,
                output=output_text if output_text else None
            )

        # 其次检查静态PNG
        if '__CHART_BASE64__' in stdout:
            parts = stdout.split('__CHART_BASE64__')
            output_text = parts[0].strip()
            img_b64 = parts[1].strip()
            return CodeResult(
                success=True,
                image_base64=img_b64,
                output=output_text if output_text else None
            )'''
)

with open('/home/xinyue/vulcan-brain/code_executor_api.py', 'w') as f:
    f.write(code_exec)
print("✅ code_executor_api.py 已更新")

# ========== 2. 更新 email_intel_agent_api.py ==========
with open('/home/xinyue/vulcan-brain/email_intel_agent_api.py', 'r') as f:
    agent_api = f.read()

# 添加 chart_html 到 AgentResponse
agent_api = agent_api.replace(
    '''class AgentResponse(BaseModel):
    answer: str
    session_id: str
    data: Optional[List] = None
    cypher: Optional[str] = None
    image: Optional[str] = None  # Base64图片
    python_code: Optional[str] = None''',
    '''class AgentResponse(BaseModel):
    answer: str
    session_id: str
    data: Optional[List] = None
    cypher: Optional[str] = None
    image: Optional[str] = None  # Base64图片
    chart_html: Optional[str] = None  # 交互式Plotly HTML
    python_code: Optional[str] = None'''
)

# 修改变量初始化
agent_api = agent_api.replace(
    '''    query_result = None
    image_base64 = None
    final_answer = llm_answer''',
    '''    query_result = None
    image_base64 = None
    chart_html = None
    final_answer = llm_answer'''
)

# 修改代码执行结果处理
agent_api = agent_api.replace(
    '''                if exec_result.get("success") and exec_result.get("image_base64"):
                    image_base64 = exec_result["image_base64"]
                    final_answer = "已为您生成图表。"''',
    '''                if exec_result.get("success"):
                    if exec_result.get("chart_html"):
                        chart_html = exec_result["chart_html"]
                        final_answer = "已为您生成交互式图表。"
                    elif exec_result.get("image_base64"):
                        image_base64 = exec_result["image_base64"]
                        final_answer = "已为您生成图表。"'''
)

# 修改返回结果
agent_api = agent_api.replace(
    '''    return AgentResponse(
        answer=final_answer,
        session_id=session_id,
        data=query_result[:20] if query_result else None,
        cypher=cypher,
        image=image_base64,
        python_code=python_code
    )''',
    '''    return AgentResponse(
        answer=final_answer,
        session_id=session_id,
        data=query_result[:20] if query_result else None,
        cypher=cypher,
        image=image_base64,
        chart_html=chart_html,
        python_code=python_code
    )'''
)

# 更新System Prompt - 使用交互式HTML
new_prompt = '''SYSTEM_PROMPT = """你是VSG公司的邮件数据分析助手。你可以：
1. 执行Cypher查询来回答数据问题
2. 生成Python代码绘制可视化图表

## 重要规则
1. **必须执行查询**：任何涉及数据的问题，必须先输出Cypher查询
2. **不要猜测数据**：所有数据必须来自查询结果
3. **可视化请求**：当用户要求"画图/图表/可视化"时，先查询数据，再生成Python绘图代码

## 数据库信息
- 数据库: KuzuDB (图数据库)
- 主要节点: BusinessEvent
- 有效事件类型: Payment(付款), Order(订单), Quotation(报价), Shipment(物流), Contract(合同)
- **重要**: 查询时必须排除脏数据，添加 WHERE e.event_type IN ['Payment', 'Order', 'Quotation', 'Shipment', 'Contract']

## ⚠️ 维度选择智能 (非常重要!)

### 场景1: 跨类型总览分析
当用户问"业务数据/所有事件/整体情况"等**不指定特定事件类型**时：
- ✅ 推荐: 按 event_type 分布（对比4种业务类型的数量/金额）

### 场景2: 单类型深入分析
当用户指定"物流/订单/付款/合同/报价"等**特定事件类型**时：

**❌ 绝对避免**: status, currency (数据极度不均匀)

**✅ 推荐维度**:
- Shipment物流: counterparty_role, direction, counterparty
- Contract合同: amount, direction, counterparty_role
- Order订单: counterparty, amount, counterparty_role
- Quotation报价: counterparty_role, event_date, counterparty
- Payment付款: counterparty_role, amount, direction

## Cypher查询格式 (必须用代码块!)
```cypher
MATCH (e:BusinessEvent)
WHERE e.event_type = 'Shipment'
RETURN e.counterparty_role, count(*) as count
ORDER BY count DESC
```

## KuzuDB 特殊语法
- **不要使用 GROUP BY**: 聚合是隐式的

## 绘图代码规则 (非常重要!)
1. **df已经存在**: 不要重新定义df!
2. **必须保存到/tmp/chart.html**: 用fig.write_html()生成交互式图表
3. **必须用```python代码块包裹!**

## Plotly交互式图表示例
```python
import plotly.express as px
fig = px.bar(df, x='event_type', y='count', color='event_type',
             title='业务事件分布', color_discrete_sequence=px.colors.qualitative.Set2)
fig.update_layout(xaxis_tickangle=-45)
fig.write_html('/tmp/chart.html', include_plotlyjs='cdn')
```

```python
import plotly.express as px
fig = px.pie(df, values='count', names='counterparty_role', title='交易对手角色分布', hole=0.4)
fig.write_html('/tmp/chart.html', include_plotlyjs='cdn')
```

请用简洁的中文回答，代码必须用markdown代码块格式输出！"""'''

pattern = r'SYSTEM_PROMPT = """.*?"""'
agent_api = re.sub(pattern, new_prompt, agent_api, flags=re.DOTALL)

with open('/home/xinyue/vulcan-brain/email_intel_agent_api.py', 'w') as f:
    f.write(agent_api)
print("✅ email_intel_agent_api.py 已更新")

print("\n🎉 后端修改完成！")
