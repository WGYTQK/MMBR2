// ====== 全局变量 ======
let isProcessing = false;
let isStreaming = false;
let currentStreamDiv = null;

// ====== 工具函数 ======
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

// ====== 信息提取和更新函数 ======
function extractMeetingInfoFromText(text) {
    console.log('📋 从AI回复提取会议信息:', text.substring(0, 200) + '...');

    const fieldMappings = {
        'time': 'meeting-time',
        'topic': 'meeting-topic',
        'location': 'meeting-location',
        'type': 'meeting-type',
        'participants': 'meeting-participants',
        'output': 'output-content' // output不作为表单字段更新
    };

    // 解析新格式：[标识]:{值}
    const pattern = /\[(time|topic|location|type|participants|output)\]:\{([^}]+)\}/g;
    const matches = [...text.matchAll(pattern)];

    console.log('✅ 找到的标识匹配:', matches);

    const updates = {};
    let outputContent = '';
    let hasUpdates = false;

    matches.forEach(match => {
        const fieldId = match[1];
        const value = match[2].trim();

        if (value && value !== '未填写') {
            if (fieldId === 'output') {
                outputContent = value;
                console.log(`📄 提取到output内容: ${value}`);
            } else {
                updates[fieldId] = value;
                hasUpdates = true;
                console.log(`🔄 提取到字段 ${fieldId}: ${value}`);
            }
        }
    });

    // 应用更新到表单
    if (hasUpdates) {
        applyMeetingInfoUpdates(updates);
    }

    // 返回output内容和是否有更新
    return {
        output: outputContent,
        hasUpdates: hasUpdates || outputContent !== ''
    };
}

// ====== 高亮字段 ======
function highlightField(fieldId, value) {
    const fieldMap = {
        'time': 'meeting-time',
        'topic': 'meeting-topic',
        'location': 'meeting-location',
        'type': 'meeting-type',
        'participants': 'meeting-participants'
    };

    const elementId = fieldMap[fieldId];

    if (fieldId === 'type') {
        // 处理会议类型选项
        const radioButtons = document.querySelectorAll('input[name="meeting-type"]');
        radioButtons.forEach(radio => {
            if (radio.value === value) {
                radio.checked = true;
                const label = radio.closest('.compact-option');
                if (label) {
                    label.classList.add('highlight-field');
                    setTimeout(() => label.classList.remove('highlight-field'), 2000);
                }
            }
        });
        showToast(`会议形式已更新为: ${value}`, 'success');
        return;
    }

    if (fieldId === 'participants') {
        // 处理参会人员（文本域）
        const element = document.getElementById(elementId);
        if (element) {
            element.value = value;
            element.classList.add('highlight-field');
            setTimeout(() => element.classList.remove('highlight-field'), 2000);
            showToast(`参会人员已更新`, 'success');
        }
        return;
    }

    const element = document.getElementById(elementId);
    if (element) {
        element.value = value;
        element.classList.add('highlight-field');
        setTimeout(() => element.classList.remove('highlight-field'), 2000);
        showToast(`${getFieldLabel(fieldId)}已更新`, 'success');
    }
}

function getFieldLabel(fieldId) {
    const labels = {
        'time': '会议时间',
        'topic': '会议主题',
        'location': '会议地点',
        'type': '会议形式',
        'participants': '参会人员'
    };
    return labels[fieldId] || fieldId;
}

// ====== 应用会议信息更新 ======
function applyMeetingInfoUpdates(updates) {
    console.log('🔄 应用会议信息更新:', updates);

    Object.entries(updates).forEach(([fieldId, value]) => {
        highlightField(fieldId, value);
    });
}

