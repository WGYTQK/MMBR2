// ====== 全局变量 ======
let activeForms = new Map();  // 当前显示的表单
let formsCheckInterval;

// ====== 表单管理 ======
async function checkForForms() {
    try {
        console.log('? 检查全局表单...');
        
        const response = await fetch('/api/forms');
        const data = await response.json();
        
        console.log('? 获取全局表单响应:', {
            status: data.status,
            count: data.count,
            is_global: data.is_global
        });
        
        if (data.status === "success") {
            // 更新表单计数
            updateFormCount(data.count);
            
            // 处理新表单
            data.forms.forEach(form => {
                if (!activeForms.has(form.form_id)) {
                    console.log(`? 发现新全局表单: ${form.form_id}`, {
                        type: form.type,
                        question: form.question,
                        source: form.source_ip || 'unknown'
                    });
                    
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
                    console.log(`?? 清理已删除的表单: ${formId}`);
                    removeForm(formId);
                }
            });
        }
    } catch (error) {
        console.error('? 获取表单失败:', error);
    }
}

function displayForm(form) {
    console.log('? 显示全局表单:', {
        form_id: form.form_id,
        type: form.type,
        question: form.question,
        source: form.source_ip || '未知来源'
    });

    const container = document.getElementById('forms-container');
    if (!container) {
        console.error('? 找不到表单容器');
        return;
    }

    const formDiv = document.createElement('div');
    formDiv.className = 'form-card global-form';
    formDiv.dataset.formId = form.form_id;
    formDiv.dataset.formType = form.type;
    
    // 添加全局表单标识
    const isGlobal = form.is_global || form.source_ip;
    
    // 表单头部
    const header = document.createElement('div');
    header.className = 'form-header';

    const title = document.createElement('h4');
    title.textContent = form.question || '请选择';
    
    // 如果是全局表单，添加来源标识
    if (isGlobal && form.source_ip) {
        const sourceSpan = document.createElement('span');
        sourceSpan.className = 'form-source';
        sourceSpan.textContent = ` [来自: ${form.source_ip}]`;
        sourceSpan.style.cssText = 'font-size: 0.8em; color: #666; font-weight: normal;';
        title.appendChild(sourceSpan);
    }
    
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
        // 选择题
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
            });

            optionsContainer.appendChild(btn);
        });

        formDiv.appendChild(optionsContainer);

        // 提交按钮
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
        // 输入表单
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

        // 提交按钮
        const submitBtn = document.createElement('button');
        submitBtn.className = 'form-submit-btn';
        submitBtn.textContent = '提交此表单';
        submitBtn.dataset.formId = form.form_id;

        submitBtn.addEventListener('click', () => {
            handleFormSubmit(form.form_id);
        });

        formDiv.appendChild(submitBtn);
    }

    // 如果是全局表单，添加提示
    if (isGlobal) {
        const globalNote = document.createElement('div');
        globalNote.className = 'global-form-note';
        globalNote.style.cssText = `
            margin-top: 10px;
            padding: 5px;
            background: #f0f7ff;
            border-radius: 3px;
            font-size: 0.85em;
            color: #0066cc;
            border-left: 3px solid #0066cc;
        `;
        globalNote.textContent = '?? 这是全局表单，所有用户都能看到';
        formDiv.appendChild(globalNote);
    }

    container.appendChild(formDiv);

    // 滚动到新表单
    formDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // 显示通知
    const formTypeText = form.type === '1' ? '选择' : '输入';
    showToast(`收到新的${formTypeText}表单`, 'info');
}

function handleOptionSelect(formId, value, text) {
    const form = activeForms.get(formId);
    if (!form) return;

    form.selected_text = text;
    form.selected_value = value;

    console.log(`表单 ${formId} 选择: ${text}`);
}

function handleFormSubmit(formId) {
    const form = activeForms.get(formId);
    if (!form) return;

    if (form.type === '2') {
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

    console.log('? 提交全局表单:', formId, form);

    try {
        const payload = {
            form_id: formId,
            type: form.type,
            form_data: {
                ...(form.selected_text && { selected_text: form.selected_text }),
                ...form.form_data
            }
        };

        const response = await fetch('/api/submit_form', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        console.log('提交响应:', data);

        if (data.status === 'success') {
            // 发送消息
            const input = document.getElementById('message-input');
            input.value = data.message_text;

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
        const validFormData = {};
        let hasInvalid = false;

        activeForms.forEach((form, formId) => {
            const formData = { type: form.type };
            
            if (form.type === '1') {
                if (!form.selected_text) {
                    showToast(`表单 ${formId} 未选择选项`, 'warning');
                    hasInvalid = true;
                    return;
                }
                formData.selected_text = form.selected_text;
                formData.selected_value = form.selected_value;
            } else if (form.type === '2') {
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
                    showToast(`表单 ${formId} 有未填写的字段`, 'warning');
                    hasInvalid = true;
                    return;
                }
                
                formData.form_data = formDataObj;
            }
            
            validFormData[formId] = formData;
        });

        if (hasInvalid) {
            showToast('请完成所有表单后再提交', 'error');
            return;
        }

        console.log('批量提交数据:', validFormData);

        const response = await fetch('/api/submit_all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                form_data: validFormData
            })
        });

        const data = await response.json();
        console.log('批量提交响应:', data);

        if (data.status === 'success') {
            const input = document.getElementById('message-input');
            input.value = data.combined_message;

            await sendMessage(true, 'batch');

            clearAllForms();
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

// ====== 工具函数 ======
function updateFormCount(count) {
    const countElement = document.getElementById('form-count');
    if (countElement) {
        countElement.textContent = `待处理: ${count}`;
        countElement.classList.toggle('has-forms', count > 0);
        
        // 如果是全局表单，添加提示
        if (count > 0) {
            countElement.title = "这是全局表单，所有用户共享";
        }
    }

    const globalActions = document.getElementById('global-actions');
    if (globalActions) {
        globalActions.style.display = count > 0 ? 'flex' : 'none';
    }
}

// ====== 初始化 ======
document.addEventListener('DOMContentLoaded', () => {
    console.log('? AUKS会议助手 - 全局弹窗版初始化...');

    // 启动表单检查轮询
    formsCheckInterval = setInterval(checkForForms, 1000);

    // 立即检查一次
    setTimeout(checkForForms, 500);

    console.log('? 全局弹窗系统初始化完成');
});

// ====== 添加全局表单状态显示 ======
function addGlobalStatusDisplay() {
    const statusDiv = document.createElement('div');
    statusDiv.id = 'global-status';
    statusDiv.style.cssText = `
        position: fixed;
        bottom: 10px;
        left: 10px;
        background: #0066cc;
        color: white;
        padding: 5px 10px;
        border-radius: 3px;
        font-size: 12px;
        z-index: 10000;
    `;
    statusDiv.textContent = '? 全局模式';
    document.body.appendChild(statusDiv);
}

// 在初始化后调用
setTimeout(addGlobalStatusDisplay, 1000);
