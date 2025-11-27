#\!/bin/bash
# ==================== Vulcan Brain 服务器加固脚本 ====================
# ⚠️ 请逐步执行，不要一次性运行全部！

echo "=========================================="
echo "  Vulcan Brain 生产环境加固脚本"
echo "=========================================="

# 1. 防火墙配置
setup_firewall() {
    echo ""
    echo "[1/5] 配置 UFW 防火墙..."
    sudo ufw --force reset
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow 22/tcp comment "SSH"
    sudo ufw allow 3000/tcp comment "Next.js Frontend"
    sudo ufw allow 8001/tcp comment "Vulcan API"
    # 注意：不开放 27017 (MongoDB) 和 11434 (Ollama) 给外网！
    sudo ufw --force enable
    sudo ufw status verbose
    echo "✅ 防火墙配置完成"
}

# 2. PM2 开机自启
setup_pm2_startup() {
    echo ""
    echo "[2/5] 配置 PM2 开机自启..."
    pm2 startup systemd -u $USER --hp $HOME
    pm2 save
    echo "✅ PM2 自启配置完成"
}

# 3. 日志轮转
setup_logrotate() {
    echo ""
    echo "[3/5] 安装 PM2 日志轮转..."
    pm2 install pm2-logrotate
    pm2 set pm2-logrotate:max_size 50M
    pm2 set pm2-logrotate:retain 7
    pm2 set pm2-logrotate:compress true
    echo "✅ 日志轮转配置完成"
}

# 4. 备份定时任务
setup_backup_cron() {
    echo ""
    echo "[4/5] 配置每日备份定时任务..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    (crontab -l 2>/dev/null | grep -v "backup_mongo.sh"; echo "0 3 * * * $SCRIPT_DIR/backup_mongo.sh >> $HOME/backups/backup.log 2>&1") | crontab -
    echo "✅ 备份定时任务已添加 (每天凌晨3点)"
    crontab -l | grep backup
}

# 5. SSH 加固 (谨慎！确保 Key 能用再执行)
harden_ssh() {
    echo ""
    echo "[5/5] SSH 加固..."
    echo "⚠️  此操作会禁用密码登录，请确保 SSH Key 已配置！"
    read -p "确认继续? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        sudo sed -i s/#PasswordAuthentication yes/PasswordAuthentication no/ /etc/ssh/sshd_config
        sudo sed -i s/PasswordAuthentication yes/PasswordAuthentication no/ /etc/ssh/sshd_config
        sudo systemctl restart sshd
        echo "✅ SSH 密码登录已禁用"
    else
        echo "⏭️  跳过 SSH 加固"
    fi
}

# 显示菜单
echo ""
echo "请选择要执行的操作:"
echo "1) 配置防火墙 (UFW)"
echo "2) 配置 PM2 开机自启"
echo "3) 安装日志轮转"
echo "4) 配置备份定时任务"
echo "5) SSH 加固 (禁用密码登录)"
echo "A) 执行全部 (1-4，SSH需手动)"
echo "Q) 退出"
echo ""
read -p "输入选项: " choice

case $choice in
    1) setup_firewall ;;
    2) setup_pm2_startup ;;
    3) setup_logrotate ;;
    4) setup_backup_cron ;;
    5) harden_ssh ;;
    A|a) setup_firewall; setup_pm2_startup; setup_logrotate; setup_backup_cron ;;
    Q|q) echo "退出"; exit 0 ;;
    *) echo "无效选项" ;;
esac
