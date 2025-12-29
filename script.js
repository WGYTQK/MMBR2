// 打字机效果实现
let agentOutputBuffer = "";
let isTyping = false;
let typingInterval;
let optionsCheckInterval;
let currentConversationId = null;
// 添加全局状态变量
let isShowingOptions = false;
let pendingMessage = null;
// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// 打字机效果
function typeWriter(content, isNewMessage = true) {
    if (isTyping) {
        clearInterval(typingInterval);
        isTyping = false;
    }

    const outputEl = document.getElementById('agent-output');
    const timestamp = new Date().toLocaleString();

    if (isNewMessage) {
        // 添加消息分隔线
        const separator = document.createElement('div');
        separator.className = 'message-separator';
        outputEl.appendChild(separator);

        // 添加到历史记录
        addToHistory(timestamp, content);
    }

    // 创建消息容器
    const messageBlock = document.createElement('div');
    messageBlock.className = 'message-block';
    outputEl.appendChild(messageBlock);

    let i = 0;
    isTyping = true;

    typingInterval = setInterval(() => {
        if (i < content.length) {
            messageBlock.textContent += content.charAt(i);
            i++;
        } else {
            clearInterval(typingInterval);
            isTyping = false;
        }
        outputEl.scrollTop = outputEl.scrollHeight;
    }, 30);
}

// 显示带选项的消息
function displayMessageWithOptions(data) {
    const outputEl = document.getElementById('agent-output');

    // 检查是否已存在相同问题
    const existingQuestions = document.querySelectorAll('.message-question');
    const isDuplicate = Array.from(existingQuestions).some(el =>
        el.textContent === data.question
    );

    if (isDuplicate) return;

    // 创建消息容器
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-with-options';

    // 添加消息内容
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = `${data.timestamp}: ${data.message}`;
    messageDiv.appendChild(contentDiv);

    // 添加问题
    const questionDiv = document.createElement('div');
    questionDiv.className = 'message-question';
    questionDiv.textContent = data.question;
    messageDiv.appendChild(questionDiv);

    // 添加选项容器
    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'options-container';

    // 添加各个选项按钮
    data.options.forEach(option => {
        const button = document.createElement('button');
        button.className = 'option-button';
        button.textContent = option.text;
        button.dataset.value = option.value;
        button.addEventListener('click', () => {
            handleOptionSelection(option.value, option.text);
        });
        optionsContainer.appendChild(button);
    });

    messageDiv.appendChild(optionsContainer);
    outputEl.appendChild(messageDiv);
    outputEl.scrollTop = outputEl.scrollHeight;
}
// 添加按钮锁定和解锁功能
function lockUI(lock = true) {
    const elements = [
        '#send-button',
        '#message-input',
        '#meeting-date',
        '#meeting-time',
        '#meeting-type',
        '#meeting-topic',
        '#meeting-attendees',
        '.option-button',
        '#reset-button'
    ];

    elements.forEach(selector => {
        const el = document.querySelector(selector);
        if (el) {
            el.disabled = lock;
            if (lock) {
                el.classList.add('disabled-ui');
            } else {
                el.classList.remove('disabled-ui');
            }
        }
    });
}

function handleOptionSelection(value, text) {
    // 禁用所有选项按钮
    document.querySelectorAll('.option-button').forEach(btn => {
        btn.disabled = true;
        if (btn.dataset.value === value) {
            btn.classList.add('selected');
        }
    });

    // 添加自动发送指示器
    const indicator = document.createElement('span');
    indicator.className = 'auto-send-indicator';
    indicator.textContent = '(自动发送中...)';
    document.querySelector('.selected').appendChild(indicator);

    // 直接发送消息（添加防抖）
    setTimeout(() => {
        const input = document.getElementById('message-input');
        input.value = text;
        sendMessage(true);
    }, 300); // 300ms防抖，避免多次触发
}

