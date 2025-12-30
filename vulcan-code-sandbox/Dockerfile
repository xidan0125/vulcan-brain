# Vulcan Code Sandbox - 安全的Python代码执行环境
FROM python:3.12-slim

# 安装中文字体支持
RUN apt-get update && apt-get install -y --no-install-recommends     fonts-wqy-microhei     && rm -rf /var/lib/apt/lists/*

# 只安装白名单库（固定版本）
# 升级版：添加 plotly + pyecharts 炫酷可视化
RUN pip install --no-cache-dir     matplotlib==3.8.2     pandas==2.1.4     numpy==1.26.2     seaborn==0.13.0     plotly==5.24.1     kaleido==0.2.1     pyecharts==2.0.6

# 配置matplotlib使用中文字体
RUN mkdir -p /root/.config/matplotlib &&     echo "font.sans-serif: WenQuanYi Micro Hei, DejaVu Sans" > /root/.config/matplotlib/matplotlibrc &&     echo "axes.unicode_minus: False" >> /root/.config/matplotlib/matplotlibrc

# 创建非root用户
RUN useradd -m -s /bin/bash sandbox
USER sandbox
WORKDIR /home/sandbox

# 禁止安装新包
ENV PIP_NO_INDEX=1
ENV MPLCONFIGDIR=/tmp/matplotlib

CMD ["python3"]
