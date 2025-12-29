// ====== 全局变量 ======
let agentOutputBuffer = "";
let isTyping = false;
let typingInterval;
let optionsCheckInterval;
let currentConversationId = null;
let isShowingOptions = false;
let pendingMessage = null;
let isProcessing = false;
let processedOptionIds = new Set();

// ====== 工具函数 ======
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function updateStatus(text, isError = false) {
    const el = document.getElementById('status');
    if (!el) return;

    el.innerHTML = `状态: <span class="status-text ${isError ? 'error' : 'ready'}">${text}</span>`;
}

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
        '#reset-btn'
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

// ====== 消息处理 ======
function typeWriter(content, isNewMessage = true) {
    if (isTyping) {
        clearInterval(typingInterval);
        isTyping = false;
    }

    const outputEl = document.getElementById('agent-output');
    if (!outputEl) return;

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (isNewMessage) {
        addToHistory(timestamp, content);
    }

    const messageBlock = document.createElement('div');
    messageBlock.className = 'message-block';
    messageBlock.innerHTML = `<div class="message-timestamp">${timestamp}</div><div class="message-content">${content}</div>`;
    outputEl.appendChild(messageBlock);

    if (isNewMessage && !content.includes('[自动选择]')) {
        const contentDiv = messageBlock.querySelector('.message-content');
        const originalText = contentDiv.textContent;
        contentDiv.textContent = '';

        let i = 0;
        isTyping = true;

        typingInterval = setInterval(() => {
            if (i < originalText.length) {
                contentDiv.textContent += originalText.charAt(i);
                i++;
                outputEl.scrollTop = outputEl.scrollHeight;
            } else {
                clearInterval(typingInterval);
                isTyping = false;
            }
        }, 30);
    } else {
        outputEl.scrollTop = outputEl.scrollHeight;
    }
}

