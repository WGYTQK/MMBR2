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
        '#reset-btn',
        '.option-button',
        '.input-field',
        '.confirm-btn'
    ];

    elements.forEach(selector => {
        const el = document.querySelectorAll(selector);
        el.forEach(e => {
            e.disabled = lock;
            if (lock) {
                e.classList.add('disabled-ui');
            } else {
                e.classList.remove('disabled-ui');
            }
        });
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

    // 检查是否已存在相同问题
    const existingQuestions = document.querySelectorAll('.message-question');
    const isDuplicate = Array.from(existingQuestions).some(el =>
        el.textContent === data.question
    );

    if (isDuplicate) {
        console.log('DOM中已存在相同问题，跳过显示');
        return;
    }

    if (processedOptionIds.has(optionId)) {
        console.log('选项已处理过，跳过显示:', data.question);
        return;
    }

    processedOptionIds.add(optionId);
    console.log('显示新选项:', data.question, 'type:', data.type, 'ID:', optionId);

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-with-options';
    messageDiv.dataset.optionId = optionId;
    messageDiv.dataset.optionType = data.type;

    const timestampDiv = document.createElement('div');
    timestampDiv.className = 'message-timestamp';
    timestampDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    messageDiv.appendChild(timestampDiv);

    if (data.message && data.message.trim()) {
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = data.message;
        messageDiv.appendChild(contentDiv);
    }

    const questionDiv = document.createElement('div');
    questionDiv.className = 'message-question';
    questionDiv.textContent = data.question;
    messageDiv.appendChild(questionDiv);

    // ====== 根据type类型生成不同的界面 ======
    if (data.type === "1") {
        // type=1: 选择按钮
        displayType1Options(data, messageDiv, optionId);
    } else if (data.type === "2") {
        // type=2: 输入表单
        displayType2Form(data, messageDiv, optionId);
    } else if (data.type === "0") {
        // type=0: 更新显示
        handleUpdateData(data.update_data);
        return; // type=0不显示界面
    }

    outputEl.appendChild(messageDiv);
    outputEl.scrollTop = outputEl.scrollHeight;

    if (data.type === '1' || data.type === '2') {
        playNotificationSound();
        isShowingOptions = true;
        showToast(data.type === '1' ? '请选择选项' : '请输入信息', 'info');
    }
}

function displayType1Options(data, container, optionId) {
    // 添加选项容器
    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'options-container';

    // 添加各个选项按钮
    data.options.forEach(option => {
        const button = document.createElement('button');
        button.className = 'option-button';
        button.textContent = option.text;
        button.dataset.value = option.value;
        button.dataset.optionId = optionId;
        optionsContainer.appendChild(button);
    });

    container.appendChild(optionsContainer);

    // 为选项按钮添加事件委托
    const clickHandler = (e) => {
        if (e.target.classList.contains('option-button') && !e.target.disabled) {
            const value = e.target.dataset.value;
            const text = e.target.textContent;
            const optionId = e.target.dataset.optionId;

            handleOptionSelection(value, text, optionId, "1");
        }
    };

    optionsContainer.addEventListener('click', clickHandler);
    container._clickListener = clickHandler;
}

function displayType2Form(data, container, optionId) {
    // 创建表单容器
    const formContainer = document.createElement('div');
    formContainer.className = 'input-form-container';

    // 创建表单元素
    const form = document.createElement('div');
    form.className = 'input-form';

    // 为每个选项创建输入框
    data.options.forEach((option, index) => {
        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';

        const label = document.createElement('label');
        label.textContent = option.text;
        label.htmlFor = `input_${optionId}_${index}`;
        formGroup.appendChild(label);

        const input = document.createElement('input');
        input.type = 'text';
        input.id = `input_${optionId}_${index}`;
        input.className = 'input-field';
        input.placeholder = `请输入${option.text}`;
        input.dataset.field = option.value || option.text;
        formGroup.appendChild(input);

        form.appendChild(formGroup);
    });

    formContainer.appendChild(form);

    // 添加确认按钮
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'confirm-btn';
    confirmBtn.textContent = '确认提交';
    confirmBtn.dataset.optionId = optionId;
    confirmBtn.dataset.formType = "2";

    confirmBtn.addEventListener('click', () => {
        handleFormSubmit(optionId, "2");
    });

    formContainer.appendChild(confirmBtn);
    container.appendChild(formContainer);
}

function handleFormSubmit(optionId, optionType) {
    const optionElement = document.querySelector(`[data-option-id="${optionId}"]`);
    if (!optionElement) return;

    // 收集表单数据
    const formData = {};
    const inputFields = optionElement.querySelectorAll('.input-field');
    let isValid = true;
    let errorMessage = '';

    inputFields.forEach(input => {
        const value = input.value.trim();
        const fieldName = input.dataset.field || input.placeholder;

        if (!value) {
            isValid = false;
            errorMessage = `请填写${fieldName}`;
            input.classList.add('error');
        } else {
            input.classList.remove('error');
            formData[fieldName] = value;
        }
    });

    if (!isValid) {
        showToast(errorMessage, 'warning');
        return;
    }

    // 构建消息文本
    const formText = Object.entries(formData)
        .map(([key, value]) => `${key}: ${value}`)
        .join(', ');

    console.log('表单提交数据:', formData, '文本:', formText);

    // 禁用表单
    optionElement.querySelectorAll('.input-field, .confirm-btn').forEach(el => {
        el.disabled = true;
    });

    const confirmBtn = optionElement.querySelector('.confirm-btn');
    if (confirmBtn) {
        confirmBtn.textContent = '提交中...';
        confirmBtn.classList.add('submitting');
    }

    // 发送消息
    setTimeout(() => {
        const input = document.getElementById('message-input');
        input.value = formText;
        sendMessage(true, JSON.stringify(formData));

        // 移除选项界面
        processedOptionIds.delete(optionId);
        isShowingOptions = false;

        // 淡出选项界面
        optionElement.style.opacity = '0.5';
        optionElement.style.pointerEvents = 'none';
        setTimeout(() => {
            if (optionElement.parentNode) {
                optionElement.remove();
            }
        }, 300);
    }, 300);
}

function handleOptionSelection(value, text, optionId, optionType) {
    console.log('处理选项选择:', text, 'type:', optionType, 'ID:', optionId);

    // 立即删除已处理的选项ID
    processedOptionIds.delete(optionId);

    // 禁用所有选项按钮
    const optionButtons = document.querySelectorAll(`[data-option-id="${optionId}"] .option-button`);
    optionButtons.forEach(btn => {
        btn.disabled = true;
        btn.style.pointerEvents = 'none';
        if (btn.dataset.value === value) {
            btn.classList.add('selected');
            btn.innerHTML += ' <span class="auto-send-indicator">(自动发送中...)</span>';
        }
    });

    if (optionType === "1") {
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

            // 移除选项界面
            const optionElement = document.querySelector(`[data-option-id="${optionId}"]`);
            if (optionElement) {
                optionElement.style.opacity = '0.5';
                optionElement.style.pointerEvents = 'none';
                setTimeout(() => {
                    if (optionElement.parentNode) {
                        optionElement.remove();
                    }
                }, 300);
            }
        }, 300);
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
            // 检查是否已经在显示相同问题
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
                showToast('信息已更新', 'success');
            } else if (data.type === "1" || data.type === "2") {
                console.log(`处理type=${data.type}选项`);
                isShowingOptions = true;
                displayMessageWithOptions(data);
                showToast(data.type === '1' ? '请选择选项' : '请输入信息', 'info');
            }
        } else if (data.status === "no_options") {
            isShowingOptions = false;
        }
    } catch (error) {
        console.error('获取选项失败:', error);
    }
}