// 检查选项
function checkForOptions() {
    // 如果正在显示选项，则不再检查新选项
    if (isShowingOptions) return;

    fetch('/api/options')
        .then(response => {
            if (!response.ok) throw new Error(`HTTP错误: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.status === "options") {
                // 设置正在显示选项状态
                isShowingOptions = true;

                if (isTyping) {
                    clearInterval(typingInterval);
                    isTyping = false;
                    const outputEl = document.getElementById('agent-output');
                    agentOutputBuffer = outputEl.textContent;
                }

                if (data.type === "0") {
                    handleUpdateData(data.update_data);
                    isShowingOptions = false; // 更新数据不需要保持选项状态
                } else if (data.type === "1") {
                    handleQuestionOptions(data);
                }
            }
        })
        .catch(error => {
            console.error('获取选项失败:', error);
        });
}

// 处理问题选项
function handleQuestionOptions(data) {
    displayMessageWithOptions(data);
    const outputEl = document.getElementById('agent-output');
    outputEl.scrollTop = outputEl.scrollHeight;
}

// 处理更新数据
function handleUpdateData(updateData) {
    if (!updateData) return;

    // 更新表单字段
    const fields = {
        'meeting-date': updateData.date,
        'meeting-time': updateData.time,
        'meeting-type': updateData.type,
        'meeting-topic': updateData.topic,
        'meeting-attendees': updateData.attendees
    };

    Object.entries(fields).forEach(([id, value]) => {
        if (value) {
            const el = document.getElementById(id);
            if (el) {
                el.value = value;
                // 添加视觉反馈
                el.classList.add('field-updated');
                setTimeout(() => el.classList.remove('field-updated'), 1000);
            }
        }
    });

    // 显示更新通知
    showUpdateNotification(updateData);
}

// 显示更新通知
function showUpdateNotification(data) {
    const outputEl = document.getElementById('agent-output');
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // 创建紧凑的通知元素
    const notice = document.createElement('div');
    notice.className = 'update-notice';

    // 构建详情HTML
    let detailsHtml = '';
    if (data.date) detailsHtml += `<div>会议日期: ${data.date}</div>`;
    if (data.time) detailsHtml += `<div>会议时间区间: ${data.time}</div>`;
    if (data.type) detailsHtml += `<div>会议形式: ${data.type}</div>`;
    if (data.topic) detailsHtml += `<div>会议主题: ${data.topic}</div>`;
    if (data.attendees) detailsHtml += `<div>与会人员: ${data.attendees}</div>`;

    notice.innerHTML = `
        <strong>会议更新</strong>
        <div class="update-details">
            ${detailsHtml}
        </div>
    `;

    // 插入到输出区域顶部（最新消息在最上面）
    if (outputEl.firstChild) {
        outputEl.insertBefore(notice, outputEl.firstChild);
    } else {
        outputEl.appendChild(notice);
    }
}

// 显示Toast通知
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container') || document.body;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// 发送消息
const debouncedSend = debounce(sendMessage, 300);

function sendMessage(isAutoSend = false) {

    // 如果有待处理消息，使用它
    if (pendingMessage) {
        const input = document.getElementById('message-input');
        input.value = pendingMessage.text;
        pendingMessage = null;
    }

    const input = document.getElementById('message-input');
    const message = input.value.trim();
    const sendBtn = document.getElementById('send-button');

    if (!message) {
        showToast('请输入消息内容', 'warning');
        return;
    }

    // 显示加载动画
    sendBtn.classList.add('loading');
    sendBtn.disabled = true;
    input.disabled = true;

    updateStatus("处理中...");

    // 获取会议信息
    const meetingDate = document.getElementById('meeting-date').value;
    const meetingTime = document.getElementById('meeting-time').value;
    const meetingType = document.getElementById('meeting-type').value;
    const meetingTopic = document.getElementById('meeting-topic').value;
    const meetingAttendees = document.getElementById('meeting-attendees').value;

    // 构建包含会议信息的消息
    const fullMessage = `会议信息: 日期: ${meetingDate} 时间: ${meetingTime} 形式: ${meetingType} 主题: ${meetingTopic} 与会人员: ${meetingAttendees}

用户需求: ${isAutoSend ? `[自动选择] ${message}` : message}`;
    lockUI(true);
    fetch('/post', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: fullMessage,
            meeting_info: {
                date: meetingDate,
                time: meetingTime,
                type: meetingType,
                topic: meetingTopic,
                attendees: meetingAttendees
            },
            conversation_id: currentConversationId
        })
    })
    .then(response => {
        if (!response.ok) throw new Error(`HTTP错误: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.status === "success") {
            if (!currentConversationId) {
                currentConversationId = data.conversation_id;
            }
            typeWriter(`${data.timestamp}: ${data.message}\n`, false);
            addToHistory(data.timestamp, data.message);
            if (!isAutoSend) {
                input.value = '';
            }
            showToast('消息发送成功', 'success');
        } else {
            updateStatus(`错误: ${data.message}`, true);
            addToHistory(data.timestamp, `[错误] ${data.message}`);
            showToast(data.message, 'error');
        }
    })
    .catch(error => {
        updateStatus(`请求失败: ${error.message}`, true);
        const timestamp = new Date().toLocaleString();
        addToHistory(timestamp, `[网络错误] ${error.message}`);
        showToast(`发送失败: ${error.message}`, 'error');
    })
    .finally(() => {
        // 恢复按钮状态
        sendBtn.classList.remove('loading');
        sendBtn.disabled = false;
        input.disabled = false;
        input.focus();
        updateStatus("准备就绪");
        lockUI(false);
    });
}
// 页面刷新处理
window.addEventListener('beforeunload', () => {
    fetch('/reset', { method: 'POST' });  // 静默重置
    clearInterval(optionsCheckInterval);
});
// 添加到历史消息
function addToHistory(timestamp, message) {
    const historyDiv = document.getElementById('message-history');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message-item';
    msgDiv.textContent = `${timestamp}: ${message}`;
    historyDiv.appendChild(msgDiv);
    historyDiv.scrollTop = historyDiv.scrollHeight;
}

