// ====== 全局变量 ======
let currentConversationId = null;
let isProcessing = false;
let activeForms = new Map();
let formsCheckInterval;
let isStreaming = false;
let currentStreamDiv = null;

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

function updateFormCount(count) {
    const countElement = document.getElementById('form-count');
    if (countElement) {
        countElement.textContent = `待处理: ${count}`;
        countElement.classList.toggle('has-forms', count > 0);
    }

    const globalActions = document.getElementById('global-actions');
    if (globalActions) {
        globalActions.style.display = count > 0 ? 'flex' : 'none';
    }
}

// ====== 表单管理 ======
async function checkForForms() {
    try {
        const response = await fetch('/api/forms');
        const data = await response.json();

        if (data.status === "success") {
            // 更新表单计数
            updateFormCount(data.count);

            // 处理新表单
            data.forms.forEach(form => {
                if (!activeForms.has(form.form_id)) {
                    displayForm(form);
                    activeForms.set(form.form_id, {
                        ...form,
                        selected_text: '',
                        form_data: {}
                    });
                }
            });

            // 清理已不存在的表单
            const existingFormIds = data.forms.map(f => f.form_id);
            activeForms.forEach((form, formId) => {
                if (!existingFormIds.includes(formId)) {
                    removeForm(formId);
                }
            });
        }
    } catch (error) {
        console.error('获取表单失败:', error);
    }
}

function displayForm(form) {
    const container = document.getElementById('forms-container');
    if (!container) return;

    const formDiv = document.createElement('div');
    formDiv.className = 'form-card';
    formDiv.dataset.formId = form.form_id;
    formDiv.dataset.formType = form.type;

    // 表单头部
    const header = document.createElement('div');
    header.className = 'form-header';

    const title = document.createElement('h4');
    title.textContent = form.question || '请选择';
    header.appendChild(title);

    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-form-btn';
    closeBtn.innerHTML = '&times;';
    closeBtn.title = '关闭';
    closeBtn.addEventListener('click', () => {
        removeForm(form.form_id);
        showToast('表单已关闭', 'info');
    });
    header.appendChild(closeBtn);

    formDiv.appendChild(header);

    // 表单消息
    if (form.message && form.message.trim()) {
        const message = document.createElement('div');
        message.className = 'form-message';
        message.textContent = form.message;
        formDiv.appendChild(message);
    }

    // 根据类型生成不同内容
    if (form.type === '1') {
        // 选择题 - 修改：增加提交按钮
        const optionsContainer = document.createElement('div');
        optionsContainer.className = 'form-options';

        form.options.forEach(option => {
            const btn = document.createElement('button');
            btn.className = 'form-option-btn';
            btn.textContent = option.text;
            btn.dataset.value = option.value;
            btn.dataset.formId = form.form_id;

            btn.addEventListener('click', (e) => {
                handleOptionSelect(form.form_id, option.value, option.text);
                // 标记为已选中
                optionsContainer.querySelectorAll('.form-option-btn').forEach(b => {
                    b.classList.remove('selected');
                });
                btn.classList.add('selected');

                // 自动提交（如果需要的话）
                // setTimeout(() => submitSingleForm(form.form_id), 300);
            });

            optionsContainer.appendChild(btn);
        });

        formDiv.appendChild(optionsContainer);

        // 为选择题添加独立的提交按钮
        const submitBtn = document.createElement('button');
        submitBtn.className = 'form-submit-btn choice-submit-btn';
        submitBtn.textContent = '提交选择';
        submitBtn.dataset.formId = form.form_id;

        submitBtn.addEventListener('click', () => {
            const formData = activeForms.get(form.form_id);
            if (!formData || !formData.selected_text) {
                showToast('请先选择一个选项', 'warning');
                return;
            }
            submitSingleForm(form.form_id);
        });

        formDiv.appendChild(submitBtn);

    } else if (form.type === '2') {
        // 输入表单（保持原有逻辑）
        const inputsContainer = document.createElement('div');
        inputsContainer.className = 'form-inputs';

        form.options.forEach((option, index) => {
            const inputGroup = document.createElement('div');
            inputGroup.className = 'form-input-group';

            const label = document.createElement('label');
            label.textContent = option.text;
            label.htmlFor = `input_${form.form_id}_${index}`;
            inputGroup.appendChild(label);

            const input = document.createElement('input');
            input.type = 'text';
            input.id = `input_${form.form_id}_${index}`;
            input.className = 'form-input';
            input.placeholder = `请输入${option.text}`;
            input.dataset.field = option.value || option.text;
            input.dataset.formId = form.form_id;

            input.addEventListener('input', () => {
                input.classList.remove('error');
            });

            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    handleFormSubmit(form.form_id);
                }
            });

            inputGroup.appendChild(input);
            inputsContainer.appendChild(inputGroup);
        });

        formDiv.appendChild(inputsContainer);

        // 单个表单的提交按钮
        const submitBtn = document.createElement('button');
        submitBtn.className = 'form-submit-btn';
        submitBtn.textContent = '提交此表单';
        submitBtn.dataset.formId = form.form_id;

        submitBtn.addEventListener('click', () => {
            handleFormSubmit(form.form_id);
        });

        formDiv.appendChild(submitBtn);
    }

    container.appendChild(formDiv);

    // 滚动到新表单
    formDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // 显示通知
    const formTypeText = form.type === '1' ? '选择' : '输入';
    showToast(`收到新的${formTypeText}表单`, 'info');
}

