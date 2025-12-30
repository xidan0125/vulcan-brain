import re

with open('/home/xinyue/vulcan-brain/email_intel_agent_api.py', 'r') as f:
    content = f.read()

# 找到绘图示例部分并替换为更好看的样式
old_examples = '''## Plotly交互式图表示例
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
```'''

new_examples = '''## Plotly交互式图表示例 (必须用这个美化配置!)

柱状图模板:
```python
import plotly.express as px
fig = px.bar(df, x='counterparty_role', y='count', color='counterparty_role',
             title='物流交易对手角色分布',
             color_discrete_sequence=['#10b981', '#f97316', '#6366f1', '#ec4899', '#eab308'])
fig.update_layout(
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(family='Arial', size=14),
    title=dict(font=dict(size=18, color='#1f2937')),
    xaxis=dict(title='', tickangle=0, showgrid=False),
    yaxis=dict(title='数量', showgrid=True, gridcolor='#f3f4f6'),
    showlegend=False,
    margin=dict(l=60, r=40, t=60, b=60)
)
fig.write_html('/tmp/chart.html', include_plotlyjs='cdn')
```

饼图/环形图模板:
```python
import plotly.express as px
fig = px.pie(df, values='count', names='event_type', title='业务事件分布', hole=0.45,
             color_discrete_sequence=['#10b981', '#f97316', '#6366f1', '#ec4899', '#eab308'])
fig.update_layout(
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(family='Arial', size=14),
    title=dict(font=dict(size=18, color='#1f2937')),
    margin=dict(l=20, r=20, t=60, b=20)
)
fig.update_traces(textposition='inside', textinfo='percent+label')
fig.write_html('/tmp/chart.html', include_plotlyjs='cdn')
```'''

content = content.replace(old_examples, new_examples)

with open('/home/xinyue/vulcan-brain/email_intel_agent_api.py', 'w') as f:
    f.write(content)

print('Updated Plotly style templates!')