// 更新状态显示
function updateStatus(text, isError = false) {
    const el = document.getElementById('status');
    el.textContent = `状态: ${text}`;
    el.style.color = isError ? 'red' : '#0066cc';
}

// 创建装饰气泡
function createDecorativeBubbles() {
    const container = document.getElementById('bubbles-container');
    const phrases = [
        "今天下午三点到四点和毛裤侠开会吧",
        "明天上午10点可以预约B栋会议室",
        "会议时长建议控制在1小时内",
        "早上8点前的会议需要特别留意",
        "可以选择Webex线上会议",
        "预约B栋会议室",
        "支持随机分配空闲会议室",
        "输入'帮助'查看所有功能",
        "支持添加会议提醒功能",
        "周末不可以开会，注意休息哦",
        "会议前会发送提醒",
        "记得提前测试会议设备"
    ];

    // 创建初始气泡
    for (let i = 0; i < 8; i++) {
        createBubble(container, phrases, i * 300);
    }

    // 持续创建新气泡
    setInterval(() => {
        createBubble(container, phrases);
    }, 8000);
}

function createBubble(container, phrases, delay = 0) {
    setTimeout(() => {
        const bubble = document.createElement('div');
        bubble.className = 'bubble';

        // 随机位置和动画时间
        bubble.style.left = `${Math.random() * 100}%`;
        bubble.style.bottom = '-20px';
        bubble.style.animationDuration = `${10 + Math.random() * 10}s`;

        bubble.textContent = phrases[Math.floor(Math.random() * phrases.length)];
        container.appendChild(bubble);

        // 气泡生命周期管理
        const timeout = setTimeout(() => {
            bubble.remove();
        }, 15000);

        bubble.addEventListener('animationend', () => {
            clearTimeout(timeout);
            bubble.remove();
        });
    }, delay);
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    createDecorativeBubbles();

    // 设置事件监听
    document.getElementById('send-button').addEventListener('click', debouncedSend);
    document.getElementById('message-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') debouncedSend();
    });

    // 历史消息切换
    const historyToggle = document.getElementById('history-toggle');
    const historyContainer = document.getElementById('history-container');
    const historyContent = document.getElementById('message-history');

    historyToggle.addEventListener('click', function() {
        const isExpanded = historyContainer.classList.toggle('expanded');
        this.querySelector('.expand-icon').textContent = isExpanded ? '▲' : '▼';
        if (isExpanded) {
            historyContent.scrollTop = historyContent.scrollHeight;
        }
    });

    // 滚动到底部按钮
    const outputEl = document.getElementById('agent-output');
    const scrollDownBtn = document.createElement('button');
    scrollDownBtn.id = 'scroll-down-btn';
    scrollDownBtn.textContent = '▼ 查看最新';
    scrollDownBtn.style.display = 'none';
    scrollDownBtn.addEventListener('click', () => {
        outputEl.scrollTop = outputEl.scrollHeight;
        scrollDownBtn.style.display = 'none';
    });

    outputEl.parentNode.appendChild(scrollDownBtn);

    // 监听滚动事件
    outputEl.addEventListener('scroll', () => {
        const isAtBottom = outputEl.scrollHeight - outputEl.scrollTop === outputEl.clientHeight;
        scrollDownBtn.style.display = isAtBottom ? 'none' : 'block';
    });

    // 启动选项检查轮询
    optionsCheckInterval = setInterval(checkForOptions, 3000);
});

// 清理定时器
window.addEventListener('beforeunload', () => {
    clearInterval(optionsCheckInterval);
});