function displayMessageWithOptions(data) {
    const outputEl = document.getElementById('agent-output');
    if (!outputEl) return;

    // 生成更唯一ID
    const optionId = `option_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // 更严格的重复检查
    if (processedOptionIds.has(optionId)) {
        console.log('选项已处理过，跳过显示:', data.question);
        return;
    }

    // 检查DOM是否已经存在相同问题
    const existingQuestions = document.querySelectorAll('.message-question');
    const isDuplicate = Array.from(existingQuestions).some(el =>
        el.textContent === data.question &&
        !el.closest('.message-with-options').classList.contains('processed')
    );

    if (isDuplicate) {
        console.log('DOM中已存在相同问题，跳过显示');
        return;
    }

    processedOptionIds.add(optionId);
    console.log('显示新选项:', data.question, 'ID:', optionId);

    // 创建消息容器
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-with-options';
    messageDiv.dataset.optionId = optionId;
    messageDiv.dataset.optionType = data.type;

    // 添加时间戳
    const timestampDiv = document.createElement('div');
    timestampDiv.className = 'message-timestamp';
    timestampDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    messageDiv.appendChild(timestampDiv);

    // 添加消息内容
    if (data.message && data.message.trim()) {
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = data.message;
        messageDiv.appendChild(contentDiv);
    }

    // 添加问题
    const questionDiv = document.createElement('div');
    questionDiv.className = 'message-question';
    questionDiv.textContent = data.question;
    messageDiv.appendChild(questionDiv);

    // 添加选项容器
    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'options-container';

    // 添加各个选项按钮 - 使用事件委托而不是直接绑定
    data.options.forEach(option => {
        const button = document.createElement('button');
        button.className = 'option-button';
        button.textContent = option.text;
        button.dataset.value = option.value;
        button.dataset.optionId = optionId; // 添加optionId到按钮
        optionsContainer.appendChild(button);
    });

    messageDiv.appendChild(optionsContainer);
    outputEl.appendChild(messageDiv);
    outputEl.scrollTop = outputEl.scrollHeight;

    if (data.type === '1') {
        playNotificationSound();
        isShowingOptions = true;
        showToast('请选择选项', 'info');
    }

    // === 关键修复：使用事件委托，避免重复绑定 ===
    // 移除旧的委托监听器（如果存在）
    const existingListener = messageDiv._clickListener;
    if (existingListener) {
        optionsContainer.removeEventListener('click', existingListener);
    }

    // 添加新的事件委托监听器
    const clickHandler = (e) => {
        if (e.target.classList.contains('option-button') && !e.target.disabled) {
            const value = e.target.dataset.value;
            const text = e.target.textContent;
            const optionId = e.target.dataset.optionId;
            const optionType = data.type;

            handleOptionSelection(value, text, optionId, optionType);
        }
    };

    optionsContainer.addEventListener('click', clickHandler);
    messageDiv._clickListener = clickHandler; // 保存引用以便后续移除
}

function handleOptionSelection(value, text, optionId, optionType) {
    console.log('处理选项选择:', text, 'type:', optionType, 'ID:', optionId);

    // === 关键修复：立即移除事件监听器 ===
    const optionElement = document.querySelector(`[data-option-id="${optionId}"]`);
    if (optionElement) {
        const optionsContainer = optionElement.querySelector('.options-container');
        if (optionsContainer && optionElement._clickListener) {
            optionsContainer.removeEventListener('click', optionElement._clickListener);
            delete optionElement._clickListener;
        }

        // 标记为已处理
        optionElement.classList.add('processed');
    }

    // 立即从已处理集合中移除
    processedOptionIds.delete(optionId);

    // 禁用所有相同optionId的按钮
    const optionButtons = document.querySelectorAll(`[data-option-id="${optionId}"] .option-button`);
    optionButtons.forEach(btn => {
        btn.disabled = true;
        btn.style.pointerEvents = 'none';
        if (btn.dataset.value === value) {
            btn.classList.add('selected');
            if (optionType === '1') {
                btn.innerHTML += ' <span class="auto-send-indicator">(自动发送中...)</span>';
            }
        }
    });

    if (optionType === '1') {
        // 防重复检查
        const sendingKey = `sending_${optionId}`;
        if (sessionStorage.getItem(sendingKey)) {
            console.log('该选项已在发送中，跳过');
            return;
        }
        sessionStorage.setItem(sendingKey, 'true');

        setTimeout(() => {
            sessionStorage.removeItem(sendingKey);
        }, 3000);

        setTimeout(() => {
            const input = document.getElementById('message-input');
            input.value = text;
            sendMessage(true, value);
            isShowingOptions = false;

            // 可选：淡出选项界面
            if (optionElement) {
                optionElement.style.opacity = '0.5';
                optionElement.style.transition = 'opacity 0.3s';
                setTimeout(() => {
                    if (optionElement.parentNode) {
                        optionElement.remove();
                    }
                }, 300);
            }
        }, 300);
    } else {
        isShowingOptions = false;
    }
}

function addToHistory(timestamp, message) {
    const historyDiv = document.getElementById('message-history');
    if (!historyDiv) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message-item';
    msgDiv.textContent = `${timestamp}: ${message.substring(0, 100)}${message.length > 100 ? '...' : ''}`;
    historyDiv.appendChild(msgDiv);
    historyDiv.scrollTop = historyDiv.scrollHeight;
}

// ====== API交互 ======
async function checkForOptions() {
    if (isShowingOptions || isProcessing) {
        return;
    }

    try {
        const response = await fetch('/api/options');
        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status}`);
        }

        const data = await response.json();
        console.log('检查选项:', data.status, 'type:', data.type || 'none', 'question:', data.question ? data.question.substring(0, 30) : 'none');

        if (data.status === "options") {
            // === 额外检查：如果正在显示相同问题，跳过 ===
            if (isShowingOptions) {
                console.log('正在显示选项，跳过新选项检查');
                return;
            }

            // 检查DOM是否已经存在相同问题
            const existingQuestions = document.querySelectorAll('.message-question');
            const isDuplicate = Array.from(existingQuestions).some(el => {
                const questionText = el.textContent.trim();
                const newQuestion = data.question ? data.question.trim() : '';
                return questionText === newQuestion && questionText !== '';
            });

            if (isDuplicate) {
                console.log('DOM中已存在相同问题，跳过处理:', data.question.substring(0, 30));
                return;
            }

            if (isTyping) {
                clearInterval(typingInterval);
                isTyping = false;
                const outputEl = document.getElementById('agent-output');
                if (outputEl) {
                    const lastMessage = outputEl.querySelector('.message-block:last-child .message-content');
                    if (lastMessage) {
                        agentOutputBuffer = lastMessage.textContent;
                    }
                }
            }

            if (data.type === "0") {
                console.log('处理type=0更新');
                handleUpdateData(data.update_data);
                showToast('会议信息已更新', 'success');
            } else if (data.type === "1") {
                console.log('处理type=1选项');
                isShowingOptions = true;
                handleQuestionOptions(data);
                showToast('请选择选项', 'info');
            }
        } else if (data.status === "no_options") {
            isShowingOptions = false;
        }
    } catch (error) {
        console.error('获取选项失败:', error);
    }
}