function handleUpdateData(updateData) {
    if (!updateData) return;

    console.log('处理更新数据:', updateData);
    showToast('信息已更新', 'success');

    // 显示更新通知
    showUpdateNotification(updateData);
}

function showUpdateNotification(data) {
    const outputEl = document.getElementById('agent-output');
    if (!outputEl) return;

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const notice = document.createElement('div');
    notice.className = 'update-notice';

    let detailsHtml = '';
    Object.entries(data).forEach(([key, value]) => {
        if (value) {
            detailsHtml += `<div><strong>${key}:</strong> ${value}</div>`;
        }
    });

    notice.innerHTML = `
        <div class="update-header">
            <strong>📅 信息已更新</strong>
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

    try {
        const response = await fetch('/post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
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
    // 发送按钮
    const sendBtn = document.getElementById('send-button');
    if (sendBtn) {
        sendBtn.addEventListener('click', debounce(sendMessage, 300));
    }

    // 输入框回车
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

    // 重置按钮
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

    // 清空输出按钮
    const clearBtn = document.getElementById('clear-output-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            const outputEl = document.getElementById('agent-output');
            if (outputEl) {
                outputEl.innerHTML = '输出已清空';
                processedOptionIds.clear();
            }
        });
    }

    // 滚动到底部按钮
    const scrollBtn = document.getElementById('scroll-down-btn');
    if (scrollBtn) {
        scrollBtn.addEventListener('click', () => {
            const outputEl = document.getElementById('agent-output');
            if (outputEl) {
                outputEl.scrollTop = outputEl.scrollHeight;
                scrollBtn.style.display = 'none';
            }
        });
    }

    // 历史消息切换
    const historyToggle = document.getElementById('history-toggle');
    if (historyToggle) {
        historyToggle.addEventListener('click', function() {
            const historyContainer = document.getElementById('history-container');
            if (historyContainer) {
                const isExpanded = historyContainer.classList.toggle('expanded');
                this.querySelector('.expand-icon').textContent = isExpanded ? '▲' : '▼';
                this.setAttribute('aria-expanded', isExpanded);
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