// ====== 消息发送函数 ======
// ====== 消息发送函数 ======
// ====== 消息发送函数 ======
async function sendMessage() {
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

    // 收集所有表单字段（无论是否为空）
    const time = document.getElementById('meeting-time').value.trim();
    const topic = document.getElementById('meeting-topic').value.trim();
    const location = document.getElementById('meeting-location').value.trim();
    const typeElement = document.querySelector('input[name="meeting-type"]:checked');
    const type = typeElement ? typeElement.value : '';
    const participants = document.getElementById('meeting-participants').value.trim();

    // 构建完整的发送消息
    let fullMessage = message;

    // 添加表单数据到消息中
    const formData = [];
    formData.push(`会议时间：${time || '未收集'}`);
    formData.push(`会议主题：${topic || '未收集'}`);
    formData.push(`会议地点：${location || '未收集'}`);
    formData.push(`会议形式：${type || '未收集'}`);
    formData.push(`参会人员：${participants || '未收集'}`);

    if (formData.length > 0) {
        fullMessage += '\n\n📋 会议信息：\n' + formData.join('\n');
    }

    console.log('📤 发送的消息（包含表单数据）:', fullMessage);

    sendBtn.classList.add('loading');
    isProcessing = true;
    updateStatus("AI正在处理中...");

    try {
        // 显示用户消息
        const timestamp = new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        const userDiv = document.createElement('div');
        userDiv.className = 'message-block user-message';
        userDiv.innerHTML = `
            <div class="message-timestamp">${timestamp} <span class="role-badge">用户</span></div>
            <div class="message-content">${message}</div>
        `;

        const outputEl = document.getElementById('agent-output');
        outputEl.appendChild(userDiv);

        // 清空输入框
        input.value = '';
        input.style.height = 'auto';

        // 发送请求
        const response = await fetch('/post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: fullMessage
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || `HTTP错误: ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            // 创建AI消息容器
            const aiTimestamp = new Date().toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });

            const aiDiv = document.createElement('div');
            aiDiv.className = 'message-block ai-message complete';
            aiDiv.innerHTML = `
                <div class="message-timestamp">${aiTimestamp} <span class="role-badge">会议预约助手</span></div>
                <div class="message-content">${data.answer}</div>
            `;

            outputEl.appendChild(aiDiv);

            // 更新左侧表单字段
            if (data.updates) {
                applyMeetingInfoUpdates(data.updates);
                showToast('会议信息已自动更新', 'success');
            }

            showToast('消息发送成功', 'success');
        } else {
            throw new Error(data.message || '未知错误');
        }

    } catch (error) {
        console.error('❌ 发送消息失败:', error);
        updateStatus(`请求失败: ${error.message}`, true);
        showToast(`发送失败: ${error.message}`, 'error');
    } finally {
        sendBtn.classList.remove('loading');
        isProcessing = false;
        updateStatus("准备就绪");
        input.focus();
        // 滚动到底部
        const outputEl = document.getElementById('agent-output');
        outputEl.scrollTop = outputEl.scrollHeight;
    }
}


// 发送会议信息函数（通过表单发送）
async function sendMeetingInfo() {
    // 收集表单数据
    const time = document.getElementById('meeting-time').value.trim();
    const topic = document.getElementById('meeting-topic').value.trim();
    const location = document.getElementById('meeting-location').value.trim();
    const typeElement = document.querySelector('input[name="meeting-type"]:checked');
    const type = typeElement ? typeElement.value : '';
    const participants = document.getElementById('meeting-participants').value.trim();

    // 检查是否有任何内容
    const hasAnyContent = time || topic || location || type || participants;

    if (!hasAnyContent) {
        showToast('请至少填写一项会议信息', 'warning');
        return;
    }

    // 构建消息（所有字段都发送，空值为"未收集"）
    const formData = [];

    formData.push(`会议时间：${time || '未收集'}`);
    formData.push(`会议主题：${topic || '未收集'}`);
    formData.push(`会议地点：${location || '未收集'}`);
    formData.push(`会议形式：${type || '未收集'}`);
    formData.push(`参会人员：${participants || '未收集'}`);

    const message = '📋 会议信息：\n' + formData.join('\n');

    console.log('📤 发送会议信息:', message);

    // 设置输入框内容并发送
    const input = document.getElementById('message-input');
    input.value = message;

    await sendMessage();
}

// ====== 气泡生成功能 ======
function createDecorativeBubbles() {
    const container = document.getElementById('bubbles-container');
    if (!container) return;

    const phrases = [
        "智能会议预约助手",
        "支持自然语言输入",
        "自动提取会议信息",
        "一键安排会议室",
        "智能识别参会人员",
        "支持多种会议形式",
        "快速生成会议安排",
        "智能推荐会议室",
        "自动更新会议信息",
        "高效会议管理"
    ];

    // 创建初始气泡
    for (let i = 0; i < 15; i++) {
        createBubble(container, phrases, i * 200);
    }

    // 持续创建新气泡
    setInterval(() => {
        createBubble(container, phrases);
    }, 3000);
}

function createBubble(container, phrases, delay = 0) {
    setTimeout(() => {
        if (!container) return;

        const bubble = document.createElement('div');
        bubble.className = 'bubble';

        // 随机位置
        const leftPos = 5 + Math.random() * 90;
        bubble.style.left = `${leftPos}%`;
        bubble.style.bottom = '-30px';

        // 随机动画时间
        const duration = 18 + Math.random() * 8;
        bubble.style.animationDuration = `${duration}s`;

        // 随机内容
        bubble.textContent = phrases[Math.floor(Math.random() * phrases.length)];
        container.appendChild(bubble);

        // 气泡生命周期
        const timeout = setTimeout(() => {
            if (bubble.parentNode) {
                bubble.remove();
            }
        }, duration * 1000 + 2000);

        bubble.addEventListener('animationend', () => {
            clearTimeout(timeout);
            if (bubble.parentNode) {
                bubble.remove();
            }
        });

    }, delay);
}

// ====== 事件监听器 ======
function setupEventListeners() {
    // 发送消息按钮
    const sendBtn = document.getElementById('send-button');
    if (sendBtn) {
        sendBtn.addEventListener('click', () => sendMessage());
    }

    // 发送会议信息按钮
    const sendMeetingBtn = document.getElementById('send-meeting-info');
    if (sendMeetingBtn) {
        sendMeetingBtn.addEventListener('click', () => sendMeetingInfo());
    }

    // 清空会议信息按钮
    const clearMeetingBtn = document.getElementById('clear-meeting-info');
    if (clearMeetingBtn) {
        clearMeetingBtn.addEventListener('click', () => {
            document.getElementById('meeting-time').value = '';
            document.getElementById('meeting-time').placeholder = "请填写会议时间，如：明天下午2点";

            document.getElementById('meeting-topic').value = '';
            document.getElementById('meeting-topic').placeholder = "请填写会议主题";

            document.getElementById('meeting-participants').value = '';
            document.getElementById('meeting-participants').placeholder = "请填写参会人员，每行一个或用逗号分隔";

            document.getElementById('meeting-location').value = '';
            document.getElementById('meeting-location').placeholder = "请填写会议地点";

            document.querySelector('input[name="meeting-type"][value="线上"]').checked = true;

            showToast('会议信息已清空', 'info');
        });
    }

    // 消息输入框事件
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 150) + 'px';
        });
    }

    // 重置按钮
    const resetBtn = document.getElementById('reset-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if (confirm('确定要重置会话吗？这将清除所有对话历史。')) {
                fetch('/reset', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            const outputEl = document.getElementById('agent-output');
                            outputEl.innerHTML = `
                                <div class="welcome-message">
                                    <div class="welcome-header">
                                        <span class="welcome-icon">🔄</span>
                                        <span class="welcome-title">会话已重置</span>
                                    </div>
                                    <div class="welcome-body">
                                        <div class="usage-guide">
                                            <p class="guide-title">📖 会议助手已重新启动</p>
                                            <p>请开始使用左侧表单填写会议信息，或在下方输入消息与AI交流。</p>
                                        </div>
                                    </div>
                                </div>
                            `;
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
    const clearOutputBtn = document.getElementById('clear-output-btn');
    if (clearOutputBtn) {
        clearOutputBtn.addEventListener('click', () => {
            const outputEl = document.getElementById('agent-output');
            if (outputEl.children.length > 1) { // 保留欢迎消息
                const welcomeMessage = outputEl.querySelector('.welcome-message');
                outputEl.innerHTML = '';
                if (welcomeMessage) {
                    outputEl.appendChild(welcomeMessage);
                } else {
                    outputEl.innerHTML = '<div class="welcome-message">对话已清空</div>';
                }
                showToast('对话已清空', 'info');
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
            }
        });

        // 监听滚动事件
        const outputEl = document.getElementById('agent-output');
        if (outputEl) {
            outputEl.addEventListener('scroll', () => {
                const isAtBottom = outputEl.scrollHeight - outputEl.scrollTop <= outputEl.clientHeight + 50;
                scrollBtn.style.display = isAtBottom ? 'none' : 'flex';
            });
        }
    }
}

// ====== 初始化 ======
document.addEventListener('DOMContentLoaded', () => {
    console.log('🤖 AUKS会议预约助手初始化...');

    setupEventListeners();

    // 启动气泡效果
    createDecorativeBubbles();

    // 不添加示例数据，保持表单为空
    setTimeout(() => {
        console.log('✅ 初始化完成');
        console.log('📋 信息提取标识：');
        console.log('  [time]:{值} - 会议时间');
        console.log('  [topic]:{值} - 会议主题');
        console.log('  [location]:{值} - 会议地点');
        console.log('  [type]:{值} - 会议形式');
        console.log('  [participants]:{值} - 参会人员');
        console.log('  [output]:{值} - 其他信息（返回值）');
        console.log('💡 发送时：所有表单字段都会发送，空值为"未收集"');
        console.log('💡 接收时：AI回复应使用[标识]:{值}格式');
    }, 100);
});