// 修改 handleOptionSelect 函数，移除自动提交
function handleOptionSelect(formId, value, text) {
    const form = activeForms.get(formId);
    if (!form) return;

    // 保存选择
    form.selected_text = text;
    form.selected_value = value;

    console.log(`表单 ${formId} 选择: ${text}`);
    // 注意：这里移除了自动提交逻辑
}
// ====== 气泡生成功能 ======
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
        "记得提前测试会议设备",
        "表单已生成，请填写",
        "点击选项后记得提交",
        "可以批量提交所有表单",
        "发送后会清空输入框",
        "气泡自然上浮不旋转",
        "消息发送成功 ✓",
        "请及时处理待办事项",
        "智能助手随时为您服务"
    ];

    // 创建初始气泡
    for (let i = 0; i < 8; i++) {
        createBubble(container, phrases, i * 250);
    }

    // 持续创建新气泡
    setInterval(() => {
        createBubble(container, phrases);
    }, 8000);
}

function createBubble(container, phrases, delay = 0) {
    setTimeout(() => {
        if (!container) return;

        const bubble = document.createElement('div');
        bubble.className = 'bubble';

        // 随机位置
        const leftPos = 5 + Math.random() * 90; // 5%到95%
        bubble.style.left = `${leftPos}%`;
        bubble.style.bottom = '-20px';

        // 随机动画时间
        const duration = 14 + Math.random() * 8; // 14-22秒
        bubble.style.animationDuration = `${duration}s`;

        // 随机内容
        bubble.textContent = phrases[Math.floor(Math.random() * phrases.length)];
        container.appendChild(bubble);

        // 气泡生命周期
        const timeout = setTimeout(() => {
            if (bubble.parentNode) {
                bubble.remove();
            }
        }, duration * 1000 + 1000); // 动画时间+1秒缓冲

        bubble.addEventListener('animationend', () => {
            clearTimeout(timeout);
            if (bubble.parentNode) {
                bubble.remove();
            }
        });

    }, delay);
}
function handleFormSubmit(formId) {
    const form = activeForms.get(formId);
    if (!form) return;

    if (form.type === '2') {
        // 收集输入框数据
        const inputs = document.querySelectorAll(`[data-form-id="${formId}"] .form-input`);
        const formData = {};
        let isValid = true;
        let errorField = '';

        inputs.forEach(input => {
            const value = input.value.trim();
            const field = input.dataset.field;

            if (!value) {
                isValid = false;
                errorField = field;
                input.classList.add('error');
            } else {
                input.classList.remove('error');
                formData[field] = value;
            }
        });

        if (!isValid) {
            showToast(`请填写${errorField}`, 'warning');
            return;
        }

        form.form_data = formData;
    }

    submitSingleForm(formId);
}