function handleQuestionOptions(data) {
    displayMessageWithOptions(data);
}

function handleUpdateData(updateData) {
    if (!updateData) return;

    console.log('处理更新数据:', updateData);

    const fields = {
        'meeting-date': updateData.date,
        'meeting-time': updateData.time,
        'meeting-type': updateData.type,
        'meeting-topic': updateData.topic,
        'meeting-attendees': updateData.attendees
    };

    let hasUpdate = false;
    Object.entries(fields).forEach(([id, value]) => {
        if (value) {
            const el = document.getElementById(id);
            if (el) {
                const oldValue = el.value;
                if (oldValue !== value) {
                    el.value = value;
                    el.classList.add('field-updated');
                    setTimeout(() => el.classList.remove('field-updated'), 1000);
                    hasUpdate = true;
                }
            }
        }
    });

    if (hasUpdate) {
        showUpdateNotification(updateData);
    }
}

function showUpdateNotification(data) {
    const outputEl = document.getElementById('agent-output');
    if (!outputEl) return;

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const notice = document.createElement('div');
    notice.className = 'update-notice';

    let detailsHtml = '';
    const fields = [
        { key: 'date', label: '会议日期' },
        { key: 'time', label: '会议时间' },
        { key: 'type', label: '会议形式' },
        { key: 'topic', label: '会议主题' },
        { key: 'attendees', label: '与会人员' }
    ];

    fields.forEach(field => {
        if (data[field.key]) {
            detailsHtml += `<div><strong>${field.label}:</strong> ${data[field.key]}</div>`;
        }
    });

    notice.innerHTML = `
        <div class="update-header">
            <strong>📅 会议信息已更新</strong>
            <span class="update-time">${now}</span>
        </div>
        <div class="update-details">
            ${detailsHtml}
        </div>
    `;

    if (outputEl.firstChild) {
        outputEl.insertBefore(notice, outputEl.firstChild);
    } else {
        outputEl.appendChild(notice);
    }

    outputEl.scrollTop = 0;

    setTimeout(() => {
        notice.style.opacity = '0';
        notice.style.transition = 'opacity 0.5s';
        setTimeout(() => {
            if (notice.parentNode) {
                notice.remove();
            }
        }, 500);
    }, 3000);
}

// ====== 发送消息 ======
async function sendMessage(isAutoSend = false, optionValue = '') {
    if (isProcessing) {
        showToast('正在处理上一个请求，请稍候...', 'warning');
        return;
    }

    const input = document.getElementById('message-input');
    const message = input.value.trim();
    const sendBtn = document.getElementById('send-button');

    if (!message) {
        showToast('请输入消息内容', 'warning');
        return;
    }

    sendBtn.classList.add('loading');
    isProcessing = true;
    lockUI(true);
    updateStatus("处理中...");

    const meetingDate = document.getElementById('meeting-date').value;
    const meetingTime = document.getElementById('meeting-time').value;
    const meetingType = document.getElementById('meeting-type').value;
    const meetingTopic = document.getElementById('meeting-topic').value;
    const meetingAttendees = document.getElementById('meeting-attendees').value;

    const fullMessage = `会议信息: 日期: ${meetingDate} 时间: ${meetingTime} 形式: ${meetingType} 主题: ${meetingTopic} 与会人员: ${meetingAttendees}

用户需求: ${isAutoSend ? `[自动选择] ${message}` : message}`;

    try {
        const response = await fetch('/post', {
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
                conversation_id: currentConversationId,
                option_value: optionValue
            })
        });

        const data = await response.json();

        if (data.status === "success") {
            if (!currentConversationId) {
                currentConversationId = data.conversationId;
            }
            typeWriter(`${data.timestamp}: ${data.message}\n`, false);
            addToHistory(data.timestamp, data.message);
            if (!isAutoSend) {
                input.value = '';
            }
            showToast('消息发送成功', 'success');
        } else if (data.blocked_by_options) {
            showToast('请先处理当前选项', 'warning');
            typeWriter(`系统: ${data.message}\n`, false);
            setTimeout(checkForOptions, 500);
        } else {
            updateStatus(`错误: ${data.message}`, true);
            addToHistory(data.timestamp, `[错误] ${data.message}`);
            showToast(data.message, 'error');
        }
    } catch (error) {
        console.error('发送消息失败:', error);
        updateStatus(`请求失败: ${error.message}`, true);
        const timestamp = new Date().toLocaleString();
        addToHistory(timestamp, `[网络错误] ${error.message}`);
        showToast(`发送失败: ${error.message}`, 'error');
    } finally {
        sendBtn.classList.remove('loading');
        isProcessing = false;
        lockUI(false);
        input.focus();
        updateStatus("准备就绪");
    }
}

// ====== 界面功能 ======
function createDecorativeBubbles() {
    const container = document.getElementById('bubbles-container');
    if (!container) return;

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

    for (let i = 0; i < 8; i++) {
        createBubble(container, phrases, i * 300);
    }

    setInterval(() => {
        createBubble(container, phrases);
    }, 8000);
}

function createBubble(container, phrases, delay = 0) {
    setTimeout(() => {
        if (!container) return;

        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.style.left = `${Math.random() * 100}%`;
        bubble.style.bottom = '-20px';
        bubble.style.animationDuration = `${10 + Math.random() * 10}s`;
        bubble.textContent = phrases[Math.floor(Math.random() * phrases.length)];
        container.appendChild(bubble);

        const timeout = setTimeout(() => {
            bubble.remove();
        }, 15000);

        bubble.addEventListener('animationend', () => {
            clearTimeout(timeout);
            bubble.remove();
        });
    }, delay);
}

function playNotificationSound() {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 800;
        oscillator.type = 'sine';

        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.2);
    } catch (e) {
        console.log('音频播放失败，使用静音模式');
    }
}

// ====== 事件监听器 ======
function setupEventListeners() {
    const sendBtn = document.getElementById('send-button');
    if (sendBtn) {
        sendBtn.addEventListener('click', debounce(sendMessage, 300));
    }

    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        });

        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }

    const resetBtn = document.getElementById('reset-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if (confirm('确定要重置会话吗？这将清除所有历史消息。')) {
                fetch('/reset', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            currentConversationId = null;
                            isShowingOptions = false;
                            processedOptionIds.clear();
                            const outputEl = document.getElementById('agent-output');
                            if (outputEl) {
                                outputEl.innerHTML = '会议助手已启动，请输入您的需求...';
                            }
                            const historyDiv = document.getElementById('message-history');
                            if (historyDiv) {
                                historyDiv.innerHTML = '';
                            }
                            showToast('会话已重置', 'success');
                        }
                    })
                    .catch(error => {
                        showToast('重置失败', 'error');
                    });
            }
        });
    }
}

// ====== 初始化 ======
document.addEventListener('DOMContentLoaded', () => {
    console.log('AUKS会议预约助手初始化...');

    createDecorativeBubbles();
    setupEventListeners();

    // 启动选项检查轮询
    optionsCheckInterval = setInterval(checkForOptions, 2000);

    // 立即检查一次
    setTimeout(checkForOptions, 1000);

    // 页面可见性变化
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            clearInterval(optionsCheckInterval);
            console.log('页面隐藏，暂停选项检查');
        } else {
            if (optionsCheckInterval) clearInterval(optionsCheckInterval);
            optionsCheckInterval = setInterval(checkForOptions, 2000);
            console.log('页面显示，恢复选项检查');
            checkForOptions();
        }
    });

    window.addEventListener('beforeunload', () => {
        clearInterval(optionsCheckInterval);
        if (typingInterval) clearInterval(typingInterval);
    });

    console.log('初始化完成');
});