async function submitSingleForm(formId) {
    const form = activeForms.get(formId);
    if (!form) {
        console.error('表单不存在:', formId);
        return;
    }

    console.log('提交单个表单:', formId, form);

    try {
        let messageText = '';

        // 构建问题+答案的完整消息
        if (form.type === '1') {
            // 选择题：问题 + 选择的答案
            messageText = `【${form.question}】\n选择：${form.selected_text}`;
        } else if (form.type === '2') {
            // 输入表单：问题 + 所有输入
            const inputs = [];
            for (const [key, value] of Object.entries(form.form_data)) {
                inputs.push(`${key}: ${value}`);
            }
            messageText = `【${form.question}】\n${inputs.join('\n')}`;
        }

        console.log('生成的完整消息:', messageText);

        // 发送到表单提交API
        const payload = {
            form_id: formId,
            type: form.type,
            form_data: {
                ...(form.selected_text && { selected_text: form.selected_text }),
                ...(form.selected_value && { selected_value: form.selected_value }),
                ...form.form_data
            },
            // 添加完整消息
            full_message: messageText
        };

        console.log('提交数据:', payload);

        const response = await fetch('/api/submit_form', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        console.log('提交响应:', data);

        if (data.status === 'success') {
            // 使用完整消息发送
            const input = document.getElementById('message-input');
            input.value = messageText;

            // 发送消息并等待完成
            await sendMessage(true, formId);

            // 移除表单
            removeForm(formId);
            showToast('表单已提交', 'success');
        } else {
            showToast(data.message || '提交失败', 'error');
        }
    } catch (error) {
        console.error('提交表单失败:', error);
        showToast('提交失败，请重试', 'error');
    }
}

async function submitAllForms() {
    if (activeForms.size === 0) {
        showToast('没有待处理的表单', 'warning');
        return;
    }

    if (!confirm(`确定要发送 ${activeForms.size} 个表单吗？`)) {
        return;
    }

    try {
        // 收集所有表单数据
        const validFormData = {};
        const allMessages = [];
        let hasInvalid = false;

        activeForms.forEach((form, formId) => {
            const formData = {
                type: form.type,
                question: form.question || '未命名问题'
            };

            if (form.type === '1') {
                // 选择题
                if (!form.selected_text) {
                    showToast(`"${form.question}" 未选择选项`, 'warning');
                    hasInvalid = true;
                    return;
                }
                formData.selected_text = form.selected_text;
                formData.selected_value = form.selected_value;

                // 构建单个表单的完整消息
                allMessages.push(`【${form.question}】\n选择：${form.selected_text}`);
            } else if (form.type === '2') {
                // 输入表单
                const inputs = document.querySelectorAll(`[data-form-id="${formId}"] .form-input`);
                const formDataObj = {};
                let isValid = true;

                inputs.forEach(input => {
                    const value = input.value.trim();
                    const field = input.dataset.field;
                    if (!value) {
                        isValid = false;
                        input.classList.add('error');
                    } else {
                        input.classList.remove('error');
                        formDataObj[field] = value;
                    }
                });

                if (!isValid) {
                    showToast(`"${form.question}" 有未填写的字段`, 'warning');
                    hasInvalid = true;
                    return;
                }

                formData.form_data = formDataObj;

                // 构建单个表单的完整消息
                const inputsText = Object.entries(formDataObj)
                    .map(([key, value]) => `${key}: ${value}`)
                    .join('\n');
                allMessages.push(`【${form.question}】\n${inputsText}`);
            }

            validFormData[formId] = formData;
        });

        if (hasInvalid) {
            showToast('请完成所有表单后再提交', 'error');
            return;
        }

        if (Object.keys(validFormData).length === 0) {
            showToast('没有有效的表单数据', 'warning');
            return;
        }

        console.log('批量提交数据:', validFormData);
        console.log('生成的完整消息数组:', allMessages);

        // 合并所有消息，用分隔符隔开
        const combinedMessage = allMessages.join('\n\n');

        const response = await fetch('/api/submit_all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                form_data: validFormData,
                combined_message: combinedMessage  // 直接提供合并后的消息
            })
        });

        const data = await response.json();
        console.log('批量提交响应:', data);

        if (data.status === 'success') {
            // 发送合并消息
            const input = document.getElementById('message-input');

            // 使用我们前端生成的完整消息
            const finalMessage = data.combined_message || combinedMessage;
            input.value = finalMessage;

            // 发送消息并等待完成
            await sendMessage(true, 'batch');

            // 清空所有表单
            activeForms.clear();
            const container = document.getElementById('forms-container');
            if (container) {
                container.innerHTML = '';
            }
            updateFormCount(0);
            showToast(`已提交 ${data.count} 个表单`, 'success');
        } else {
            showToast(data.message || '批量提交失败', 'error');
        }
    } catch (error) {
        console.error('批量提交失败:', error);
        showToast('批量提交失败: ' + error.message, 'error');
    }
}

function removeForm(formId) {
    const formElement = document.querySelector(`[data-form-id="${formId}"]`);
    if (formElement) {
        formElement.style.opacity = '0';
        formElement.style.transform = 'translateX(-20px)';
        setTimeout(() => {
            if (formElement.parentNode) {
                formElement.remove();
            }
        }, 300);
    }

    activeForms.delete(formId);
    updateFormCount(activeForms.size);
}

async function clearAllForms() {
    if (activeForms.size === 0) return;

    try {
        const response = await fetch('/api/clear_forms', {
            method: 'POST'
        });

        const data = await response.json();
        if (data.status === 'success') {
            activeForms.clear();
            const container = document.getElementById('forms-container');
            if (container) {
                container.innerHTML = '';
            }
            updateFormCount(0);
            showToast(`已清空 ${data.count} 个表单`, 'info');
        }
    } catch (error) {
        console.error('清空表单失败:', error);
    }
}

// ====== 消息处理 ======
async function sendMessage(isAutoSend = false, source = '') {
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
    updateStatus("处理中...");

    try {
        // 显示用户消息
        if (!isAutoSend) {
            const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const userDiv = document.createElement('div');
            userDiv.className = 'message-block user-message';
            userDiv.innerHTML = `
                <div class="message-timestamp">${timestamp}</div>
                <div class="message-content"><strong>你:</strong> ${message}</div>
            `;
            document.getElementById('agent-output').appendChild(userDiv);
        }

        const response = await fetch('/post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                conversation_id: currentConversationId,
                option_value: source
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status}`);
        }

        // 处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullAnswer = '';

        // 创建AI消息容器
        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        currentStreamDiv = document.createElement('div');
        currentStreamDiv.className = 'message-block ai-message';
        currentStreamDiv.innerHTML = `
            <div class="message-timestamp">${timestamp}</div>
            <div class="message-content"><strong>助手:</strong> <span class="streaming-text"></span></div>
        `;
        document.getElementById('agent-output').appendChild(currentStreamDiv);

        isStreaming = true;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));

                        switch (data.type) {
                            case 'start':
                                console.log('开始接收流式响应');
                                break;

                            case 'chunk':
                                if (currentStreamDiv) {
                                    fullAnswer += data.chunk;
                                    const textSpan = currentStreamDiv.querySelector('.streaming-text');
                                    if (textSpan) {
                                        textSpan.textContent = fullAnswer;
                                    }
                                }
                                break;

                            case 'complete':
                                if (data.answer) {
                                    fullAnswer = data.answer;
                                    if (currentStreamDiv) {
                                        const textSpan = currentStreamDiv.querySelector('.streaming-text');
                                        if (textSpan) {
                                            textSpan.textContent = fullAnswer;
                                        }
                                        currentStreamDiv.classList.add('complete');
                                    }

                                    // 更新conversationId
                                    if (data.conversation_id) {
                                        currentConversationId = data.conversation_id;
                                        console.log('更新conversationId:', currentConversationId);
                                    }
                                }
                                break;

                            case 'error':
                                showToast(data.message || '发生错误', 'error');
                                if (currentStreamDiv) {
                                    currentStreamDiv.classList.add('error-message');
                                    const textSpan = currentStreamDiv.querySelector('.streaming-text');
                                    if (textSpan) {
                                        textSpan.textContent = `错误: ${data.message}`;
                                    }
                                }
                                break;
                        }
                    } catch (e) {
                        console.error('解析流式数据失败:', e);
                    }
                }
            }

            // 滚动到底部
            const outputEl = document.getElementById('agent-output');
            if (outputEl) {
                outputEl.scrollTop = outputEl.scrollHeight;
            }
        }

        // 完成处理
        isStreaming = false;
        currentStreamDiv = null;

        // === 关键修复：无论是否自动发送，都清空输入框 ===
        input.value = '';
        input.style.height = 'auto'; // 重置高度

        showToast('消息发送成功', 'success');

    } catch (error) {
        console.error('发送消息失败:', error);
        updateStatus(`请求失败: ${error.message}`, true);
        showToast(`发送失败: ${error.message}`, 'error');

        if (currentStreamDiv) {
            currentStreamDiv.classList.add('error-message');
            const textSpan = currentStreamDiv.querySelector('.streaming-text');
            if (textSpan) {
                textSpan.textContent = `错误: ${error.message}`;
            }
        }
    } finally {
        sendBtn.classList.remove('loading');
        isProcessing = false;
        updateStatus("准备就绪");
        const input = document.getElementById('message-input');
        if (input) input.focus();
    }
}

// ====== 事件监听器 ======
function setupEventListeners() {
    // 发送按钮
    const sendBtn = document.getElementById('send-button');
    if (sendBtn) {
        sendBtn.addEventListener('click', debounce(() => sendMessage(), 300));
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

    // 全局发送所有按钮
    const submitAllBtn = document.getElementById('submit-all-btn');
    if (submitAllBtn) {
        submitAllBtn.addEventListener('click', submitAllForms);
    }

    // 清空所有按钮
    const clearAllBtn = document.getElementById('clear-all-btn');
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', () => {
            if (activeForms.size > 0) {
                if (confirm(`确定要清空 ${activeForms.size} 个待处理表单吗？`)) {
                    clearAllForms();
                }
            } else {
                showToast('没有待处理的表单', 'info');
            }
        });
    }

    // 重置按钮
    const resetBtn = document.getElementById('reset-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if (confirm('确定要重置会话吗？这将清除所有历史消息和表单。')) {
                fetch('/reset', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            currentConversationId = null;
                            clearAllForms();
                            activeForms.clear();
                            document.getElementById('agent-output').innerHTML =
                                '<div class="message-block">会话已重置，请输入您的需求...</div>';
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
            document.getElementById('agent-output').innerHTML = '输出已清空';
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
                const isAtBottom = outputEl.scrollHeight - outputEl.scrollTop <= outputEl.clientHeight + 10;
                scrollBtn.style.display = isAtBottom ? 'none' : 'block';
            });
        }
    }
}

// ====== 初始化 ======
// ====== 初始化 ======
document.addEventListener('DOMContentLoaded', () => {
    console.log('🤖 AUKS会议预约助手初始化...');

    setupEventListeners();

    // 启动气泡效果
    createDecorativeBubbles();

    // 启动表单检查轮询（每秒检查一次）
    formsCheckInterval = setInterval(checkForForms, 1000);

    // 立即检查一次
    setTimeout(checkForForms, 500);

    // 页面可见性变化
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            console.log('页面隐藏，暂停表单检查');
            clearInterval(formsCheckInterval);
        } else {
            console.log('页面显示，恢复表单检查');
            if (formsCheckInterval) clearInterval(formsCheckInterval);
            formsCheckInterval = setInterval(checkForForms, 1000);
            checkForForms();
        }
    });

    // 页面卸载处理
    window.addEventListener('beforeunload', () => {
        clearInterval(formsCheckInterval);
    });

    console.log('✅ 初始化完成');
});